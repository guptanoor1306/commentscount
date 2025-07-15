# File: app.py
import streamlit as st
from googleapiclient.discovery import build
import isodate

# Ensure you have your YouTube API key in Streamlit secrets:
# [secrets]
# YOUTUBE_API_KEY = "YOUR_API_KEY"

API_KEY = st.secrets["YOUTUBE_API_KEY"]

@st.cache_data(show_spinner=False)
def get_channel_id(url: str) -> str | None:
    """
    Extracts a channel ID from YouTube URLs.
    Supports:
      - /channel/CHANNEL_ID
      - /user/USERNAME
      - /c/CUSTOM_NAME
      - /@HANDLE
      - fallback search by last path segment
    """
    youtube = build("youtube", "v3", developerKey=API_KEY)
    # Standard channel links
    if "/channel/" in url:
        return url.split("/channel/")[1].split("/")[0]
    # Legacy username links
    if "/user/" in url:
        username = url.split("/user/")[1].split("/")[0]
        res = youtube.channels().list(part="id", forUsername=username).execute()
        items = res.get("items", [])
        return items[0]["id"] if items else None
    # Custom URL
    if "/c/" in url:
        custom = url.split("/c/")[1].split("/")[0]
        res = youtube.search().list(part="snippet", q=custom, type="channel", maxResults=1).execute()
        items = res.get("items", [])
        return items[0]["snippet"]["channelId"] if items else None
    # Handle URL
    if "/@" in url:
        handle = url.split("/@")[1].split("/")[0]
        # Search channels by handle text
        res = youtube.search().list(part="snippet", q=handle, type="channel", maxResults=1).execute()
        items = res.get("items", [])
        return items[0]["snippet"]["channelId"] if items else None
    # Fallback: search by last segment
    name = url.rstrip("/").split("/")[-1]
    res = youtube.search().list(part="snippet", q=name, type="channel", maxResults=1).execute()
    items = res.get("items", [])
    return items[0]["snippet"]["channelId"] if items else None

@st.cache_data(show_spinner=False)
def fetch_videos(channel_id: str) -> list[dict]:
    """
    Fetches all videos from a channel with ID `channel_id`.
    Returns list of {id, url, duration (sec), comments}.
    """
    youtube = build("youtube", "v3", developerKey=API_KEY)
    videos = []
    next_token = None
    while True:
        search_res = youtube.search().list(
            part="id",
            channelId=channel_id,
            maxResults=50,
            pageToken=next_token,
            order="date",
            type="video"
        ).execute()
        ids = [item["id"]["videoId"] for item in search_res.get("items", [])]
        if not ids:
            break
        details = youtube.videos().list(
            part="contentDetails,statistics",
            id=','.join(ids)
        ).execute()
        for d in details.get("items", []):
            duration = isodate.parse_duration(d["contentDetails"]["duration"]).total_seconds()
            comments = int(d.get("statistics", {}).get("commentCount", 0))
            videos.append({
                "id": d["id"],
                "url": f"https://www.youtube.com/watch?v={d['id']}",
                "duration": duration,
                "comments": comments
            })
        next_token = search_res.get("nextPageToken")
        if not next_token:
            break
    return videos

# Streamlit App UI
st.title("YouTube Channel Comment Sorter")

channel_url = st.text_input("YouTube Channel URL", placeholder="https://www.youtube.com/channel/... or /@handle or /c/name")
filter_option = st.selectbox(
    "Filter by content type",
    ["Both", "Videos (>3 mins)", "Shorts (<=3 mins)"]
)

if channel_url:
    channel_id = get_channel_id(channel_url)
    if not channel_id:
        st.error("Could not extract channel ID. Check URL format or API quotas.")
    else:
        with st.spinner("Fetching videos..."):
            all_videos = fetch_videos(channel_id)

        if filter_option == "Videos (>3 mins)":
            filtered = [v for v in all_videos if v["duration"] > 180]
        elif filter_option == "Shorts (<=3 mins)":
            filtered = [v for v in all_videos if v["duration"] <= 180]
        else:
            filtered = all_videos

        sorted_videos = sorted(filtered, key=lambda x: x["comments"], reverse=True)
        st.write(f"**Total found:** {len(sorted_videos)}")
        for vid in sorted_videos:
            mins = round(vid["duration"] / 60, 2)
            st.markdown(f"- [{vid['id']}]({vid['url']}) — Comments: **{vid['comments']}**, Duration: {mins} mins")
