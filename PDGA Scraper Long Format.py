import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import re
import time
from datetime import datetime

BASE_URL = "https://www.pdga.com/player/"


# -----------------------
# DATE NORMALIZER
# -----------------------
def normalize_date(date_str):
    if not date_str:
        return None

    try:
        # Remove weekday if present
        date_str = re.sub(
            r"^(Mon|Tue|Wed|Thu|Fri|Sat|Sun)[a-z]*,?\s+",
            "",
            date_str
        )

        # Handle ranges like "May 3–5, 2026"
        date_str = re.sub(r"–\d{1,2}", "", date_str)

        # Format: 12-Jul-2026
        if "-" in date_str and date_str.count("-") == 2:
            return datetime.strptime(date_str, "%d-%b-%Y")

        # Format: 6/15/2026
        if "/" in date_str:
            return datetime.strptime(date_str, "%m/%d/%Y")

        # Format: May 3, 2026
        return datetime.strptime(date_str, "%B %d, %Y")

    except:
        return None


# -----------------------
# SCRAPE PLAYER (LINK-BASED)
# -----------------------
def get_player_rows(pdga_number):
    url = f"{BASE_URL}{pdga_number}"
    rows = []

    try:
        response = requests.get(url, timeout=10)
        soup = BeautifulSoup(response.text, "html.parser")

        name_tag = soup.find("h1")
        name = name_tag.text.strip() if name_tag else "Unknown"

        # Find Upcoming section
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

        # 🔥 FULL TEXT (critical fix)
        full_text = upcoming_section.get_text(" ", strip=True)
        full_text = re.sub(r"\s+", " ", full_text)

        # 🔥 Find ALL dates in full text
        date_pattern = r"""(
            (Mon|Tue|Wed|Thu|Fri|Sat|Sun)[a-z]*,?\s+
            (Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s\d{1,2}(?:–\d{1,2})?,\s\d{4}
            |
            (Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s\d{1,2}(?:–\d{1,2})?,\s\d{4}
            |
            \d{1,2}-[A-Za-z]{3}-\d{4}
            |
            \d{1,2}/\d{1,2}/\d{4}
        )"""

        date_matches = list(re.finditer(date_pattern, full_text, re.VERBOSE))

        # Store (position, cleaned_date)
        parsed_dates = []
        for m in date_matches:
            raw_date = m.group(0)

            cleaned_date = re.sub(
                r"^(Mon|Tue|Wed|Thu|Fri|Sat|Sun)[a-z]*,?\s+",
                "",
                raw_date
            )

            parsed_dates.append((m.start(), cleaned_date))

        # 🔥 Extract event links
        links = upcoming_section.find_all("a", href=True)

        for link in links:
            href = link["href"]

            if "/event/" not in href and "/tour/event/" not in href:
                continue

            event_name = link.get_text(strip=True)

            # Find link position in full text
            link_text = link.get_text(strip=True)
            link_pos = full_text.find(link_text)

            # Find closest date BEFORE this link
            event_date = None

            for pos, d in reversed(parsed_dates):
                if pos <= link_pos:
                    event_date = d
                    break

            rows.append({
                "PDGA": pdga_number,
                "Name": name,
                "Date": normalize_date(event_date),
                "Event": event_name,
                "Event URL": f"https://www.pdga.com{href}"
            })

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
        time.sleep(0.4)  # be polite

    return all_rows


# -----------------------
# UI
# -----------------------
st.title("🥏 PDGA Event Tracker (Link-Based)")

input_text = st.text_area("Enter PDGA numbers (comma or newline separated)")

if st.button("Fetch Events"):

    numbers = [
        int(x.strip())
        for x in input_text.replace(",", "\n").split()
        if x.strip().isdigit()
    ]

    with st.spinner("Scraping PDGA data..."):
        data = run_scraper(numbers)
        df = pd.DataFrame(data)

    # Sort by soonest upcoming
    df = df.sort_values(by="Date", ascending=True, na_position="last")

    # Remove time from display
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce").dt.date

    st.success("Done!")
    st.dataframe(df)

    # Export to Excel
    file_name = "pdga_events.xlsx"
    df.to_excel(file_name, index=False)

    with open(file_name, "rb") as f:
        st.download_button("📥 Download Excel", f, file_name=file_name)