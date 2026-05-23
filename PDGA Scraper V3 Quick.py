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
# PARSE DATE STRINGS
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
# SCRAPE EVENT PAGE
# (returns START + END)
# -----------------------
def scrape_event_page(url):

    try:

        r = session.get(url, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")

        text = soup.get_text(" ", strip=True)
        text = re.sub(r"\s+", " ", text)

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

        matches = re.findall(date_pattern, text, re.VERBOSE)

        dates = []

        for m in matches:

            raw = m[0] if isinstance(m, tuple) else m
            dt = parse_date(raw)

            if dt:
                dates.append(dt)

        if not dates:
            return None, None

        return min(dates), max(dates)

    except:
        return None, None


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
# PROCESS EVENT (PARALLEL)
# -----------------------
def process_event(event):

    start, end = scrape_event_page(event["url"])

    event["Start Date"] = start
    event["End Date"] = end

    return event


# -----------------------
# PLAYER SCRAPER
# -----------------------
def get_player_rows(pdga_number):

    rows = []

    try:

        r = session.get(f"{PLAYER_URL}{pdga_number}", timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")

        name_tag = soup.find("h1")
        name = name_tag.text.strip() if name_tag else "Unknown"

        all_events = []
        all_events += extract_current_events(soup)
        all_events += extract_upcoming_events(soup)

        # dedupe
        seen = set()
        unique = []

        for e in all_events:
            if e["url"] not in seen:
                seen.add(e["url"])
                unique.append(e)

        # parallel event scraping
        with ThreadPoolExecutor(max_workers=10) as ex:

            futures = [ex.submit(process_event, e) for e in unique]

            for f in as_completed(futures):

                e = f.result()

                rows.append({
                    "PDGA": pdga_number,
                    "Name": name,
                    "Source": e["source"],
                    "Event": e["name"],
                    "Event URL": e["url"],
                    "Start Date": e["Start Date"],
                    "End Date": e["End Date"]
                })

        return rows

    except Exception as e:

        return [{
            "PDGA": pdga_number,
            "Name": "Error",
            "Source": "",
            "Event": str(e),
            "Event URL": "",
            "Start Date": None,
            "End Date": None
        }]


# -----------------------
# RUN ALL PLAYERS (PARALLEL)
# -----------------------
def run_scraper(numbers):

    all_rows = []

    with ThreadPoolExecutor(max_workers=8) as ex:

        futures = [ex.submit(get_player_rows, n) for n in numbers]

        for f in as_completed(futures):
            all_rows += f.result()

    return all_rows


# -----------------------
# UI
# -----------------------
st.title("🥏 PDGA Event Tracker (Parallel + Date Range)")

input_text = st.text_area("Enter PDGA numbers")

if st.button("Fetch Events"):

    numbers = [
        int(x.strip())
        for x in input_text.replace(",", "\n").split()
        if x.strip().isdigit()
    ]

    with st.spinner("Scraping..."):

        df = pd.DataFrame(run_scraper(numbers))

    # format dates
    df["Start Date"] = pd.to_datetime(df["Start Date"], errors="coerce").dt.date
    df["End Date"] = pd.to_datetime(df["End Date"], errors="coerce").dt.date

    # sort by start date
    df = df.sort_values(by="Start Date", na_position="last")

    st.success(f"{len(df)} rows loaded")

    st.dataframe(df, use_container_width=True)

    df.to_excel("pdga_events.xlsx", index=False)

    with open("pdga_events.xlsx", "rb") as f:
        st.download_button(
            "📥 Download Excel",
            f,
            file_name="pdga_events.xlsx"
        )