import requests
from bs4 import BeautifulSoup
import pandas as pd
import streamlit as st
import time

BASE_URL = "https://www.pdga.com/player/"


def get_player_data(pdga_number):
    url = f"{BASE_URL}{pdga_number}"

    try:
        response = requests.get(url, timeout=10)
        soup = BeautifulSoup(response.text, "html.parser")

        name_tag = soup.find("h1")
        name = name_tag.text.strip() if name_tag else "Unknown"

        upcoming_section = soup.find("div", {"id": "upcoming-events"})

        if not upcoming_section:
            return {
                "PDGA": pdga_number,
                "Name": name,
                "Next Event": "None",
                "Date": "",
                "Location": ""
            }

        rows = upcoming_section.find_all("tr")

        for row in rows[1:]:
            cols = row.find_all("td")
            if len(cols) >= 3:
                return {
                    "PDGA": pdga_number,
                    "Name": name,
                    "Next Event": cols[0].text.strip(),
                    "Date": cols[1].text.strip(),
                    "Location": cols[2].text.strip()
                }

        return {
            "PDGA": pdga_number,
            "Name": name,
            "Next Event": "None",
            "Date": "",
            "Location": ""
        }

    except Exception as e:
        return {"PDGA": pdga_number, "Error": str(e)}


def run_scraper(pdga_numbers):
    results = []
    for num in pdga_numbers:
        data = get_player_data(num)
        results.append(data)
        time.sleep(0.5)
    return results


# 🌐 UI
st.title("🥏 PDGA Next Event Finder")

st.write("Paste PDGA numbers (comma or new line separated)")

input_text = st.text_area("PDGA Numbers")

if st.button("Find Events"):
    if input_text.strip():
        numbers = [
            int(x.strip())
            for x in input_text.replace(",", "\n").split()
        ]

        with st.spinner("Fetching data..."):
            data = run_scraper(numbers)
            df = pd.DataFrame(data)

        st.success("Done!")
        st.dataframe(df)

        excel_file = "pdga_events.xlsx"
        df.to_excel(excel_file, index=False)

        with open(excel_file, "rb") as f:
            st.download_button(
                "Download Excel",
                f,
                file_name="pdga_events.xlsx"
            )