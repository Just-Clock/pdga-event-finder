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
# DATE NORMALIZATION
# -----------------------

def normalize_date(date_str):

    if not date_str:
        return None

    try:

        # Remove weekday if present
        date_str = re.sub(
            r"^(Mon|Tue|Wed|Thu|Fri|Sat|Sun)[a-z]*,?\s+",
            "",
            date_str
        )

        # Convert:
        # May 3–5,2026 -> May 3,2026
        date_str = re.sub(
            r"–\d{1,2}",
            "",
            date_str
        )

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
# SCRAPE EVENT PAGE
# -----------------------

def scrape_event_page(event_url):

    try:

        response = requests.get(
            event_url,
            headers=HEADERS,
            timeout=10
        )

        soup = BeautifulSoup(
            response.text,
            "html.parser"
        )

        text = soup.get_text(
            " ",
            strip=True
        )

        text = re.sub(
            r"\s+",
            " ",
            text
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
            text,
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
# CURRENT EVENTS
# -----------------------

def extract_current_events(soup):

    events = []

    current_section = soup.find(
        class_="current-events"
    )

    if not current_section:
        return events

    links = current_section.find_all(
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

        events.append({

            "name":
            link.get_text(
                strip=True
            ),

            "url":
            BASE_URL + href,

            "source":
            "Now Playing"

        })

    return events


# -----------------------
# UPCOMING EVENTS
# -----------------------

def extract_upcoming_events(soup):

    events=[]

    for section in soup.find_all(
        "details"
    ):

        summary=section.find(
            "summary"
        )

        if not summary:
            continue

        title=summary.get_text(
            strip=True
        ).lower()

        if "upcoming" not in title:
            continue

        links=section.find_all(
            "a",
            href=True
        )

        for link in links:

            href=link["href"]

            if (
                "/event/" not in href
                and
                "/tour/event/" not in href
            ):
                continue

            events.append({

                "name":
                link.get_text(
                    strip=True
                ),

                "url":
                BASE_URL+href,

                "source":
                "Upcoming"

            })

    return events


# -----------------------
# PLAYER SCRAPER
# -----------------------

def get_player_rows(pdga_number):

    rows=[]

    try:

        response=requests.get(
            f"{PLAYER_URL}{pdga_number}",
            headers=HEADERS,
            timeout=10
        )

        soup=BeautifulSoup(
            response.text,
            "html.parser"
        )

        name_tag=soup.find("h1")

        player_name=(
            name_tag.text.strip()
            if name_tag
            else "Unknown"
        )

        all_events=[]

        # Pull current events
        all_events.extend(
            extract_current_events(
                soup
            )
        )

        # Pull upcoming events
        all_events.extend(
            extract_upcoming_events(
                soup
            )
        )

        # Remove duplicates
        unique=[]
        seen=set()

        for event in all_events:

            if event["url"] in seen:
                continue

            seen.add(
                event["url"]
            )

            unique.append(
                event
            )

        # Visit event pages
        for event in unique:

            event_date=scrape_event_page(
                event["url"]
            )

            rows.append({

                "PDGA":
                pdga_number,

                "Name":
                player_name,

                "Source":
                event["source"],

                "Date":
                event_date,

                "Event":
                event["name"],

                "Event URL":
                event["url"]

            })

            time.sleep(.25)

        if not rows:

            rows.append({

                "PDGA":
                pdga_number,

                "Name":
                player_name,

                "Source":
                "",

                "Date":
                None,

                "Event":
                "No events found",

                "Event URL":
                ""

            })

        return rows

    except Exception as e:

        return [{

            "PDGA":
            pdga_number,

            "Name":
            "Error",

            "Source":
            "",

            "Date":
            None,

            "Event":
            str(e),

            "Event URL":
            ""

        }]


# -----------------------
# RUN SCRAPER
# -----------------------

def run_scraper(numbers):

    all_rows=[]

    for n in numbers:

        all_rows.extend(
            get_player_rows(n)
        )

    return all_rows


# -----------------------
# STREAMLIT UI
# -----------------------

st.title(
    "🥏 PDGA Event Tracker"
)

input_text=st.text_area(
    "Enter PDGA numbers (comma or newline separated)"
)

if st.button(
    "Fetch Events"
):

    numbers=[

        int(x.strip())

        for x in
        input_text
        .replace(",", "\n")
        .split()

        if x.strip().isdigit()

    ]

    with st.spinner(
        "Scraping PDGA..."
    ):

        data=run_scraper(
            numbers
        )

        df=pd.DataFrame(
            data
        )

    df=df.sort_values(
        by="Date",
        ascending=True,
        na_position="last"
    )

    # remove time portion
    df["Date"]=pd.to_datetime(
        df["Date"],
        errors="coerce"
    ).dt.date

    st.success(
        f"{len(df)} rows loaded"
    )

    st.dataframe(
        df,
        use_container_width=True
    )

    filename="pdga_events.xlsx"

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