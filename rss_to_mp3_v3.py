import requests
import os
import re
import xml.etree.ElementTree as ET
from tqdm import tqdm

def slugify(text):
    """
    Creates a safe filename from text.
    Removes invalid characters for Windows and other systems.
    """
    # Remove characters that are illegal in file names
    text = re.sub(r'[\\/*?:"<>|]', "", text)
    # Replace spaces with underscores and remove multiple underscores
    text = re.sub(r'\s+', "_", text)
    return text.strip("_")

def download_rss_to_mp3(rss_url, folder="downloads", max_episodes=10):
    # 1. Create directory
    if not os.path.exists(folder):
        os.makedirs(folder)
        print(f"[*] Folder '{folder}' created.")

    # 2. Fetch Feed
    print(f"[*] Loading feed: {rss_url}")
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(rss_url, headers=headers, timeout=60)
        response.raise_for_status()
        root = ET.fromstring(response.content)
    except Exception as e:
        print(f"[!] Error fetching or parsing feed: {e}")
        return

    # RSS elements are in the 'channel' tag
    channel = root.find('channel')
    if channel is None:
        print("[!] No channel found in RSS.")
        return

    podcast_title = channel.findtext('title', 'Unknown Podcast')
    print(f"[*] Podcast found: {podcast_title}")
    print("-" * 50)

    # 3. Iterate through items
    items = channel.findall('item')
    if max_episodes:
        items = items[:max_episodes]

    for item in items:
        title = item.findtext('title', 'Untitled_Episode')
        safe_title = slugify(title)
        file_path = os.path.join(folder, f"{safe_title}.mp3")

        # Find enclosure
        enclosure = item.find('enclosure')
        mp3_url = None
        if enclosure is not None:
            url = enclosure.get('url')
            # Check if it's likely an audio file
            ctype = enclosure.get('type', '')
            if 'audio' in ctype or url.lower().endswith('.mp3'):
                mp3_url = url
        
        if not mp3_url:
            # Fallback check for link with .mp3
            link = item.findtext('link', '')
            if link.lower().endswith('.mp3'):
                mp3_url = link
            else:
                print(f"[?] Skipping: {title} (no audio file found)")
                continue

        # Already downloaded?
        if os.path.exists(file_path):
            print(f"[-] Already downloaded: {title}")
            continue

        # 4. Download
        try:
            print(f"[+] Downloading: {title}")
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            response = requests.get(mp3_url, headers=headers, stream=True, timeout=60)
            response.raise_for_status()

            total_size = int(response.headers.get('content-length', 0))
            
            with open(file_path, 'wb') as f, tqdm(
                desc=safe_title[:30],
                total=total_size,
                unit='iB',
                unit_scale=True,
                unit_divisor=1024,
            ) as bar:
                for chunk in response.iter_content(chunk_size=8192):
                    size = f.write(chunk)
                    bar.update(size)

        except Exception as e:
            print(f" [!] Error downloading {title}: {e}")
            if os.path.exists(file_path):
                os.remove(file_path) # Clean up partial download

    print("-" * 50)
    print(f"[*] Done! All episodes are in '{folder}'")

# --- CONFIGURATION ---
MIJN_RSS_URL = "https://anchor.fm/s/d399ffec/podcast/rss" # Planet Money (NPR)
TARGET_MAP = "mijn_podcasts"

if __name__ == "__main__":

    download_rss_to_mp3(MIJN_RSS_URL, TARGET_MAP, max_episodes=1000)
#https://www.vrt.be/vrtmax/podcasts/radio-1/d/de-wereld-van-sofie/7/de-grote-pot/?utm_medium=internal&utm_source=vrtmax-app&utm_campaign=share-button&utm_content=web