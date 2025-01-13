import os
import json
import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
import yt_dlp
import whisper
from pathlib import Path
from datetime import datetime
from anthropic import AnthropicBedrock
from dotenv import load_dotenv
from anthropic.types import ToolParam, MessageParam
import argparse



def load_json_file(file_path: str):
    # Path to your JSON subscription file
    try:
        with open(file_path, "r", encoding="utf-8") as file:
            youtube_subscriptions = json.load(file)
            return youtube_subscriptions
    
    except FileNotFoundError:
        print(f"The file '{file_path}' was not found.")
    except json.JSONDecodeError as e:
        print(f"Failed to decode JSON: {e}")
        
def check_channel_recent_videos(channel_id: str, channel_title: str, youtube_url:str):
    url = f"{youtube_url}/channel/{channel_id}/videos"
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
            

def transcribe_downloads(directory:str):
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
        
        


def summarize_transcript(transcript_text: str, client):
    model_name=os.getenv("BEDROCK_AWS_MODEL")

    user_prompt=f"Summarize this transcript, highlight any key details. \n\n transcript: {transcript_text}"
    
    """
    user_prompt=f"get a summary of this document, use available tools if necessary: {video_text}"
    tools: list[ToolParam] = [
        {
            "name": "summarize_document",
            "description": "provides an accurate and detailed summary of text",
            "input_schema": {
                "type": "object",
                "properties": {"text": {"type": "string", "description": "the text to summarize"}},
            }
        }
    ]
    """
    """ # Model tried to call the tool AND regenerate the entire input text in the tool call, replaced with above to just output a call-tool flag
    tools: list[ToolParam] = [
        {
            "name": "summarize_document",
            "description": "provides an accurate and detailed summary of text",
            "input_schema": {
                "type": "object",
                "properties": {"call": {"type": "boolean", "description": "decision to call summarize_document"}},
            }
        }
    ]

    """

    message = client.messages.create(
        max_tokens=1024,
        messages = [
            {
                "role": "user",
                "content": user_prompt
            }
        ],
        model=model_name,
        #tools=tools
    )
    return message.content[0].text

def save_summary(summary_text: str, file_name:str, summaries_path: str):
    # Create the summaries directory if it doesn't exist
    if not os.path.exists(summaries_path):
        os.makedirs(summaries_path)
    summary_filename = os.path.splitext(file_name)[0] + "_summary.txt"
    summary_path = os.path.join(summaries_path, summary_filename)
    
    # Write the summary to a file in the summaries directory
    with open(summary_path, 'w', encoding='utf-8') as summary_file:
        summary_file.write(summary_text)
    
    print(f"Summary written to: {summary_path}")    


            
def main():
    parser = argparse.ArgumentParser(description="Process YouTube channel videos")
    parser.add_argument("--test", action="store_true", help="Run in test mode with a single channel")
    args = parser.parse_args()

    load_dotenv()

    # Configuration
    JSON_FILE = "youtube-subscriptions.json"
    DOWNLOAD_DIR = "audio_downloads"
    WHISPER_MODEL = "base"
    BASE_YOUTUBE_URL = "https://www.youtube.com"

    data = load_json_file(JSON_FILE)

    test_channel_id="UCTq1zHztiV69Ur8t6jco4CQ"
    test_channel_name="S2 Underground"

    save_folder = "audio_downloads"
    folder_path = "transcripts"
    summaries_path = "summaries"

    client = AnthropicBedrock()
    
    if args.test:
        channels = [{"id": test_channel_id, "name": test_channel_name}]
    else:
        channels = data["channels"] 
    
    for channel in channels:
        channel_id = channel["id"]
        channel_name = channel["name"]
        print(f"Processing channel: {channel_name}")

        channel_videos = check_channel_recent_videos(channel_id=channel_id, channel_title=channel_name, youtube_url=BASE_YOUTUBE_URL)

        for video in channel_videos:
            download_video(video_url=video['url'], save_folder=save_folder)

        transcribe_downloads(directory=save_folder)
    
    if os.path.exists(folder_path) and os.path.isdir(folder_path):
        for filename in os.listdir(folder_path):
            file_path = os.path.join(folder_path, filename)
            if os.path.isfile(file_path):
                print(f"summarizing: {filename}")
                transcript_data = load_json_file(file_path)
                transcript_text = transcript_data["text"]
                summary = summarize_transcript(transcript_text=transcript_text, client=client)
                print(f"saving: {filename}")
                save_summary(summary_text=summary, file_name=filename, summaries_path=summaries_path)
    
if __name__ == "__main__":
    main()