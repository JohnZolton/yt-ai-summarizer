import os
import json
import subprocess
import requests
from bs4 import BeautifulSoup
import whisper
from playwright.sync_api import sync_playwright
import yt_dlp
import whisper
from pathlib import Path
from datetime import datetime

# Configuration
JSON_FILE = "youtube-subscriptions.json"
DOWNLOAD_DIR = "audio_downloads"
WHISPER_MODEL = "base"  # Whisper model to use (base, medium, large, etc.)
BASE_YOUTUBE_URL = "https://www.youtube.com"


def load_file(file_path: str):
    # Path to your JSON subscription file
    try:
        with open(file_path, "r", encoding="utf-8") as file:
            youtube_subscriptions = json.load(file)
            return youtube_subscriptions
    
    except FileNotFoundError:
        print(f"The file '{file_path}' was not found.")
    except json.JSONDecodeError as e:
        print(f"Failed to decode JSON: {e}")
        
def check_channel_recent_videos(channel_id: str, channel_title: str):
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
        return video_data

def download_video(video_url: str, save_folder: str):
    youtube_download_opts = {
        'format': 'bestaudio/best',  # Get best quality audio
        'extractaudio': True,  # Extract audio
        'audioformat': 'mp3',  # Convert to mp3
        'outtmpl': f'{save_folder}/%(title)s.%(ext)s',  # Control save path
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
    }
    with yt_dlp.YoutubeDL(youtube_download_opts) as ydl:
        ydl.download([video_url])
            

def process_downloads(directory:str):
    audio_dir = Path(directory)
    
    if not audio_dir.exists():
        raise FileNotFoundError(f"Directory {directory} does not exist")
    
    # Create transcripts directory if it doesn't exist
    transcripts_dir = Path("transcripts")
    transcripts_dir.mkdir(exist_ok=True)

    audio_files = list(audio_dir.glob("*.mp3"))
    model = whisper.load_model("base")
    for audio_file in audio_files:
        print(f"transcribing: {audio_file}")
        transcript_file = transcripts_dir / f"{audio_file.stem}_transcript.json"
        
        try:
            result = model.transcribe(str(audio_file))
            transcript_data = {
                'filename': audio_file.name,
                'transcription_date': datetime.now().isoformat(),
                'text': result['text'],
            }
            with open(transcript_file, 'w', encoding='utf-8') as f:
                json.dump(transcript_data, f, ensure_ascii=False, indent=2)
        except Exception as e: 
            print(f"Error processing {audio_file.name}: {str(e)}")
        
        

data = load_file(JSON_FILE)

test_channel_id="UCTq1zHztiV69Ur8t6jco4CQ"
test_channel_name="S2 Underground"

save_folder = "audio_downloads"
#channel_videos = check_channel_recent_videos(channel_id=test_channel_id, channel_title=test_channel_name)

#os.makedirs(save_folder, exist_ok=True)  # Create the directory if it doesn't exist

#for video in channel_videos:
#    download_video(video_url=video['url'], save_folder=save_folder)

#process_downloads(directory=save_folder)
    

quit()
for subscription in data:
    channel_id = subscription["snippet"]["channelId"]
    channel_title = subscription["snippet"]["title"]
    print(f"checking channel: {channel_title}")

    recent_videos = fetch_recent_videos(channel_id)
    
    for video in recent_videos:
        print(f"found recent video: {video['title'] ({video['url']})}")

