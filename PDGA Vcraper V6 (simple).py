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

WATCHLIST = [
83596,231663,126098,299223,197269,220870,180280,207096,72628,294797,
253260,193824,275893,128316,241718,269038,87094,259842,95343,232260,
168353,244806,167837,181739,142155,146226,283063,242035,106118,167184,
83649,189511,194555,104226,308064,159762,75861,312238,295124,140354,
179839,132038,143853,103087,250811,269079,105496,83627,214778,111943,
145131,156926,282268,103627,258743,127864,180461,274791,106751,209741,
]


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
            timeout=20
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

    events = []

    for section in soup.find_all("details"):

        summary = section.find("summary")

        if not summary:
            continue

        title = summary.get_text(
            " ",
            strip=True
        ).lower()

        if not any(
            phrase in title
            for phrase in [
                "upcoming",
                "next event"
            ]
        ):
            continue

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

            events.append({

                "name":
                link.get_text(
                    strip=True
                ),

                "url":
                BASE_URL + href,

                "source":
                "Upcoming"

            })

    return events

# -----------------------
# NEXT EVENT (fallback)
# -----------------------

def extract_next_event(soup):

    events = []

    next_text = soup.find(
        string=lambda s:
        s and "next event" in s.lower()
    )

    if not next_text:
        return events

    node = next_text.parent

    for link in node.find_all_next(
        "a",
        href=True
    ):

        href = link["href"]

        if (
            "/event/" in href
            or "/tour/event/" in href
        ):

            events.append({

                "name":
                link.get_text(
                    strip=True
                ),

                "url":
                BASE_URL + href,

                "source":
                "Next Event"

            })

            break

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
            timeout=20
        )

        if response.status_code != 200:
            return [{
                "PDGA": pdga_number,
                "Name": "HTTP Error",
                "Source": "",
                "Date": None,
                "Event": f"Status {response.status_code}",
                "Event URL": ""
            }]

        soup=BeautifulSoup(
            response.text,
            "html.parser"
        )

        name_tag = soup.find("h1")

        if not name_tag:
            name_tag = soup.select_one(
                ".page-title"
            )

        if not name_tag:
            name_tag = soup.find(
                attrs={"property": "schema:name"}
            )

        player_name = (
            name_tag.get_text(
                " ",
                strip=True
            )
            if name_tag
            else "Unknown"
        )

        all_events = []

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

        # Pull "Next event" blocks
        all_events.extend(
            extract_next_event(
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

    all_rows = []

    progress = st.progress(0)

    total = len(numbers)

    for idx, n in enumerate(numbers):

        all_rows.extend(
            get_player_rows(n)
        )

        progress.progress(
            (idx + 1) / total
        )

    progress.empty()

    return all_rows


# -----------------------
# STREAMLIT UI
# -----------------------

st.title("🥏 PDGA Event Tracker")


# =====================================================
# WATCHLIST SECTION
# =====================================================

st.header("📌 Watchlist")

watchlist_df = pd.DataFrame({
    "PDGA": WATCHLIST
})

csv_data = watchlist_df.to_csv(
    index=False
)

st.download_button(
    "📄 Export Watchlist CSV",
    csv_data,
    file_name="watchlist.csv",
    mime="text/csv"
)

if st.button(
    "Run Watchlist Scrape"
):

    with st.spinner(
        "Scraping watchlist..."
    ):

        data = run_scraper(
            WATCHLIST
        )

        df = pd.DataFrame(
            data
        )

    df["Date"] = pd.to_datetime(
        df["Date"],
        errors="coerce"
    ).dt.date

    df = df.sort_values(
        by="Date",
        ascending=True,
        na_position="last"
    )

    st.success(
        f"{len(df)} rows loaded"
    )

    st.dataframe(
        df,
        use_container_width=True
    )

    filename = "watchlist_events.xlsx"

    df.to_excel(
        filename,
        index=False
    )

    with open(
        filename,
        "rb"
    ) as f:

        st.download_button(
            "📥 Download Watchlist Excel",
            f,
            file_name=filename
        )


st.divider()


# =====================================================
# MANUAL LOOKUP SECTION
# =====================================================

st.header("🔎 Manual Lookup")

input_text = st.text_area(
    "Enter PDGA numbers (comma or newline separated)"
)

if st.button(
    "Run Manual Scrape"
):

    numbers = [

        int(x.strip())

        for x in
        input_text
        .replace(",", "\n")
        .split()

        if x.strip().isdigit()

    ]

    if not numbers:

        st.warning(
            "Please enter at least one PDGA number."
        )

    else:

        with st.spinner(
            "Scraping PDGA..."
        ):

            data = run_scraper(
                numbers
            )

            df = pd.DataFrame(
                data
            )

        df["Date"] = pd.to_datetime(
            df["Date"],
            errors="coerce"
        ).dt.date

        df = df.sort_values(
            by="Date",
            ascending=True,
            na_position="last"
        )

        st.success(
            f"{len(df)} rows loaded"
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