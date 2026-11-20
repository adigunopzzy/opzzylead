from datetime import datetime, timedelta, timezone

import pandas as pd
import streamlit as st
from supabase import create_client

st.set_page_config(
    page_title="S.O ADIGUN — Scout • Verify • Export",
    page_icon="🟢",
    layout="wide",
)

# Custom Styling to match S.O ADIGUN Lead Scouting UI
st.markdown(
    """
    <style>
    .stApp {
        background-color: #f4f7f9;
        color: #102a43;
    }
    .hero-banner {
        background: linear-gradient(135deg, #102a43 0%, #1d4e68 100%);
        padding: 28px 32px;
        border-radius: 14px;
        color: white;
        margin-bottom: 22px;
    }
    .hero-banner h1 {
        color: white;
        font-size: 26px;
        margin: 0 0 8px 0;
    }
    .hero-banner p {
        color: #d9e2ec;
        font-size: 14px;
        margin: 0 0 16px 0;
    }
    .badge {
        display: inline-block;
        background-color: rgba(255, 255, 255, 0.14);
        color: #e6fffa;
        padding: 5px 12px;
        border-radius: 20px;
        font-size: 12px;
        margin-right: 8px;
        border: 1px solid rgba(255,255,255,0.2);
    }
    .brand-header {
        font-size: 20px;
        font-weight: 800;
        color: #102a43;
        margin-bottom: 2px;
    }
    .brand-sub {
        font-size: 11px;
        letter-spacing: 1.5px;
        color: #0d9488;
        font-weight: 700;
        margin-bottom: 18px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# Sidebar Navigation matching S.O ADIGUN layout
with st.sidebar:
    st.markdown('<div class="brand-header">🟢 S.O ADIGUN</div>', unsafe_allow_html=True)
    st.markdown('<div class="brand-sub">SCOUT • VERIFY • EXPORT</div>', unsafe_allow_html=True)
    page = st.radio(
        "Navigation",
        ["Lead Scouting", "Results & Exports"],
        label_visibility="collapsed",
    )
    st.divider()
    st.caption("NO OUTREACH — Discover, verify, and export real website links, owner emails, and phone numbers.")

# Top Hero Banner
st.markdown(
    """
    <div class="hero-banner">
        <h1>Find 100+ newly launched stores & businesses</h1>
        <p>Scout real websites across 195+ countries, extract verified @gmail.com addresses, find owner phone numbers, and export clean CSV leads — ready for your CRM.</p>
        <span class="badge">Real website links</span>
        <span class="badge">@gmail.com verified</span>
        <span class="badge">Owner phone numbers</span>
        <span class="badge">195+ countries</span>
        <span class="badge">CSV export</span>
    </div>
    """,
    unsafe_allow_html=True,
)

# Filter Card
lead_type = st.radio(
    "Category",
    ["Online Stores", "Businesses (All Platforms)"],
    horizontal=True,
    label_visibility="collapsed",
)

col1, col2 = st.columns(2)
with col1:
    niche_query = st.text_input(
        "Store Niche / Keyword",
        placeholder="e.g. skincare, fashion, gadgets, dental, roofing (leave blank for all)",
    )
with col2:
    country_filter = st.selectbox(
        "Market / Country",
        [
            "All Countries (Global)",
            "United States (+1)",
            "United Kingdom (+44)",
            "Nigeria (+234)",
            "Canada (+1)",
            "Australia (+61)",
            "Europe (+49 / +33 / +31)",
        ],
    )

col3, col4 = st.columns(2)
with col3:
    timeframe = st.selectbox(
        "Launch Timeframe",
        [
            "Today (24 hrs ago)",
            "Last 7 Days",
            "Last 1 Month",
            "Last 3 Months",
            "Up to 1 Year",
        ],
    )
with col4:
    lead_limit_label = st.radio(
        "Target Lead Count",
        ["100+ Stores", "150+ Stores", "250+ Stores"],
        horizontal=True,
    )

col5, col6 = st.columns(2)
with col5:
    platform_choice = st.selectbox(
        "Platform Filter",
        ["All Platforms", "Shopify", "WordPress / WooCommerce", "Wix", "Squarespace", "Webflow", "Local Business / Other"],
    )
with col6:
    gmail_only = st.toggle("Only return @gmail.com email addresses", value=False)
    contact_only = st.toggle("Only show stores with Email, Phone, or WhatsApp", value=False)

# Build Query
limit_num = 100 if "100" in lead_limit_label else (150 if "150" in lead_limit_label else 250)
now = datetime.now(timezone.utc)
if "Today" in timeframe:
    since = now - timedelta(hours=24)
elif "7 Days" in timeframe:
    since = now - timedelta(days=7)
elif "1 Month" in timeframe:
    since = now - timedelta(days=30)
elif "3 Months" in timeframe:
    since = now - timedelta(days=90)
else:
    since = now - timedelta(days=365)

query = (
    supabase.table("leads")
    .select("*")
    .gte("discovered_at", since.isoformat())
    .order("discovered_at", desc=True)
    .limit(1000)
)

if lead_type == "Online Stores" and platform_choice == "All Platforms":
    query = query.in_("platform", ["Shopify", "WordPress / WooCommerce", "Wix", "Squarespace", "Webflow"])
elif platform_choice != "All Platforms":
    query = query.eq("platform", platform_choice)

rows = query.execute().data or []
df = pd.DataFrame(rows)

if not df.empty:
    # Niche keyword filter
    if niche_query.strip():
        keywords = [k.strip().lower() for k in niche_query.split(",") if k.strip()]
        mask = df.apply(
            lambda r: any(
                kw in str(r.get("domain", "")).lower()
                or kw in str(r.get("social_links", "")).lower()
                for kw in keywords
            ),
            axis=1,
        )
        df = df[mask]

    # Country prefix filter
    if country_filter != "All Countries (Global)":
        code_map = {
            "United States (+1)": "+1",
            "United Kingdom (+44)": "+44",
            "Nigeria (+234)": "+234",
            "Canada (+1)": "+1",
            "Australia (+61)": "+61",
            "Europe (+49 / +33 / +31)": ("+49", "+33", "+31", "+34", "+39"),
        }
        prefix = code_map[country_filter]
        df = df[df["phone"].fillna("").str.startswith(prefix)]

    if gmail_only:
        df = df[df["email"].fillna("").str.lower().str.contains("@gmail.com")]

    if contact_only:
        df = df[df["email"].notna() | df["phone"].notna() | df["whatsapp_url"].notna()]

    df = df.head(limit_num)

st.divider()
st.subheader(f"Results ({len(df)} Verified Leads)")

if not df.empty:
    display_cols = [
        "domain",
        "website_url",
        "platform",
        "email",
        "phone",
        "whatsapp_url",
        "social_links",
        "discovered_at",
    ]
    df_view = df[[c for c in display_cols if c in df.columns]].rename(
        columns={
            "domain": "Store / Domain",
            "website_url": "Website Link",
            "platform": "Platform",
            "email": "Owner Email",
            "phone": "Phone Number",
            "whatsapp_url": "WhatsApp",
            "social_links": "Store Niche / Title",
            "discovered_at": "Launched",
        }
    )

    st.dataframe(
        df_view,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Website Link": st.column_config.LinkColumn("Website Link", display_text="Visit Store ↗"),
            "WhatsApp": st.column_config.LinkColumn("WhatsApp", display_text="Chat on WhatsApp ↗"),
        },
    )

    csv = df_view.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="⬇️ Export Leads to CSV",
        data=csv,
        file_name=f"so_adigun_leads_{datetime.now().strftime('%Y%m%d')}.csv",
        mime="text/csv",
        type="primary",
    )
else:
    st.info("No leads matched these filters yet. Try switching 'Online Stores' to 'Businesses (All Platforms)', expanding Launch Timeframe to 'Up to 1 Year', or running your GitHub scraper!")
