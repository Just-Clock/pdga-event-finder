import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import re
import time
from datetime import datetime

BASE_URL = "https://www.pdga.com"
PLAYER_URL = "https://www.pdga.com/player/"


# -----------------------
# EXTRACT DATE FROM EVENT PAGE
# -----------------------
def scrape_event_page(event_url):
    try:
        r = requests.get(event_url, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")

        text = soup.get_text(" ", strip=True)
        text = re.sub(r"\s+", " ", text)

        # Look for common PDGA event date formats
        date_pattern = r"""(
            (Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s\d{1,2},\s\d{4}
            |
            \d{1,2}-[A-Za-z]{3}-\d{4}
        )"""

        match = re.search(date_pattern, text, re.VERBOSE)

        if not match:
            return None

        raw_date = match.group(0)

        # Normalize
        try:
            if "-" in raw_date and len(raw_date.split("-")) == 3:
                return datetime.strptime(raw_date, "%d-%b-%Y")

            return datetime.strptime(raw_date, "%B %d, %Y")
        except:
            return None

    except:
        return None


# -----------------------
# SCRAPE PLAYER PAGE (GET LINKS ONLY)
# -----------------------
def get_player_rows(pdga_number):
    url = f"{PLAYER_URL}{pdga_number}"
    rows = []

    try:
        r = requests.get(url, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")

        name_tag = soup.find("h1")
        name = name_tag.text.strip() if name_tag else "Unknown"

        details_blocks = soup.find_all("details")

        upcoming_section = None
        for d in details_blocks:
            summary = d.find("summary")
            if summary and "upcoming" in summary.text.lower():
                upcoming_section = d
                break

        if not upcoming_section:
            return [{
                "PDGA": pdga_number,
                "Name": name,
                "Date": None,
                "Event": "None",
                "Event URL": ""
            }]

        # Find event links
        links = upcoming_section.find_all("a", href=True)

        for link in links:
            href = link["href"]

            # filter only event pages
            if "/event/" not in href and "/tour/event/" not in href:
                continue

            event_name = link.get_text(strip=True)
            event_url = BASE_URL + href

            # 🔥 SCRAPE REAL DATE FROM EVENT PAGE
            event_date = scrape_event_page(event_url)

            rows.append({
                "PDGA": pdga_number,
                "Name": name,
                "Date": event_date,
                "Event": event_name,
                "Event URL": event_url
            })

            time.sleep(0.3)  # be polite to PDGA servers

        return rows if rows else [{
            "PDGA": pdga_number,
            "Name": name,
            "Date": None,
            "Event": "None",
            "Event URL": ""
        }]

    except Exception as e:
        return [{
            "PDGA": pdga_number,
            "Name": "Error",
            "Date": None,
            "Event": str(e),
            "Event URL": ""
        }]


# -----------------------
# RUN SCRAPER
# -----------------------
def run_scraper(numbers):
    all_rows = []

    for n in numbers:
        all_rows.extend(get_player_rows(n))

    return all_rows


# -----------------------
# UI
# -----------------------
st.title("🥏 PDGA Event Tracker (Event Page Scraper)")

input_text = st.text_area("Enter PDGA numbers (comma or newline separated)")

if st.button("Fetch Events"):

    numbers = [
        int(x.strip())
        for x in input_text.replace(",", "\n").split()
        if x.strip().isdigit()
    ]

    with st.spinner("Scraping PDGA event pages..."):
        data = run_scraper(numbers)
        df = pd.DataFrame(data)

    # Sort safely
    df = df.sort_values(by="Date", ascending=True, na_position="last")

    # Remove time
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce").dt.date

    st.success("Done!")
    st.dataframe(df)

    file_name = "pdga_events.xlsx"
    df.to_excel(file_name, index=False)

    with open(file_name, "rb") as f:
        st.download_button("📥 Download Excel", f, file_name=file_name)