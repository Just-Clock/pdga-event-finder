import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import re
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE_URL = "https://www.pdga.com"
PLAYER_URL = "https://www.pdga.com/player/"

session = requests.Session()
session.headers.update({"User-Agent": "Mozilla/5.0"})


# -----------------------
# DATE PARSER
# -----------------------
def parse_date(raw):

    if not raw:
        return None

    try:
        raw = re.sub(r"^(Mon|Tue|Wed|Thu|Fri|Sat|Sun)[a-z]*,?\s+", "", raw)
        raw = re.sub(r"–\d{1,2}", "", raw)

        if "-" in raw and raw.count("-") == 2:
            return datetime.strptime(raw, "%d-%b-%Y")

        if "/" in raw:
            return datetime.strptime(raw, "%m/%d/%Y")

        return datetime.strptime(raw, "%B %d, %Y")

    except:
        return None


# -----------------------
# EVENT SCRAPER
# -----------------------
def scrape_event_page(url):

    try:

        r = session.get(url, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")

        text = soup.get_text(" ", strip=True)
        text = re.sub(r"\s+", " ", text)

        pattern = r"""
            (?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)?\s*
            (?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s\d{1,2}(?:–\d{1,2})?,\s\d{4}
            |
            \d{1,2}-[A-Za-z]{3}-\d{4}
            |
            \d{1,2}/\d{1,2}/\d{4}
        """

        match = re.search(pattern, text, re.VERBOSE)

        if not match:
            return None

        return parse_date(match.group(0))

    except:
        return None


# -----------------------
# PLAYER PAGE SCRAPER
# -----------------------
def get_player_rows(pdga_number):

    try:

        r = session.get(f"{PLAYER_URL}{pdga_number}", timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")

        name_tag = soup.find("h1")
        name = name_tag.text.strip() if name_tag else "Unknown"

        events = []

        # now playing
        current = soup.find(class_="current-events")
        if current:
            for a in current.find_all("a", href=True):
                if "/event/" in a["href"] or "/tour/event/" in a["href"]:
                    events.append({
                        "name": a.get_text(strip=True),
                        "url": BASE_URL + a["href"],
                        "source": "Now Playing"
                    })

        # upcoming
        for d in soup.find_all("details"):
            summary = d.find("summary")
            if summary and "upcoming" in summary.get_text(strip=True).lower():

                for a in d.find_all("a", href=True):
                    if "/event/" in a["href"] or "/tour/event/" in a["href"]:
                        events.append({
                            "name": a.get_text(strip=True),
                            "url": BASE_URL + a["href"],
                            "source": "Upcoming"
                        })

        # dedupe
        seen = set()
        unique = []

        for e in events:
            if e["url"] not in seen:
                seen.add(e["url"])
                unique.append(e)

        rows = []

        with ThreadPoolExecutor(max_workers=10) as ex:
            futures = [
                ex.submit(lambda e: (e, scrape_event_page(e["url"])), e)
                for e in unique
            ]

            for f in as_completed(futures):

                event, date = f.result()

                rows.append({
                    "PDGA": pdga_number,
                    "Name": name,
                    "Source": event["source"],
                    "Date": date,
                    "Event": event["name"],
                    "Event URL": event["url"]
                })

        return rows

    except Exception as e:

        return [{
            "PDGA": pdga_number,
            "Name": "Error",
            "Source": "",
            "Date": None,
            "Event": str(e),
            "Event URL": ""
        }]


# -----------------------
# SCRAPER WRAPPER (PURE)
# -----------------------
def run_scraper(pdga_list):

    all_rows = []

    with ThreadPoolExecutor(max_workers=8) as ex:
        futures = [ex.submit(get_player_rows, n) for n in pdga_list]

        for f in as_completed(futures):
            all_rows += f.result()

    return all_rows


# -----------------------
# STREAMLIT UI (WATCHLIST SEPARATED)
# -----------------------
st.title("🥏 PDGA Event Tracker")

# init watchlist ONLY
if "watchlist" not in st.session_state:
    st.session_state.watchlist = []


# -----------------------
# ADD TO WATCHLIST
# -----------------------
col1, col2 = st.columns([3, 1])

with col1:
    pdga_input = st.text_input("Add PDGA number")

with col2:
    if st.button("Add"):
        if pdga_input.isdigit():
            n = int(pdga_input)
            if n not in st.session_state.watchlist:
                st.session_state.watchlist.append(n)


# -----------------------
# SHOW WATCHLIST (NO SCRAPING HERE)
# -----------------------
st.subheader("Watchlist")

for n in st.session_state.watchlist:
    colA, colB = st.columns([4, 1])

    colA.write(str(n))

    if colB.button("Remove", key=f"rm_{n}"):
        st.session_state.watchlist.remove(n)
        st.rerun()


# -----------------------
# RUN SCRAPER ONLY ON DEMAND
# -----------------------
if st.button("Fetch Events"):

    if not st.session_state.watchlist:
        st.warning("Add PDGA numbers first")
        st.stop()

    with st.spinner("Scraping PDGA..."):

        df = pd.DataFrame(run_scraper(st.session_state.watchlist))

    df["Date"] = pd.to_datetime(df["Date"], errors="coerce").dt.date

    df = df.sort_values(by="Date", na_position="last")

    df = df[
        ["PDGA", "Name", "Source", "Date", "Event", "Event URL"]
    ]

    st.success(f"{len(df)} rows loaded")

    st.dataframe(df, use_container_width=True)

    df.to_excel("pdga_events.xlsx", index=False)

    with open("pdga_events.xlsx", "rb") as f:
        st.download_button(
            "📥 Download Excel",
            f,
            file_name="pdga_events.xlsx"
        )