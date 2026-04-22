import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import re
import time
from datetime import datetime

BASE_URL = "https://www.pdga.com/player/"


# -----------------------
# EXTRACT MULTIPLE EVENTS
# -----------------------
def extract_all_events(text):
    date_pattern = r"((Mon|Tue|Wed|Thu|Fri|Sat|Sun)[a-z]*,?\s+)?(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s\d{1,2}(?:–\d{1,2})?,\s\d{4}"

    matches = list(re.finditer(date_pattern, text))
    events = []

    for i, match in enumerate(matches):
        full_date = match.group(0)

        # Remove weekday
        cleaned_date = re.sub(
            r"^(Mon|Tue|Wed|Thu|Fri|Sat|Sun)[a-z]*,?\s+",
            "",
            full_date
        )

        start = match.end()

        if i + 1 < len(matches):
            end = matches[i + 1].start()
        else:
            end = len(text)

        event_name = text[start:end].strip()

        # Clean leading junk
        event_name = re.sub(r"^[:\-\s]+", "", event_name)

        events.append((cleaned_date, event_name))

    return events


# -----------------------
# NORMALIZE DATE
# -----------------------
def normalize_date(date_str):
    try:
        # Convert range → first day only
        date_str = re.sub(r"–\d{1,2}", "", date_str)
        return datetime.strptime(date_str, "%B %d, %Y")
    except:
        return None


# -----------------------
# SCRAPE ONE PLAYER → MULTIPLE ROWS
# -----------------------
def get_player_rows(pdga_number):
    url = f"{BASE_URL}{pdga_number}"
    rows = []

    try:
        response = requests.get(url, timeout=10)
        soup = BeautifulSoup(response.text, "html.parser")

        # Player name
        name_tag = soup.find("h1")
        name = name_tag.text.strip() if name_tag else "Unknown"

        # Find Upcoming Events section
        details_blocks = soup.find_all("details")

        upcoming_text = None

        for d in details_blocks:
            summary = d.find("summary")
            if summary and "upcoming" in summary.text.lower():
                upcoming_text = d.get_text(" ", strip=True)
                break

        if not upcoming_text:
            return [{
                "PDGA": pdga_number,
                "Name": name,
                "Date": None,
                "Event": "None"
            }]

        # Clean label
        cleaned = upcoming_text.replace("Upcoming Events", "").strip()

        events = extract_all_events(cleaned)

        for date_str, event_name in events:
            rows.append({
                "PDGA": pdga_number,
                "Name": name,
                "Date": normalize_date(date_str),
                "Event": event_name
            })

        return rows

    except Exception as e:
        return [{
            "PDGA": pdga_number,
            "Name": "Error",
            "Date": None,
            "Event": str(e)
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
st.title("🥏 PDGA Event Tracker (Long Format)")

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

    st.success("Done!")
    st.dataframe(df)

    # Export to Excel
    file_name = "pdga_events.xlsx"
    df.to_excel(file_name, index=False)

    with open(file_name, "rb") as f:
        st.download_button("📥 Download Excel", f, file_name=file_name)