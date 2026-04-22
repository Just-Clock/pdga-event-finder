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

        # Upcoming events section
        upcoming = soup.find("div", {"id": "upcoming-events"})

        if not upcoming:
            return {
                "PDGA": pdga_number,
                "Name": name,
                "Next Event": "None",
                "Date": "",
                "Location": "",
                "Event Link": ""
            }

        rows = upcoming.find_all("tr")

        for row in rows[1:]:  # skip header
            cols = row.find_all("td")

            if len(cols) >= 3:
                event_name = cols[0].text.strip()
                event_date = cols[1].text.strip()
                location = cols[2].text.strip()

                link_tag = cols[0].find("a")
                event_link = (
                    "https://www.pdga.com" + link_tag["href"]
                    if link_tag else ""
                )

                return {
                    "PDGA": pdga_number,
                    "Name": name,
                    "Next Event": event_name,
                    "Date": event_date,
                    "Location": location,
                    "Event Link": event_link
                }

        return {
            "PDGA": pdga_number,
            "Name": name,
            "Next Event": "None",
            "Date": "",
            "Location": "",
            "Event Link": ""
        }

    except Exception as e:
        return {
            "PDGA": pdga_number,
            "Name": "Error",
            "Next Event": str(e),
            "Date": "",
            "Location": "",
            "Event Link": ""
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
            st.error("Please enter valid PDGA numbers.")            )