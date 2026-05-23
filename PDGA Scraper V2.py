import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import re
import time
from datetime import datetime

BASE_URL = "https://www.pdga.com"
PLAYER_URL = "https://www.pdga.com/player/"

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}


# -----------------------
# NORMALIZE EVENT DATES
# -----------------------
def normalize_date(date_str):

    if not date_str:
        return None

    try:

        date_str = re.sub(
            r"^(Mon|Tue|Wed|Thu|Fri|Sat|Sun)[a-z]*,?\s+",
            "",
            date_str
        )

        # Convert ranges:
        # May 3–5, 2026 -> May 3, 2026
        date_str = re.sub(r"–\d{1,2}", "", date_str)

        # DD-MMM-YYYY
        if "-" in date_str and date_str.count("-") == 2:
            return datetime.strptime(
                date_str,
                "%d-%b-%Y"
            )

        # MM/DD/YYYY
        if "/" in date_str:
            return datetime.strptime(
                date_str,
                "%m/%d/%Y"
            )

        # Month DD, YYYY
        return datetime.strptime(
            date_str,
            "%B %d, %Y"
        )

    except:
        return None


# -----------------------
# SCRAPE DATE FROM EVENT PAGE
# -----------------------
def scrape_event_page(event_url):

    try:

        r = requests.get(
            event_url,
            headers=HEADERS,
            timeout=10
        )

        soup = BeautifulSoup(
            r.text,
            "html.parser"
        )

        page_text = soup.get_text(
            " ",
            strip=True
        )

        page_text = re.sub(
            r"\s+",
            " ",
            page_text
        )

        date_pattern = r"""(
            ((Mon|Tue|Wed|Thu|Fri|Sat|Sun)[a-z]*,?\s+)?
            (Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s\d{1,2}(?:–\d{1,2})?,\s\d{4}

            |

            \d{1,2}-[A-Za-z]{3}-\d{4}

            |

            \d{1,2}/\d{1,2}/\d{4}
        )"""

        match = re.search(
            date_pattern,
            page_text,
            re.VERBOSE
        )

        if not match:
            return None

        return normalize_date(
            match.group(0)
        )

    except:
        return None


# -----------------------
# GET EVENT LINKS
# Searches:
# 1) Now Playing
# 2) Upcoming Events
# -----------------------
def get_event_links(section):

    events = []

    links = section.find_all(
        "a",
        href=True
    )

    for link in links:

        href = link["href"]

        if (
            "/event/" not in href
            and
            "/tour/event/" not in href
        ):
            continue

        event_name = link.get_text(
            strip=True
        )

        event_url = BASE_URL + href

        events.append({
            "name": event_name,
            "url": event_url
        })

    return events


# -----------------------
# SCRAPE PLAYER
# -----------------------
def get_player_rows(pdga_number):

    url = f"{PLAYER_URL}{pdga_number}"

    rows = []

    try:

        r = requests.get(
            url,
            headers=HEADERS,
            timeout=10
        )

        soup = BeautifulSoup(
            r.text,
            "html.parser"
        )

        name_tag = soup.find("h1")

        player_name = (
            name_tag.text.strip()
            if name_tag
            else "Unknown"
        )

        sections = soup.find_all(
            "details"
        )

        all_events = []

        for section in sections:

            summary = section.find(
                "summary"
            )

            if not summary:
                continue

            title = summary.get_text(
                strip=True
            ).lower()

            if (
                "now playing" in title
                or
                "upcoming" in title
            ):

                all_events.extend(
                    get_event_links(section)
                )

        # Remove duplicates
        seen = set()

        unique_events = []

        for event in all_events:

            if event["url"] not in seen:

                seen.add(
                    event["url"]
                )

                unique_events.append(
                    event
                )

        # Visit each event page
        for event in unique_events:

            event_date = scrape_event_page(
                event["url"]
            )

            rows.append({
                "PDGA": pdga_number,
                "Name": player_name,
                "Date": event_date,
                "Event": event["name"],
                "Event URL": event["url"]
            })

            time.sleep(.3)

        if not rows:

            rows.append({
                "PDGA": pdga_number,
                "Name": player_name,
                "Date": None,
                "Event": "None Found",
                "Event URL": ""
            })

        return rows

    except Exception as e:

        return [{
            "PDGA": pdga_number,
            "Name": "Error",
            "Date": None,
            "Event": str(e),
            "Event URL": ""
        }]


# -----------------------
# RUN SCRAPER
# -----------------------
def run_scraper(numbers):

    all_rows = []

    for number in numbers:

        all_rows.extend(
            get_player_rows(number)
        )

    return all_rows


# -----------------------
# STREAMLIT UI
# -----------------------
st.title(
    "🥏 PDGA Event Tracker"
)

input_text = st.text_area(
    "Enter PDGA numbers (comma or newline separated)"
)

if st.button(
    "Fetch Events"
):

    numbers = [

        int(x.strip())

        for x in
        input_text
        .replace(",", "\n")
        .split()

        if x.strip().isdigit()

    ]

    with st.spinner(
        "Scraping player/event pages..."
    ):

        data = run_scraper(
            numbers
        )

        df = pd.DataFrame(
            data
        )

    # Sort
    df = df.sort_values(
        by="Date",
        ascending=True,
        na_position="last"
    )

    # Remove time component
    df["Date"] = pd.to_datetime(
        df["Date"],
        errors="coerce"
    ).dt.date

    st.success(
        f"Loaded {len(df)} rows"
    )

    st.dataframe(
        df,
        use_container_width=True
    )

    filename = "pdga_events.xlsx"

    df.to_excel(
        filename,
        index=False
    )

    with open(
        filename,
        "rb"
    ) as f:

        st.download_button(
            "📥 Download Excel",
            f,
            file_name=filename
        )