import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import re
import time

BASE_URL = "https://www.pdga.com/player/"


# -----------------------
# PARSER
# -----------------------
def parse_event_text(text):
    """
    Extract:
    - Event Name
    - Start Date (single date or range collapsed to one)
    """

    # Pull text inside parentheses
    match = re.search(r"\((.*?)\)", text)

    if not match:
        return text.strip(), ""

    date_part = match.group(1).strip()

    # Event name is everything before "("
    event_name = text.split("(")[0].strip()

    return event_name, date_part


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

        # Find correct <details> section
        details_sections = soup.find_all("details")

        upcoming_text = None

        for d in details_sections:
            title_attr = d.get("title", "")
            summary = d.find("summary")
            summary_text = summary.text if summary else ""

            if "upcoming" in title_attr.lower() or "upcoming" in summary_text.lower():
                upcoming_text = d.get_text(" ", strip=True)
                break

        if not upcoming_text:
            return {
                "PDGA": pdga_number,
                "Name": name,
                "Event": "None",
                "Date": ""
            }

        # Clean label text
        cleaned = upcoming_text.replace("Upcoming Events", "").strip()

        event_name, event_date = parse_event_text(cleaned)

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
def run_scraper(pdga_numbers):
    results = []

    for num in pdga_numbers:
        results.append(get_player_data(num))
        time.sleep(0.5)  # be polite to PDGA servers

    return results


# -----------------------
# UI
# -----------------------
st.title("🥏 PDGA Next Event Finder (Simple)")

st.write("Enter PDGA numbers separated by commas or new lines")

input_text = st.text_area("PDGA Numbers")

if st.button("Find Events"):
    if input_text.strip():

        try:
            numbers = [
                int(x.strip())
                for x in input_text.replace(",", "\n").split()
                if x.strip().isdigit()
            ]

            with st.spinner("Fetching PDGA data..."):
                data = run_scraper(numbers)
                df = pd.DataFrame(data)

            st.success("Done!")
            st.dataframe(df)

            # Excel export
            file_name = "pdga_events.xlsx"
            df.to_excel(file_name, index=False)

            with open(file_name, "rb") as f:
                st.download_button(
                    "📥 Download Excel",
                    f,
                    file_name=file_name
                )

        except Exception as e:
            st.error(f"Error: {e}")