import os
import re
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import urljoin

import phonenumbers
import requests
from bs4 import BeautifulSoup
from supabase import create_client

SUPABASE_URL = os.environ["SUPABASE_URL"].strip()
SUPABASE_KEY = os.environ["SUPABASE_KEY"].strip()
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

DAILY_LIMIT = 250
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
}


def cleanup_old_leads():
    cutoff = (datetime.now(timezone.utc) - timedelta(days=365)).isoformat()
    supabase.table("leads").delete().lt("discovered_at", cutoff).execute()


def get_today_count():
    start_of_day = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    ).isoformat()
    res = (
        supabase.table("leads")
        .select("id", count="exact")
        .gte("discovered_at", start_of_day)
        .execute()
    )
    return res.count or 0


def fetch_new_domains():
    domains = set()

    queries = [
        "myshopify.com",
        "mybigcommerce.com",
        "wixsite.com",
        "squarespace.com",
        "webflow.io",
        "shopify",
        "boutique",
        "skincare",
        "dental",
        "roofing",
    ]
    for q in queries:
        try:
            url = f"https://crt.sh{q}&exclude=expired&output=json"
            resp = requests.get(url, headers=HEADERS, timeout=25)
            if resp.status_code == 200:
                data = resp.json()
                for entry in data[:120]:
                    raw = entry.get("name_value", "") or entry.get("common_name", "")
                    for line in raw.splitlines():
                        name = line.lower().strip()
                        if (
                            name
                            and not name.startswith("*")
                            and "." in name
                            and not name.startswith("www.")
                        ):
                            domains.add(name)
            time.sleep(3)
        except Exception as e:
            print(f"crt.sh skipped {q}: {e}")

    for domain_root in ("myshopify.com", "webflow.io", "wixsite.com"):
        try:
            url = f"https://certspotter.com{domain_root}&include_subdomains=true&expand=dns_names"
            resp = requests.get(url, headers=HEADERS, timeout=20)
            if resp.status_code == 200:
                for item in resp.json():
                    for name in item.get("dns_names", []):
                        name = name.lower().strip()
                        if name and not name.startswith("*") and "." in name:
                            domains.add(name)
            time.sleep(2)
        except Exception as e:
            print(f"CertSpotter skipped {domain_root}: {e}")

    return list(domains)


def detect_platform(html_lower, domain):
    if "://shopify.com" in html_lower or ".myshopify.com" in domain:
        return "Shopify"
    if "wp-content" in html_lower or "woocommerce" in html_lower:
        return "WordPress / WooCommerce"
    if "wix.com" in html_lower or "wixstatic" in html_lower or ".wixsite.com" in domain:
        return "Wix"
    if "squarespace" in html_lower:
        return "Squarespace"
    if "webflow" in html_lower or ".webflow.io" in domain:
        return "Webflow"
    return "Local Business / Other"


def extract_contacts(html, base_url):
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text(" ", strip=True)

    emails = set(re.findall(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", html))
    clean_emails = [
        e
        for e in emails
        if not e.lower().endswith(
            (".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", "sentry.io", "example.com", "wixpress.com")
        )
    ]

    phones = set()
    whatsapp_url = ""

    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        lower_href = href.lower()
        if lower_href.startswith("tel:"):
            _, _, after_colon = href.partition(":")
            raw_num, _, _ = after_colon.partition("?")
            phones.add(raw_num.strip())
        elif "wa.me/" in lower_href or "://whatsapp.com" in lower_href:
            whatsapp_url = href

    valid_phones = []
    for candidate in list(phones) + re.findall(r"\+?\d[\d\s().-]{7,18}\d", text):
        try:
            parsed = phonenumbers.parse(candidate, None)
            if phonenumbers.is_valid_number(parsed):
                formatted = phonenumbers.format_number(
                    parsed, phonenumbers.PhoneNumberFormat.INTERNATIONAL
                )
                if formatted not in valid_phones:
                    valid_phones.append(formatted)
        except Exception:
            continue

    socials = set()
    social_domains = (
        "://instagram.com",
        "://facebook.com",
        "://tiktok.com",
        "://twitter.com",
        "://x.com",
        "://linkedin.com",
    )
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if any(sd in href.lower() for sd in social_domains):
            socials.add(href)

    title = soup.title.string.strip() if soup.title and soup.title.string else ""
    meta_desc = ""
    meta_tag = soup.find("meta", attrs={"name": "description"})
    if meta_tag and meta_tag.get("content"):
        meta_desc = meta_tag["content"].strip()

    niche_summary = f"{title} {meta_desc}".strip()[:250]

    return (
        ", ".join(clean_emails[:2]),
        ", ".join(valid_phones[:2]),
        whatsapp_url,
        ", ".join(list(socials)[:4]),
        niche_summary,
    )


def scrape_site(domain):
    url = f"https://{domain}"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10, allow_redirects=True)
        if resp.status_code >= 400:
            return None
        html = resp.text
        platform = detect_platform(html.lower(), domain)
        email, phone, whatsapp, socials, niche_summary = extract_contacts(html, resp.url)

        if not email or not phone:
            for path in ("/pages/contact", "/contact", "/contact-us"):
                try:
                    c_resp = requests.get(urljoin(resp.url, path), headers=HEADERS, timeout=6)
                    if c_resp.status_code == 200:
                        e2, p2, w2, s2, _ = extract_contacts(c_resp.text, c_resp.url)
                        email = email or e2
                        phone = phone or p2
                        whatsapp = whatsapp or w2
                        if s2:
                            socials = ", ".join(
                                set(filter(None, (socials + ", " + s2).split(", ")))
                            )
                        if email and phone:
                            break
                except Exception:
                    continue

        return {
            "domain": domain,
            "website_url": resp.url,
            "platform": platform,
            "email": email or None,
            "phone": phone or None,
            "whatsapp_url": whatsapp or None,
            "social_links": niche_summary or socials or None,
        }
    except Exception:
        return None


def main():
    cleanup_old_leads()
    current_today = get_today_count()
    print(f"Leads collected today so far: {current_today}/{DAILY_LIMIT}")

    if current_today >= DAILY_LIMIT:
        print("Daily limit of 250 reached. Waiting until midnight UTC.")
        return

    candidates = fetch_new_domains()
    print(f"Found {len(candidates)} candidate domains to inspect.")

    added = 0
    for domain in candidates:
        if current_today + added >= DAILY_LIMIT:
            break

        existing = supabase.table("leads").select("id").eq("domain", domain).execute()
        if existing.data:
            continue

        lead = scrape_site(domain)
        if lead:
            try:
                supabase.table("leads").insert(lead).execute()
                added += 1
                print(f"[{current_today + added}/{DAILY_LIMIT}] Saved: {domain} ({lead['platform']})")
            except Exception as e:
                print(f"Insert skipped for {domain}: {e}")

    print(f"Done! Added {added} new leads.")


if __name__ == "__main__":
    main()

