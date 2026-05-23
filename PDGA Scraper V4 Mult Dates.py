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
# DATE PARSER (SINGLE DATE ONLY)
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
# EVENT PAGE SCRAPER (SINGLE BEST DATE)
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
# CURRENT EVENTS
# -----------------------
def extract_current_events(soup):

    events = []

    section = soup.find(class_="current-events")

    if not section:
        return events

    for a in section.find_all("a", href=True):

        href = a["href"]

        if "/event/" not in href and "/tour/event/" not in href:
            continue

        events.append({
            "name": a.get_text(strip=True),
            "url": BASE_URL + href,
            "source": "Now Playing"
        })

    return events


# -----------------------
# UPCOMING EVENTS
# -----------------------
def extract_upcoming_events(soup):

    events = []

    for d in soup.find_all("details"):

        summary = d.find("summary")

        if not summary:
            continue

        if "upcoming" not in summary.get_text(strip=True).lower():
            continue

        for a in d.find_all("a", href=True):

            href = a["href"]

            if "/event/" not in href and "/tour/event/" not in href:
                continue

            events.append({
                "name": a.get_text(strip=True),
                "url": BASE_URL + href,
                "source": "Upcoming"
            })

    return events


# -----------------------
# PLAYER SCRAPER
# -----------------------
def get_player_rows(pdga_number):

    try:

        r = session.get(f"{PLAYER_URL}{pdga_number}", timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")

        name_tag = soup.find("h1")
        name = name_tag.text.strip() if name_tag else "Unknown"

        events = []
        events += extract_current_events(soup)
        events += extract_upcoming_events(soup)

        seen = set()
        unique = []

        for e in events:
            if e["url"] not in seen:
                seen.add(e["url"])
                unique.append(e)

        rows = []

        with ThreadPoolExecutor(max_workers=10) as ex:
            futures = [ex.submit(lambda e: (e, scrape_event_page(e["url"])), e) for e in unique]

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
# RUN SCRAPER
# -----------------------
def run_scraper(numbers):

    all_rows = []

    with ThreadPoolExecutor(max_workers=8) as ex:
        futures = [ex.submit(get_player_rows, n) for n in numbers]

        for f in as_completed(futures):
            all_rows += f.result()

    return all_rows


# -----------------------
# STREAMLIT UI + WATCHLIST
# -----------------------
st.title("🥏 PDGA Event Tracker")

# initialize watchlist
if "watchlist" not in st.session_state:
    st.session_state.watchlist = []


# add player
col1, col2 = st.columns([3, 1])

with col1:
    new_pdga = st.text_input("Add PDGA number")

with col2:
    if st.button("Add"):
        if new_pdga.isdigit():
            if int(new_pdga) not in st.session_state.watchlist:
                st.session_state.watchlist.append(int(new_pdga))


# show watchlist
st.subheader("Watchlist")

for n in st.session_state.watchlist:
    colA, colB = st.columns([4, 1])

    colA.write(str(n))

    if colB.button("Remove", key=str(n)):
        st.session_state.watchlist.remove(n)


# run scrape
if st.button("Fetch Events"):

    with st.spinner("Scraping PDGA..."):

        df = pd.DataFrame(run_scraper(st.session_state.watchlist))

    df["Date"] = pd.to_datetime(df["Date"], errors="coerce").dt.date

    df = df.sort_values(by="Date", na_position="last")

    df = df[
        [
            "PDGA",
            "Name",
            "Source",
            "Date",
            "Event",
            "Event URL"
        ]
    ]

    st.success(f"{len(df)} rows loaded")

    st.dataframe(df, use_container_width=True)

    df.to_excel("pdga_events.xlsx", index=False)

    with open("pdga_events.xlsx", "rb") as f:
        st.download_button("📥 Download Excel", f, file_name="pdga_events.xlsx")