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


# =========================================================
# FIXED WATCHLIST (YOUR LIST)
# =========================================================
WATCHLIST = [
83596,231663,126098,299223,197269,220870,180280,207096,72628,294797,
253260,193824,275893,128316,241718,269038,87094,259842,95343,232260,
168353,244806,167837,181739,142155,146226,283063,242035,106118,167184,
83649,189511,194555,104226,308064,159762,75861,312238,295124,140354,
179839,132038,143853,103087,250811,269079,105496,83627,214778,111943,
145131,156926,282268,103627,258743,127864,180461,274791,106751
]


# =========================================================
# DATE PARSER
# =========================================================
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


# =========================================================
# EVENT SCRAPER
# =========================================================
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


# =========================================================
# PLAYER SCRAPER
# =========================================================
def get_player_rows(pdga_number):

    try:

        r = session.get(f"{PLAYER_URL}{pdga_number}", timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")

        name_tag = soup.find("h1")
        name = name_tag.text.strip() if name_tag else "Unknown"

        events = []

        # NOW PLAYING
        current = soup.find(class_="current-events")
        if current:
            for a in current.find_all("a", href=True):
                if "/event/" in a["href"] or "/tour/event/" in a["href"]:
                    events.append({
                        "name": a.get_text(strip=True),
                        "url": BASE_URL + a["href"],
                        "source": "Now Playing"
                    })

        # UPCOMING
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

        for e in unique:

            date = scrape_event_page(e["url"])

            rows.append({
                "PDGA": pdga_number,
                "Name": name,
                "Source": e["source"],
                "Date": date,
                "Event": e["name"],
                "Event URL": e["url"]
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


# =========================================================
# SCRAPER ENGINE
# =========================================================
def run_scraper(numbers):

    all_rows = []

    with ThreadPoolExecutor(max_workers=8) as ex:
        futures = [ex.submit(get_player_rows, n) for n in numbers]

        for f in as_completed(futures):
            all_rows += f.result()

    return all_rows


# =========================================================
# STREAMLIT UI
# =========================================================
st.title("🥏 PDGA Tracker")

# -------------------------
# FIXED WATCHLIST SECTION
# -------------------------
st.subheader("📌 Watchlist (Fixed Roster)")

if st.button("Run Watchlist Scrape"):

    with st.spinner("Scraping watchlist..."):

        df_watch = pd.DataFrame(run_scraper(WATCHLIST))

    df_watch["Date"] = pd.to_datetime(df_watch["Date"], errors="coerce").dt.date

    df_watch = df_watch.sort_values(by="Date", na_position="last")

    df_watch = df_watch[
        ["PDGA", "Name", "Source", "Date", "Event", "Event URL"]
    ]

    st.success(f"{len(df_watch)} watchlist rows loaded")

    st.dataframe(df_watch, use_container_width=True)


# -------------------------
# MANUAL SCRAPE TOOL (SEPARATE)
# -------------------------
st.subheader("🔎 Manual PDGA Lookup")

manual_input = st.text_area("Enter PDGA numbers (comma or newline separated)")

if st.button("Run Manual Scrape"):

    numbers = [
        int(x.strip())
        for x in manual_input.replace(",", "\n").split()
        if x.strip().isdigit()
    ]

    if numbers:

        with st.spinner("Scraping manual input..."):

            df_manual = pd.DataFrame(run_scraper(numbers))

        df_manual["Date"] = pd.to_datetime(df_manual["Date"], errors="coerce").dt.date

        df_manual = df_manual.sort_values(by="Date", na_position="last")

        df_manual = df_manual[
            ["PDGA", "Name", "Source", "Date", "Event", "Event URL"]
        ]

        st.success(f"{len(df_manual)} manual rows loaded")

        st.dataframe(df_manual, use_container_width=True)

    else:
        st.warning("No valid PDGA numbers entered")