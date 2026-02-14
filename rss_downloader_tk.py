import os
import sys
import threading
import requests
import xml.etree.ElementTree as ET
import re
import tkinter as tk
from tkinter import ttk, filedialog, scrolledtext, messagebox

# --- Core Logic from v3 ---

def slugify(text):
    """Creates a safe filename from text."""
    text = re.sub(r'[\\/*?Raw:"<>|]', "", text)
    text = re.sub(r'\s+', "_", text)
    return text.strip("_")

class RSSDownloaderApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("RSS Audio Grabber (Lite)")
        self.geometry("600x480")
        
        self.stop_event = threading.Event()
        self.download_thread = None

        # Style
        self.style = ttk.Style(self)
        self.style.theme_use('clam') 
        
        self.create_widgets()
        
    def create_widgets(self):
        # Main Frame
        main_frame = ttk.Frame(self, padding="20 20 20 20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Header
        header_label = ttk.Label(main_frame, text="RSS TO MP3 DOWNLOADER", font=("Segoe UI", 16, "bold"))
        header_label.pack(pady=(0, 20))
        
        # RSS URL Input
        rss_frame = ttk.Frame(main_frame)
        rss_frame.pack(fill=tk.X, pady=5)
        ttk.Label(rss_frame, text="RSS Feed URL:").pack(anchor=tk.W)
        self.rss_entry = ttk.Entry(rss_frame)
        self.rss_entry.pack(fill=tk.X, pady=(2, 0))
        self.rss_entry.insert(0, "https://anchor.fm/s/d399ffec/podcast/rss") 
        
        # Destination Folder
        dest_frame = ttk.Frame(main_frame)
        dest_frame.pack(fill=tk.X, pady=5)
        ttk.Label(dest_frame, text="Destination Folder:").pack(anchor=tk.W)
        
        dest_inner = ttk.Frame(dest_frame)
        dest_inner.pack(fill=tk.X, pady=(2, 0))
        
        self.dest_entry = ttk.Entry(dest_inner)
        self.dest_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        default_path = os.path.join(os.getcwd(), "mijn_podcasts")
        self.dest_entry.insert(0, default_path)
        
        browse_btn = ttk.Button(dest_inner, text="Browse", command=self.browse_folder)
        browse_btn.pack(side=tk.RIGHT, padx=(5, 0))
        
        # Buttons Frame
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X, pady=20)

        # Start Button
        self.start_btn = ttk.Button(btn_frame, text="START DOWNLOAD", command=self.start_download_thread)
        self.start_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        
        # Cancel Button
        self.cancel_btn = ttk.Button(btn_frame, text="CANCEL", command=self.cancel_download, state='disabled')
        self.cancel_btn.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(5, 0))
        
        # Log Area
        ttk.Label(main_frame, text="Progress Output:").pack(anchor=tk.W)
        self.log_area = scrolledtext.ScrolledText(main_frame, height=10, state='disabled', font=("Consolas", 9))
        self.log_area.pack(fill=tk.BOTH, expand=True)

    def browse_folder(self):
        folder = filedialog.askdirectory(initialdir=self.dest_entry.get())
        if folder:
            self.dest_entry.delete(0, tk.END)
            self.dest_entry.insert(0, folder)

    def log(self, message):
        self.log_area.config(state='normal')
        self.log_area.insert(tk.END, message + "\n")
        self.log_area.see(tk.END)
        self.log_area.config(state='disabled')

    def start_download_thread(self):
        rss_url = self.rss_entry.get().strip()
        folder = self.dest_entry.get().strip()
        
        if not rss_url:
            messagebox.showerror("Error", "Please enter an RSS URL")
            return
            
        self.start_btn.config(state='disabled')
        self.cancel_btn.config(state='normal')
        self.log_area.config(state='normal')
        self.log_area.delete(1.0, tk.END)
        self.log_area.config(state='disabled')
        
        self.stop_event.clear()
        
        self.download_thread = threading.Thread(target=self.run_download, args=(rss_url, folder))
        self.download_thread.daemon = True
        self.download_thread.start()

    def cancel_download(self):
        if self.download_thread and self.download_thread.is_alive():
            self.log_safe("[!] Cancelling... please wait for current file to clean up.")
            self.stop_event.set()
            self.cancel_btn.config(state='disabled')

    def run_download(self, rss_url, folder):
        try:
            self.perform_download(rss_url, folder)
        except Exception as e:
            self.log_safe(f"[!] Critical Error: {e}")
        finally:
            self.after(0, lambda: self.start_btn.config(state='normal'))
            self.after(0, lambda: self.cancel_btn.config(state='disabled'))
            if self.stop_event.is_set():
                self.log_safe("[*] Download session cancelled.")
            else:
                self.log_safe("[*] Download session finished.")

    def log_safe(self, message):
        self.after(0, lambda: self.log(message))

    def perform_download(self, rss_url, folder, max_episodes=1000):
        if self.stop_event.is_set(): return

        if not os.path.exists(folder):
            try:
                os.makedirs(folder)
                self.log_safe(f"[*] Created folder: {folder}")
            except Exception as e:
                self.log_safe(f"[!] Error creating folder: {e}")
                return

        self.log_safe(f"[*] Fetching feed: {rss_url}")
        try:
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
            response = requests.get(rss_url, headers=headers, timeout=60)
            response.raise_for_status()
            root = ET.fromstring(response.content)
        except Exception as e:
            self.log_safe(f"[!] Error fetching/parsing feed: {e}")
            return

        if self.stop_event.is_set(): return

        channel = root.find('channel')
        if channel is None:
            self.log_safe("[!] Invalid RSS format (no channel).")
            return

        podcast_title = channel.findtext('title', 'Unknown Podcast')
        self.log_safe(f"[*] Podcast: {podcast_title}")
        self.log_safe("=" * 40)

        items = channel.findall('item')
        if max_episodes:
            items = items[:max_episodes]

        count = 0
        for item in items:
            if self.stop_event.is_set(): break
            
            title = item.findtext('title', 'Untitled_Episode')
            safe_title = slugify(title)
            file_path = os.path.join(folder, f"{safe_title}.mp3")

            # Check if exists
            if os.path.exists(file_path):
                self.log_safe(f"[-] Exists: {title}")
                continue

            # Find URL
            mp3_url = None
            enclosure = item.find('enclosure')
            if enclosure is not None:
                url = enclosure.get('url')
                ctype = enclosure.get('type', '')
                if 'audio' in ctype or (url and url.lower().endswith('.mp3')):
                    mp3_url = url
            
            if not mp3_url:
                link = item.findtext('link', '')
                if link and link.lower().endswith('.mp3'):
                    mp3_url = link
            
            if not mp3_url:
                self.log_safe(f"[-] Skipping: {title} (No MP3 found)")
                continue

            # Download
            try:
                self.log_safe(f"[+] Downloading: {title}...")
                with requests.get(mp3_url, headers=headers, stream=True, timeout=60) as r:
                    r.raise_for_status()
                    with open(file_path, 'wb') as f:
                        for chunk in r.iter_content(chunk_size=8192):
                            if self.stop_event.is_set():
                                f.close()
                                os.remove(file_path)
                                self.log_safe(f" [!] Interrupted: {title}")
                                return
                            f.write(chunk)
                self.log_safe(f"    [DONE]")
                count += 1
            except Exception as e:
                self.log_safe(f" [!] Failed {title}: {e}")
                if os.path.exists(file_path):
                    try:
                        os.remove(file_path)
                    except:
                        pass
        
        self.log_safe("=" * 40)
        if not self.stop_event.is_set():
            self.log_safe(f"[*] Process complete. {count} new episodes.")

if __name__ == "__main__":
    app = RSSDownloaderApp()
    app.mainloop()
