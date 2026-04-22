import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import re
import time

BASE_URL = "https://www.pdga.com/player/"


# -----------------------
# DATE PARSER (KEY FIX)
# -----------------------
import re

def extract_event_and_date(text):
    """
    Pattern: DATE comes first, then EVENT NAME
    Example:
    "May 3–5, 2026 Spring Classic"
    """

    # Match PDGA-style dates
    date_pattern = r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s\d{1,2}(?:–\d{1,2})?,\s\d{4}"

    match = re.search(date_pattern, text)

    if not match:
        return "", ""

    full_date = match.group(0)

    # 🔥 Remove weekday from beginning
    cleaned_date = re.sub(
        r"^(Mon|Tue|Wed|Thu|Fri|Sat|Sun)[a-z]*,?\s+",
        "",
        full_date
    )

    # EVERYTHING after the date = event name
    event_name = text.split(full_date, 1)[1].strip()

    return event_name, cleaned_date


# -----------------------
# SCRAPER
# -----------------------
def get_player_data(pdga_number):
    url = f"{BASE_URL}{pdga_number}"

    try:
        response = requests.get(url, timeout=10)
        soup = BeautifulSoup(response.text, "html.parser")

        # Player name
        name_tag = soup.find("h1")
        name = name_tag.text.strip() if name_tag else "Unknown"

        # Find correct <details> block
        details_blocks = soup.find_all("details")

        upcoming_text = None

        for d in details_blocks:
            summary = d.find("summary")
            summary_text = summary.text.lower() if summary else ""

            if "upcoming" in summary_text:
                upcoming_text = d.get_text(" ", strip=True)
                break

        if not upcoming_text:
            return {
                "PDGA": pdga_number,
                "Name": name,
                "Event": "None",
                "Date": ""
            }

        # Clean noise
        cleaned = upcoming_text.replace("Upcoming Events", "").strip()

        event_name, event_date = extract_event_and_date(cleaned)

        return {
            "PDGA": pdga_number,
            "Name": name,
            "Event": event_name,
            "Date": event_date
        }

    except Exception as e:
        return {
            "PDGA": pdga_number,
            "Name": "Error",
            "Event": str(e),
            "Date": ""
        }


# -----------------------
# RUNNER
# -----------------------
def run_scraper(numbers):
    results = []

    for n in numbers:
        results.append(get_player_data(n))
        time.sleep(0.4)

    return results


# -----------------------
# UI
# -----------------------
st.title("🥏 PDGA Next Event Finder")

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

    st.success("Done")
    st.dataframe(df)

    file = "pdga_events.xlsx"
    df.to_excel(file, index=False)

    with open(file, "rb") as f:
        st.download_button("Download Excel", f, file_name=file)