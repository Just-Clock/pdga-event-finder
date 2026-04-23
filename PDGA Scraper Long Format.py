import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import re
import time
from datetime import datetime

BASE_URL = "https://www.pdga.com/player/"


# -----------------------
# EXTRACT MULTIPLE EVENTS (UPDATED)
# -----------------------
def extract_all_events(text):
    """
    More robust parser:
    - Splits text by dates
    - Pairs each date with following event text
    """

    date_pattern = r"""(
        # Weekday + Month format
        ((Mon|Tue|Wed|Thu|Fri|Sat|Sun)[a-z]*,?\s+)?
        (Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s\d{1,2}(?:–\d{1,2})?,\s\d{4}

        |

        # DD-MMM-YYYY
        \d{1,2}-[A-Za-z]{3}-\d{4}

        |

        # MM/DD/YYYY or M/D/YYYY
        \d{1,2}/\d{1,2}/\d{4}

        |

        # DD Mon YYYY (e.g., 15 Jul 2026)
        \d{1,2}\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s\d{4}
    )"""

    # Find all date matches
    matches = list(re.finditer(date_pattern, text, re.VERBOSE))

    if not matches:
        return []

    events = []

    # Split text into chunks starting at each date
    split_points = [m.start() for m in matches] + [len(text)]

    for i in range(len(matches)):
        start = split_points[i]
        end = split_points[i + 1]

        chunk = text[start:end].strip()

        # Extract date from start of chunk
        date_match = re.match(date_pattern, chunk, re.VERBOSE)
        if not date_match:
            continue

        full_date = date_match.group(0)

        # Clean date (remove weekday)
        cleaned_date = re.sub(
            r"^(Mon|Tue|Wed|Thu|Fri|Sat|Sun)[a-z]*,?\s+",
            "",
            full_date
        )

        # Remove date from chunk → remaining is event name
        event_name = chunk[len(full_date):].strip()

        # Clean junk prefixes
        event_name = re.sub(r"^[:\-\s]+", "", event_name)

        # 🔥 IMPORTANT: stop at next sentence-ish boundary
        event_name = re.split(r"\s{2,}|\.\s", event_name)[0].strip()

        events.append((cleaned_date, event_name))

    return events


# -----------------------
# NORMALIZE DATE (UPDATED)
# -----------------------
def normalize_date(date_str):
    try:
        date_str = re.sub(r"–\d{1,2}", "", date_str)

        # 12-Jul-2026
        if "-" in date_str and date_str.count("-") == 2:
            return datetime.strptime(date_str, "%d-%b-%Y")

        # 6/15/2026
        if "/" in date_str:
            return datetime.strptime(date_str, "%m/%d/%Y")

        # 15 Jul 2026
        if re.match(r"\d{1,2}\s+[A-Za-z]+", date_str):
            return datetime.strptime(date_str, "%d %b %Y")

        # May 3, 2026
        return datetime.strptime(date_str, "%B %d, %Y")

    except:
        return None


# -----------------------
# SCRAPE PLAYER
# -----------------------
def get_player_rows(pdga_number):
    url = f"{BASE_URL}{pdga_number}"
    rows = []

    try:
        response = requests.get(url, timeout=10)
        soup = BeautifulSoup(response.text, "html.parser")

        # Player name
        name_tag = soup.find("h1")
        name = name_tag.text.strip() if name_tag else "Unknown"

        # Find Upcoming Events section
        details_blocks = soup.find_all("details")

        upcoming_section = None
        for d in details_blocks:
            summary = d.find("summary")
            if summary and "upcoming" in summary.text.lower():
                upcoming_section = d
                break

        if not upcoming_section:
            return [{
                "PDGA": pdga_number,
                "Name": name,
                "Date": None,
                "Event": "None"
            }]

        # 🔥 Find all event links
        links = upcoming_section.find_all("a", href=True)

        for link in links:
            href = link["href"]

            # Only keep PDGA event links
            if "/event/" not in href and "/tour/event/" not in href:
                continue

            event_name = link.get_text(strip=True)

            # 🔍 Find surrounding text for date
            parent_text = link.parent.get_text(" ", strip=True)

            # Extract date from that chunk
            date_match = re.search(
                r"((Mon|Tue|Wed|Thu|Fri|Sat|Sun)[a-z]*,?\s+)?"
                r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s\d{1,2}(?:–\d{1,2})?,\s\d{4}"
                r"|"
                r"\d{1,2}-[A-Za-z]{3}-\d{4}"
                r"|"
                r"\d{1,2}/\d{1,2}/\d{4}",
                parent_text
            )

            date_str = date_match.group(0) if date_match else None

            rows.append({
                "PDGA": pdga_number,
                "Name": name,
                "Date": normalize_date(date_str) if date_str else None,
                "Event": event_name
            })

        return rows if rows else [{
            "PDGA": pdga_number,
            "Name": name,
            "Date": None,
            "Event": "None"
        }]

    except Exception as e:
        return [{
            "PDGA": pdga_number,
            "Name": "Error",
            "Date": None,
            "Event": str(e)
        }]


# -----------------------
# RUN SCRAPER
# -----------------------
def run_scraper(numbers):
    all_rows = []

    for n in numbers:
        all_rows.extend(get_player_rows(n))
        time.sleep(0.4)

    return all_rows


# -----------------------
# UI
# -----------------------
st.title("🥏 PDGA Event Tracker (Long Format)")

input_text = st.text_area("Enter PDGA numbers (comma or newline separated)")

if st.button("Fetch Events"):

    numbers = [
        int(x.strip())
        for x in input_text.replace(",", "\n").split()
        if x.strip().isdigit()
    ]

    with st.spinner("Scraping PDGA data..."):
        data = run_scraper(numbers)
        df = pd.DataFrame(data)

    # Sort by soonest upcoming
    df = df.sort_values(by="Date", ascending=True, na_position="last")

    # 🔥 CLEAN DISPLAY
    df["Date"] = df["Date"].dt.date

    st.success("Done!")
    st.dataframe(df)

    # Export to Excel
    file_name = "pdga_events.xlsx"
    df.to_excel(file_name, index=False)

    with open(file_name, "rb") as f:
        st.download_button("📥 Download Excel", f, file_name=file_name)