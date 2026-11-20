import os
from datetime import datetime, timedelta, timezone

import pandas as pd
import streamlit as st
from supabase import create_client

st.set_page_config(page_title="OpzzyLead — Fresh Store Finder", layout="wide")
st.title("OpzzyLead — Newly Launched Stores & Websites")

SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# Top Filter Controls
col1, col2, col3 = st.columns([2, 2, 3])
with col1:
    timeframe = st.selectbox(
        "Discovered Timeframe",
        ["Today", "Last 7 Days", "Last 1 Month", "Last 3 Months", "Up to 1 Year"],
    )
with col2:
    platform_filter = st.selectbox(
        "Platform",
        ["All", "Shopify", "WordPress / WooCommerce", "Wix", "Squarespace", "Webflow", "Custom / Other"],
    )
with col3:
    only_with_contact = st.checkbox("Only show leads with Phone, WhatsApp, or Email", value=False)

now = datetime.now(timezone.utc)
if timeframe == "Today":
    since = now.replace(hour=0, minute=0, second=0, microsecond=0)
elif timeframe == "Last 7 Days":
    since = now - timedelta(days=7)
elif timeframe == "Last 1 Month":
    since = now - timedelta(days=30)
elif timeframe == "Last 3 Months":
    since = now - timedelta(days=90)
else:
    since = now - timedelta(days=365)

query = (
    supabase.table("leads")
    .select("*")
    .gte("discovered_at", since.isoformat())
    .order("discovered_at", desc=True)
    .limit(5000)
)
if platform_filter != "All":
    query = query.eq("platform", platform_filter)

rows = query.execute().data or []
df = pd.DataFrame(rows)

if not df.empty:
    if only_with_contact:
        df = df[
            df["email"].notna() | df["phone"].notna() | df["whatsapp_url"].notna()
        ]

    st.metric(f"Leads Found ({timeframe})", len(df))

    display_cols = [
        "domain",
        "website_url",
        "platform",
        "phone",
        "whatsapp_url",
        "email",
        "social_links",
        "discovered_at",
    ]
    df = df[[c for c in display_cols if c in df.columns]]

    st.dataframe(
        df,
        use_container_width=True,
        column_config={
            "website_url": st.column_config.LinkColumn("Website Link"),
            "whatsapp_url": st.column_config.LinkColumn("WhatsApp Link"),
        },
    )

    csv = df.to_csv(index=False).encode("utf-8")
    st.download_button(
        "Download Filtered Leads (CSV)",
        data=csv,
        file_name=f"opzzylead_{timeframe.lower().replace(' ', '_')}.csv",
        mime="text/csv",
    )
else:
    st.info("No leads found for this filter yet. Check back after the next daily run!")
