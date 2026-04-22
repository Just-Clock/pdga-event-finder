import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import httpx
import asyncio
from supabase import create_client

# -----------------------
# CONFIG
# -----------------------
SUPABASE_URL = "https://nalaynrnhvjfupvcplvo.supabase.co"
SUPABASE_KEY = "sb_publishable_5r5rJLYBJ9L8r6p2UVp93w_7u1XroMn"

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

BASE_URL = "https://www.pdga.com/player/"

# -----------------------
# AUTH (simple user ID)
# -----------------------
user_id = st.text_input("Enter your username (simple login)")


# -----------------------
# DATABASE FUNCTIONS
# -----------------------
def get_watchlist():
    res = supabase.table("watchlists").select("*").eq("user_id", user_id).execute()
    return [r["pdga_number"] for r in res.data]


def add_player(num):
    supabase.table("watchlists").insert({
        "user_id": user_id,
        "pdga_number": num
    }).execute()


def remove_player(num):
    supabase.table("watchlists").delete().eq("user_id", user_id).eq("pdga_number", num).execute()


# -----------------------
# FAST SCRAPER (ASYNC)
# -----------------------
async def fetch_player(client, pdga_number):
    url = f"{BASE_URL}{pdga_number}"

    try:
        r = await client.get(url, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")

        name = soup.find("h1").text.strip()

        upcoming = soup.find("div", {"id": "upcoming-events"})

        if not upcoming:
            return [pdga_number, name, "None", "", "", ""]

        row = upcoming.find_all("tr")[1]
        cols = row.find_all("td")

        link = cols[0].find("a")["href"] if cols[0].find("a") else ""

        return [
            pdga_number,
            name,
            cols[0].text.strip(),
            cols[1].text.strip(),
            cols[2].text.strip(),
            f"https://www.pdga.com{link}"
        ]

    except:
        return [pdga_number, "Error", "", "", "", ""]


async def run_async(pdga_numbers):
    async with httpx.AsyncClient() as client:
        tasks = [fetch_player(client, n) for n in pdga_numbers]
        return await asyncio.gather(*tasks)


# -----------------------
# UI
# -----------------------
st.title("🥏 PDGA Tracker Pro")

if user_id:
    watchlist = get_watchlist()

    st.subheader("📋 Your Watchlist")
    st.write(watchlist)

    new_player = st.text_input("Add Player")

    if st.button("Add"):
        if new_player.isdigit():
            add_player(int(new_player))
            st.rerun()

    remove = st.text_input("Remove Player")

    if st.button("Remove"):
        if remove.isdigit():
            remove_player(int(remove))
            st.rerun()

    if st.button("Check Events"):
        if watchlist:
            with st.spinner("Fast scraping..."):
                data = asyncio.run(run_async(watchlist))

                df = pd.DataFrame(data, columns=[
                    "PDGA", "Name", "Event", "Date", "Location", "Link"
                ])

            st.dataframe(df)

            excel = "events.xlsx"
            df.to_excel(excel, index=False)

            with open(excel, "rb") as f:
                st.download_button("Download Excel", f)

            # SHARE LINK
            share_url = f"?watchlist={','.join(map(str, watchlist))}"
            st.write("🔗 Share this:", share_url)

# SHARE MODE
params = st.query_params
if "watchlist" in params:
    numbers = [int(x) for x in params["watchlist"].split(",")]

    st.subheader("📡 Shared Watchlist")

    data = asyncio.run(run_async(numbers))
    df = pd.DataFrame(data, columns=[
        "PDGA", "Name", "Event", "Date", "Location", "Link"
    ])

    st.dataframe(df)