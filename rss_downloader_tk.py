import os
import sys
import socket
import threading
import requests
import logging
import urllib3
import tempfile
import urllib.request
import shutil
import time
import xml.etree.ElementTree as ET
import re
import tkinter as tk
from tkinter import ttk, filedialog, scrolledtext, messagebox
import pygame
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Setup logging in temp directory to avoid slow Google Drive I/O
log_file = os.path.join(tempfile.gettempdir(), 'rss_audio_grabber.log')
logging.basicConfig(filename=log_file, level=logging.DEBUG, 
                    format='%(asctime)s - %(levelname)s - %(message)s', filemode='w')

DEBUG_KEEP_TEMP = False # Set to True to prevent deletion of temp audio for debugging

# Silence verbose library logging that might slow down the app
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("requests").setLevel(logging.WARNING)
logging.getLogger("pygame").setLevel(logging.WARNING)

print(f"Logging to: {log_file}")

# Bypass system proxies (often a cause of slow connections in Python)
os.environ['NO_PROXY'] = '*'

# Force IPv4 in requests/urllib3
# This is often more effective than patching socket.getaddrinfo directly
def allowed_gai_family():
    return socket.AF_INET

urllib3.util.connection.allowed_gai_family = allowed_gai_family

# Retain the socket patch just in case
try:
    _orig_getaddrinfo = socket.getaddrinfo
except AttributeError:
    _orig_getaddrinfo = None

def _getaddrinfo_ipv4(host, port, family=0, type=0, proto=0, flags=0):
    if family == 0:
        family = socket.AF_INET
    return _orig_getaddrinfo(host, port, family, type, proto, flags)

# Apply patch
if _orig_getaddrinfo:
    socket.getaddrinfo = _getaddrinfo_ipv4

# --- Core Logic from v3 ---

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)


def slugify(text):
    """Creates a safe filename from text."""
    text = re.sub(r'[\\/*?Raw:"<>|]', "", text)
    text = re.sub(r'\s+', "_", text)
    return text.strip("_")

class RSSDownloaderApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("RSS Audio Grabber (Lite)")
        self.geometry("800x600")
        try:
             self.iconbitmap(resource_path("app.ico"))
        except Exception as e:
             print(f"Icon not found: {e}")
        
        # Initialize pygame mixer
        try:
            pygame.mixer.init()
        except Exception as e:
            print(f"Error initializing pygame mixer: {e}")

        self.stop_event = threading.Event()
        self.download_thread = None
        self.episodes = [] # Store episode data


        # Style
        self.style = ttk.Style(self)
        self.style.theme_use('clam') 
        
        self.create_widgets()
        
    def create_widgets(self):
        # Main Frame
        main_frame = ttk.Frame(self, padding="10 10 10 10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Header
        header_label = ttk.Label(main_frame, text="RSS TO MP3 DOWNLOADER", font=("Segoe UI", 14, "bold"))
        header_label.pack(pady=(0, 10))
        
        # RSS URL Input
        rss_frame = ttk.Frame(main_frame)
        rss_frame.pack(fill=tk.X, pady=5)
        ttk.Label(rss_frame, text="RSS Feed URL:").pack(anchor=tk.W)
        
        url_input_frame = ttk.Frame(rss_frame)
        url_input_frame.pack(fill=tk.X, pady=(2, 0))
        
        self.rss_entry = ttk.Entry(url_input_frame)
        self.rss_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.rss_entry.insert(0, "https://anchor.fm/s/d399ffec/podcast/rss") 
        
        self.list_btn = ttk.Button(url_input_frame, text="List Episodes", command=self.fetch_episodes_thread)
        self.list_btn.pack(side=tk.RIGHT, padx=(5, 0))

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
        
        # Episode List
        list_frame = ttk.Frame(main_frame)
        list_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        ttk.Label(list_frame, text="Episodes (Select to Download):").pack(anchor=tk.W)
        
        columns = ('date', 'duration', 'title')
        self.tree = ttk.Treeview(list_frame, columns=columns, show='headings', selectmode='extended')
        self.tree.heading('date', text='Date')
        self.tree.heading('duration', text='Duration')
        self.tree.heading('title', text='Title')
        self.tree.column('date', width=100, stretch=False)
        self.tree.column('duration', width=80, stretch=False)
        self.tree.column('title', stretch=True)
        
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Buttons Frame
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X, pady=10)

        # Download Selected Button
        self.start_btn = ttk.Button(btn_frame, text="DOWNLOAD SELECTED", command=self.start_download_thread)
        self.start_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5), ipady=10)
        self.start_btn.config(state='disabled') # Disabled initially
        
        # Play/Stop Buttons
        self.play_btn = ttk.Button(btn_frame, text="PLAY", command=self.play_episode_thread)
        self.play_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5), ipady=10)
        
        self.stop_audio_btn = ttk.Button(btn_frame, text="STOP AUDIO", command=self.stop_audio)
        self.stop_audio_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5), ipady=10)
        self.stop_audio_btn.config(state='disabled')

        # Select All Button
        self.select_all_btn = ttk.Button(btn_frame, text="SELECT ALL", command=self.select_all)
        self.select_all_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5), ipady=10)
        
        # Cancel Button
        # Cancel Button
        self.cancel_btn = ttk.Button(btn_frame, text="CANCEL", command=self.cancel_download, state='disabled')
        self.cancel_btn.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(5, 0), ipady=10)
        
        # Status Bar
        self.status_var = tk.StringVar()
        self.status_var.set("Ready")
        status_bar = ttk.Label(main_frame, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        status_bar.pack(fill=tk.X, pady=(5, 0))

    def browse_folder(self):
        folder = filedialog.askdirectory(initialdir=self.dest_entry.get())
        if folder:
            self.dest_entry.delete(0, tk.END)
            self.dest_entry.insert(0, folder)

    def log(self, message):
        print(message)
        # Update status bar with the latest message
        self.status_var.set(message)
        self.update_idletasks()


    def fetch_episodes_thread(self):
        rss_url = self.rss_entry.get().strip()
        if not rss_url:
            messagebox.showerror("Error", "Please enter an RSS URL")
            return
        
        self.list_btn.config(state='disabled')
        self.status_var.set("Fetching feed...")
        
        thread = threading.Thread(target=self.fetch_episodes_logic, args=(rss_url,))
        thread.daemon = True
        thread.start()

    def get_session(self):
        session = requests.Session()
        # Remove Retry logic for now to see if it's causing the hang
        # Just use plain adapter
        adapter = HTTPAdapter(max_retries=0)
        session.mount('http://', adapter)
        session.mount('https://', adapter)
        return session

    def fetch_episodes_logic(self, rss_url):
        try:
            logging.info(f"Python: {sys.executable}")
            logging.info(f"Path: {sys.path}")
            logging.info(f"Starting fetch for URL: {rss_url}")
            t_start = time.time()
            
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
            
            self.after(0, lambda: self.status_var.set("Connecting (Urllib)..."))
            print(f"Connecting to: {rss_url}")
            logging.info(f"Connecting to {rss_url} using Urllib...")
            
            t_req_start = time.time()
            try:
                # Use urllib.request instead of requests to bypass potential library-on-G:Drive issues
                import urllib.request
                req = urllib.request.Request(rss_url, headers=headers)
                # Aggressive 15s timeout
                with urllib.request.urlopen(req, timeout=15) as response_obj:
                    blob = response_obj.read()
                    status_code = response_obj.getcode()
                t_req_end = time.time()
                logging.info(f"Urllib request success in {t_req_end - t_req_start:.2f}s")
            except Exception as e_urllib:
                logging.warning(f"Urllib failed: {e_urllib}. Falling back to requests...")
                self.after(0, lambda: self.status_var.set("Connecting (Requests Fallback)..."))
                t_req_start = time.time()
                # Disable certificate verification and proxies for speed test
                response = requests.get(rss_url, headers=headers, timeout=15, verify=False, proxies={'http': None, 'https': None})
                blob = response.content
                status_code = response.status_code
                t_req_end = time.time()
                logging.info(f"Requests fallback finished in {t_req_end - t_req_start:.2f}s")

            logging.info(f"HTTP Status: {status_code}, Blob size: {len(blob)}")
            
            if status_code != 200:
                raise Exception(f"Server returned status {status_code}")
                
            self.after(0, lambda: self.status_var.set(f"Downloaded {len(blob)/1024:.0f} KB. Parsing..."))
            print("Downloaded. Parsing...")
            logging.info("Parsing XML content...")
            
            try:
                t_parse_start = time.time()
                root = ET.fromstring(blob)
                t_parse_end = time.time()
                logging.info(f"Parsed XML in {t_parse_end - t_parse_start:.4f}s")
            except ET.ParseError as e:
                logging.error(f"XML Parse Error: {e}")
                self.after(0, lambda: messagebox.showerror("Error", f"Failed to parse XML: {e}"))
                return

            channel = root.find('channel')
            if channel is None:
                logging.error("No channel element found.")
                self.after(0, lambda: messagebox.showerror("Error", "Invalid RSS feed"))
                return

            self.episodes = []
            items = channel.findall('item')
            logging.info(f"Found {len(items)} items. Processing loop starting...")
            
            self.after(0, lambda: self.status_var.set(f"Found {len(items)} items. Processing..."))
            print(f"Found {len(items)} items.")
            
            t_loop_start = time.time()
            for i, item in enumerate(items):
                # if i % 50 == 0:
                #      self.after(0, lambda count=i: self.status_var.set(f"Processing item {count}/{len(items)}..."))
                # Disable excessive updates if loop is fast
                
                title = item.findtext('title', 'Untitled')
                pubDate = item.findtext('pubDate', '')
                
                duration = "Unknown"
                # Searching children for duration
                for child in item:
                    if 'duration' in child.tag.lower():
                        if child.text:
                             duration = child.text
                        break
                
                mp3_url = None
                enclosure = item.find('enclosure')
                if enclosure is not None:
                    mp3_url = enclosure.get('url')
                
                if not mp3_url:
                    link = item.findtext('link')
                    if link and link.lower().endswith('.mp3'):
                        mp3_url = link
                
                if mp3_url:
                    # Clean filename
                    filename = slugify(title) + ".mp3"
                    self.episodes.append({
                        'title': title,
                        'url': mp3_url,
                        'filename': filename,
                        'date': pubDate,
                        'duration': duration
                    })
            
            t_loop_end = time.time()
            logging.info(f"Loop finished in {t_loop_end - t_loop_start:.4f}s. Episodes: {len(self.episodes)}")

            logging.info("Scheduling UI update...")
            self.after(0, self.update_list)
            
            t_total = time.time() - t_start
            logging.info(f"Total time: {t_total:.2f}s")

        except Exception as e:
            logging.error(f"Fetch Error: {e}")
            self.after(0, lambda: self.status_var.set("Error fetching feed"))
            self.after(0, lambda: messagebox.showerror("Error", f"Failed to fetch feed: {e}"))
            print(f"Error: {e}")
        finally:
            self.after(0, lambda: self.list_btn.config(state='normal'))

    def update_list(self):
        self.status_var.set("Updating list...")
        print("Updating UI list...")
        
        # Clear existing
        try:
            for item in self.tree.get_children():
                self.tree.delete(item)
                
            for i, ep in enumerate(self.episodes):
                self.tree.insert('', 'end', iid=i, values=(ep['date'], ep['duration'], ep['title']))
                
            self.status_var.set(f"Found {len(self.episodes)} episodes.")
            self.start_btn.config(state='normal')
            print("UI Updated.")
        except Exception as e:
            print(f"Error updating list: {e}")
            messagebox.showerror("Error", f"UI Error: {e}")

    def start_download_thread(self):
        selection = self.tree.selection()
        if not selection:
             messagebox.showwarning("Warning", "No episodes selected.")
             return
             
        folder = self.dest_entry.get().strip()
        if not folder:
             messagebox.showerror("Error", "Please select a destination folder.")
             return

        self.start_btn.config(state='disabled')
        self.cancel_btn.config(state='normal')
        self.list_btn.config(state='disabled')
        
        self.stop_event.clear()
        
        # Get selected episodes data
        selected_indices = [int(item) for item in selection]
        episodes_to_download = [self.episodes[i] for i in selected_indices]
        
        self.download_thread = threading.Thread(target=self.run_download, args=(episodes_to_download, folder))
        self.download_thread.daemon = True
        self.download_thread.start()

    def cancel_download(self):
        if self.download_thread and self.download_thread.is_alive():
            self.log_safe("[!] Cancelling... please wait for current file to clean up.")
            self.stop_event.set()
            self.cancel_btn.config(state='disabled')

    def run_download(self, episodes, folder):
        try:
            self.perform_download_selected(episodes, folder)
        except Exception as e:
            self.log_safe(f"[!] Critical Error: {e}")
            err_msg = str(e)
            self.after(0, lambda: messagebox.showerror("Error", err_msg))
        finally:
            self.after(0, lambda: self.start_btn.config(state='normal'))
            self.after(0, lambda: self.cancel_btn.config(state='disabled'))
            self.after(0, lambda: self.list_btn.config(state='normal'))
            if self.stop_event.is_set():
                self.log_safe("[*] Download session cancelled.")
            else:
                self.log_safe("[*] Download session finished.")


    def log_safe(self, message):
        self.after(0, lambda: self.log(message))

    def robust_download(self, url, file_path):
        """Downloads a file using urllib with a requests fallback and progress logging."""
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
            'Referer': 'https://podcasts.vrt.be/'
        }
        
        # Force global socket timeout to prevent indefinite hangs
        socket.setdefaulttimeout(15)
        
        success = False
        error_msg = ""
        
        logging.info(f"Downloading to: {file_path}")
        print(f"[*] Attemping download to local disk...")

        # Progress callback for urlretrieve
        def reporthook(count, block_size, total_size):
            if self.stop_event.is_set():
                raise Exception("Cancelled")
            downloaded = count * block_size
            if downloaded % (1024 * 512) < block_size:
                self.log_safe(f"[*] Buffering: {downloaded/1024:.0f}KB received...")
                print(f"    - Progress: {downloaded/1024:.0f}KB")

        try:
            logging.info(f"Attempting urlretrieve: {url}")
            # We need to add headers to the opener
            opener = urllib.request.build_opener()
            opener.addheaders = [('User-agent', headers['User-Agent']), ('Referer', headers['Referer'])]
            urllib.request.install_opener(opener)
            
            # Disable SSL for this attempt just in case
            import ssl
            ssl._create_default_https_context = ssl._create_unverified_context
            
            urllib.request.urlretrieve(url, file_path, reporthook=reporthook)
            
            size = os.path.getsize(file_path)
            logging.info(f"urlretrieve finished. Size: {size}")
            if size > 1024:
                success = True
            else:
                error_msg = f"Download ended prematurely (Size: {size})"
        except Exception as e:
            error_msg = f"urlretrieve failed: {e}"
            logging.warning(error_msg)
            print(f"    [!] Primary attempt failed: {e}")
            
        # Requests fallback (minimal)
        if not success and not self.stop_event.is_set():
            try:
                logging.info(f"Attempting Requests fallback: {url}")
                print("    [*] Trying fallback method...")
                response = requests.get(url, headers=headers, stream=True, timeout=15, verify=False)
                response.raise_for_status()
                with open(file_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=65536):
                        if self.stop_event.is_set():
                             return False, "Cancelled"
                        f.write(chunk)
                if os.path.exists(file_path) and os.path.getsize(file_path) > 1024:
                    success = True
            except Exception as e:
                error_msg = f"Fallback also failed: {e}"
                logging.error(error_msg)
                
        return success, error_msg

    def perform_download_selected(self, episodes, folder):
        if self.stop_event.is_set(): return

        if not os.path.exists(folder):
            try:
                os.makedirs(folder)
                self.log_safe(f"[*] Created folder: {folder}")
            except Exception as e:
                self.log_safe(f"[!] Error creating folder: {e}")
                return

        self.log_safe(f"[*] Starting download of {len(episodes)} episodes...")
        self.log_safe("=" * 40)

        for i, ep in enumerate(episodes):
            if self.stop_event.is_set(): break
            
            title = ep['title']
            url = ep['url']
            safe_title = slugify(title)
            file_path = os.path.join(folder, f"{safe_title}.mp3")

            if os.path.exists(file_path):
                self.log_safe(f"[-] Exists: {title}")
                continue

            self.log_safe(f"[+] Downloading ({i+1}/{len(episodes)}): {title}...")
            
            success, err = self.robust_download(url, file_path)
            if success:
                self.log_safe(f"    [DONE]")
            else:
                if err == "Cancelled":
                    self.log_safe(f" [!] Interrupted: {title}")
                    if os.path.exists(file_path): os.remove(file_path)
                    return
                else:
                    self.log_safe(f" [!] Failed {title}: {err}")
                    if os.path.exists(file_path): os.remove(file_path)
        
        self.log_safe("=" * 40)
        if not self.stop_event.is_set():
            self.log_safe(f"[*] Process complete.")

    def select_all(self):
        self.tree.selection_set(self.tree.get_children())

    def play_episode_thread(self):
        selection = self.tree.selection()
        if not selection:
            return
        
        # Only play first selected if multiple
        index = int(selection[0])
        episode = self.episodes[index]
        
        self.stop_audio() # Stop any current playback
        
        thread = threading.Thread(target=self.play_episode_logic, args=(episode,))
        thread.daemon = True
        thread.start()

    def play_episode_logic(self, episode):
        self.stop_event.clear() # Clear any previous stop signals
        url = episode['url']
        self.log_safe(f"[*] Buffering: {episode['title']}...")
        self.after(0, lambda: self.play_btn.config(state='disabled'))
        self.after(0, lambda: self.stop_audio_btn.config(state='normal'))
        
        try:
            # Create a temp file
            self.temp_audio = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
            self.temp_audio_path = self.temp_audio.name
            self.temp_audio.close() 
            
            logging.info(f"Starting playback download to {self.temp_audio_path}")
            success, err = self.robust_download(url, self.temp_audio_path)
            
            if success:
                size = os.path.getsize(self.temp_audio_path)
                logging.info(f"Download success. File size: {size} bytes")
                
                if size < 1000:
                    raise Exception(f"Downloaded file is too small ({size} bytes). Possibly not a valid MP3.")

                self.log_safe(f"[*] Playing: {episode['title']}")
                
                if not pygame.mixer.get_init():
                    logging.info("Re-initializing pygame mixer...")
                    pygame.mixer.init()

                pygame.mixer.music.load(self.temp_audio_path)
                pygame.mixer.music.play()
                
                # Wait loop to check for end of song or stop
                while pygame.mixer.music.get_busy():
                    if self.stop_event.is_set():
                        pygame.mixer.music.stop()
                        break
                    time.sleep(0.5)
                logging.info("Playback finished or stopped.")
            else:
                if err != "Cancelled":
                    raise Exception(f"Download failed: {err}")

        except Exception as e:
            logging.error(f"Playback error: {e}")
            self.log_safe(f"[!] Playback Error: {e}")
            err_msg = str(e)
            self.after(0, lambda: messagebox.showerror("Playback Error", err_msg))
        finally:
            self.stop_event.clear()
            self.after(0, lambda: self.play_btn.config(state='normal'))
            self.after(0, lambda: self.stop_audio_btn.config(state='disabled'))
            self.cleanup_temp_audio()
            self.log_safe("Ready")

    def stop_audio(self):
        self.stop_event.set() # Signal thread to stop
        if pygame.mixer.get_init():
             pygame.mixer.music.stop()
        self.log_safe("Stopped.")

    def cleanup_temp_audio(self):
        try:
            pygame.mixer.music.unload() # Unload to release file lock
        except:
            pass
            
        if DEBUG_KEEP_TEMP:
            logging.info(f"DEBUG: Keeping temp file at {getattr(self, 'temp_audio_path', 'N/A')}")
            return

        if hasattr(self, 'temp_audio_path') and self.temp_audio_path:
            try:
                os.remove(self.temp_audio_path)
            except Exception as e:
                print(f"Error removing temp file: {e}")
            self.temp_audio_path = None

if __name__ == "__main__":
    app = RSSDownloaderApp()
    try:
        app.mainloop()
    finally:
        # Final cleanup
        if hasattr(app, 'cleanup_temp_audio'):
            app.cleanup_temp_audio()
        try:
            pygame.mixer.quit()
        except:
            pass
