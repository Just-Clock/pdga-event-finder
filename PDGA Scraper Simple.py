import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import time

BASE_URL = "https://www.pdga.com/player/"


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

        # Find <details> with "Upcoming"
        details_sections = soup.find_all("details")

        upcoming_text = None
        for d in details_sections:
            title_attr = d.get("title", "")

            # Check both title and summary text
            summary = d.find("summary")
            summary_text = summary.text if summary else ""

            if "upcoming" in title_attr.lower() or "upcoming" in summary_text.lower():
                upcoming_text = d.get_text(" ", strip=True)
                break

        if not upcoming_text:
            return {
                "PDGA": pdga_number,
                "Name": name,
                "Next Event": "None",
                "Date": "",
                "Location": ""
            }

        # Clean up text (remove "Upcoming Events" label)
        cleaned = upcoming_text.replace("Upcoming Events", "").strip()

        # Try to split event + date (basic heuristic)
        # Example: "John is registered for the Spring Classic (May 3–5)"
        event_name = cleaned
        event_date = ""

        if "(" in cleaned and ")" in cleaned:
            event_name = cleaned.split("(")[0].strip()
            event_date = cleaned.split("(")[1].replace(")", "").strip()

        return {
            "PDGA": pdga_number,
            "Name": name,
            "Next Event": event_name,
            "Date": event_date,
            "Location": ""
        }

    except Exception as e:
        return {
            "PDGA": pdga_number,
            "Name": "Error",
            "Next Event": str(e),
            "Date": "",
            "Location": ""
        }


def run_scraper(pdga_numbers):
    results = []

    for num in pdga_numbers:
        results.append(get_player_data(num))
        time.sleep(0.5)  # be nice to PDGA servers

    return results


# -----------------------
# UI
# -----------------------
st.title("🥏 PDGA Next Event Finder")

st.write("Paste PDGA numbers (comma or newline separated)")

input_text = st.text_area("PDGA Numbers")

if st.button("Find Events"):
    if input_text.strip():
        try:
            numbers = [
                int(x.strip())
                for x in input_text.replace(",", "\n").split()
            ]

            with st.spinner("Fetching events..."):
                data = run_scraper(numbers)
                df = pd.DataFrame(data)

            st.success("Done!")
            st.dataframe(df)

            # Excel download
            file_name = "pdga_events.xlsx"
            df.to_excel(file_name, index=False)

            with open(file_name, "rb") as f:
                st.download_button(
                    "📥 Download Excel",
                    f,
                    file_name=file_name
                )

        except:
            st.error("Please enter valid PDGA numbers.")
