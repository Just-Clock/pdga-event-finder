# app.py

import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import re
import io

st.set_page_config(page_title="PDGA Event Tracker", layout="wide")

# =========================================================
# FIXED WATCHLIST
# =========================================================

WATCHLIST = [
    83596,231663,126098,299223,197269,220870,180280,207096,72628,294797,
    253260,193824,275893,128316,241718,269038,87094,259842,95343,232260,
    168353,244806,167837,181739,142155,146226,283063,242035,106118,167184,
    83649,189511,194555,104226,308064,159762,75861,312238,295124,140354,
    179839,132038,143853,103087,250811,269079,105496,83627,214778,111943,
    145131,156926,282268,103627,258743,127864,180461,274791,106751
]

BASE_URL = "https://www.pdga.com/player/"


# =========================================================
# CACHED PLAYER PAGE FETCH
# =========================================================

@st.cache_data(ttl=3600)
def fetch_player_page(pdga_number):

    url = f"{BASE_URL}{pdga_number}"

    response = requests.get(
        url,
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=20
    )

    response.raise_for_status()

    return response.text


# =========================================================
# EVENT EXTRACTION
# =========================================================

def extract_events(soup):

    rows = []

    for details in soup.find_all("details"):

        title = details.get("title", "")

        if not title:
            continue

        matches = re.findall(
            r"([A-Za-z]{3,9}\s+\d{1,2},?\s+\d{4})\s*:?\s*([^|]+)",
            title
        )

        for date_text, event_name in matches:

            try:

                event_date = pd.to_datetime(date_text)

                rows.append(
                    {
                        "Date": event_date.date(),
                        "Event": event_name.strip().lstrip(":").strip()
                    }
                )

            except Exception:
                pass

    return rows


# =========================================================
# PLAYER SCRAPER
# =========================================================

def scrape_player(pdga_number):

    try:

        html = fetch_player_page(pdga_number)

        soup = BeautifulSoup(html, "html.parser")

        name_tag = soup.find("h1")

        player_name = (
            name_tag.get_text(strip=True)
            if name_tag
            else "Unknown"
        )

        events = extract_events(soup)

        rows = []

        for event in events:

            rows.append(
                {
                    "PDGA": pdga_number,
                    "Name": player_name,
                    "Date": event["Date"],
                    "Event": event["Event"]
                }
            )

        return rows

    except Exception as e:

        return [
            {
                "PDGA": pdga_number,
                "Name": "Error",
                "Date": None,
                "Event": str(e)
            }
        ]


# =========================================================
# SERIAL SCRAPER
# =========================================================

def run_scraper(numbers):

    all_rows = []

    progress = st.progress(0)

    total = len(numbers)

    for idx, pdga_number in enumerate(numbers):

        rows = scrape_player(pdga_number)

        all_rows.extend(rows)

        progress.progress((idx + 1) / total)

    progress.empty()

    df = pd.DataFrame(all_rows)

    if not df.empty and "Date" in df.columns:
        df = df.sort_values(
            by="Date",
            na_position="last"
        )

    return df


# =========================================================
# APP UI
# =========================================================

st.title("🥏 PDGA Event Tracker")

# =========================================================
# WATCHLIST SECTION
# =========================================================

st.header("📌 Watchlist")

watchlist_df = pd.DataFrame(
    {"PDGA": WATCHLIST}
)

st.caption(f"{len(WATCHLIST)} players in watchlist")

st.download_button(
    label="📄 Export Watchlist CSV",
    data=watchlist_df.to_csv(index=False),
    file_name="watchlist.csv",
    mime="text/csv"
)

if st.button("Run Watchlist Scrape"):

    with st.spinner("Scraping watchlist..."):

        df_watch = run_scraper(WATCHLIST)

    st.dataframe(
        df_watch,
        use_container_width=True
    )

    excel_buffer = io.BytesIO()

    with pd.ExcelWriter(
        excel_buffer,
        engine="openpyxl"
    ) as writer:

        df_watch.to_excel(
            writer,
            index=False,
            sheet_name="Watchlist"
        )

    st.download_button(
        label="📥 Download Watchlist Excel",
        data=excel_buffer.getvalue(),
        file_name="pdga_watchlist.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


st.divider()

# =========================================================
# MANUAL LOOKUP SECTION
# =========================================================

st.header("🔎 Manual Lookup")

manual_input = st.text_area(
    "Enter PDGA numbers (comma, space, or newline separated)"
)

if st.button("Run Manual Scrape"):

    numbers = [
        int(x)
        for x in re.findall(r"\d+", manual_input)
    ]

    if not numbers:

        st.warning("No valid PDGA numbers entered.")

    else:

        with st.spinner("Scraping manual list..."):

            df_manual = run_scraper(numbers)

        st.dataframe(
            df_manual,
            use_container_width=True
        )

        excel_buffer = io.BytesIO()

        with pd.ExcelWriter(
            excel_buffer,
            engine="openpyxl"
        ) as writer:

            df_manual.to_excel(
                writer,
                index=False,
                sheet_name="Manual"
            )

        st.download_button(
            label="📥 Download Manual Excel",
            data=excel_buffer.getvalue(),
            file_name="pdga_manual.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )