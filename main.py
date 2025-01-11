import os
import json
import datetime
import subprocess
import requests
from bs4 import BeautifulSoup
import whisper
from playwright.sync_api import sync_playwright


# Configuration
JSON_FILE = "youtube-subscriptions.json"
DOWNLOAD_DIR = "downloads"  # Directory for downloaded videos
WHISPER_MODEL = "base"  # Whisper model to use (base, medium, large, etc.)
BASE_YOUTUBE_URL = "https://www.youtube.com"


def load_file(file_path: str):
    # Path to your JSON subscription file

    # Open and load the JSON file
    try:
        with open(file_path, "r", encoding="utf-8") as file:
            youtube_subscriptions = json.load(file)
            return youtube_subscriptions
    
    except FileNotFoundError:
        print(f"The file '{file_path}' was not found.")
    except json.JSONDecodeError as e:
        print(f"Failed to decode JSON: {e}")
        
def fetch_recent_videos(channel_id: str, channel_title: str):
    url = f"{BASE_YOUTUBE_URL}/channel/{channel_id}/videos"
    print(url)
    video_data = []
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url)
        
        page.wait_for_selector("ytd-rich-item-renderer", timeout=10000)
        
        video_blocks = page.query_selector_all("ytd-rich-item-renderer")
        
        for video_block in video_blocks:
            view_count_block = video_block.query_selector("span.inline-metadata-item.style-scope.ytd-video-meta-block")
            if not view_count_block: continue
            time_ago_tag = view_count_block.evaluate_handle("el => el.nextElementSibling")

            if not time_ago_tag:
                continue
            
            time_ago_text = time_ago_tag.inner_text().strip()

            if "hour" in time_ago_text or "minute" in time_ago_text:
                title_tag = video_block.query_selector("a#video-title-link")
                if not title_tag:
                    continue
                
                video_title = title_tag.get_attribute("title")
                video_url = f"{BASE_YOUTUBE_URL}{title_tag.get_attribute('href')}"
                video_data.append({"title": video_title, "url": video_url, "time_ago": time_ago_text})
        browser.close()
        print(video_data)
            

data = load_file(JSON_FILE)
videos_to_download = []

test_channel_id="UCTq1zHztiV69Ur8t6jco4CQ"
test_channel_name="S2 Underground"

fetch_recent_videos(channel_id=test_channel_id, channel_title=test_channel_name)

quit()
for subscription in data:
    channel_id = subscription["snippet"]["channelId"]
    channel_title = subscription["snippet"]["title"]
    print(f"checking channel: {channel_title}")

    recent_videos = fetch_recent_videos(channel_id)
    
    for video in recent_videos:
        print(f"found recent video: {video['title'] ({video['url']})}")

