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
        
        columns = ('date', 'title')
        self.tree = ttk.Treeview(list_frame, columns=columns, show='headings', selectmode='extended')
        self.tree.heading('date', text='Date')
        self.tree.heading('title', text='Title')
        self.tree.column('date', width=100, stretch=False)
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
        self.start_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        self.start_btn.config(state='disabled') # Disabled initially
        
        # Cancel Button
        self.cancel_btn = ttk.Button(btn_frame, text="CANCEL", command=self.cancel_download, state='disabled')
        self.cancel_btn.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(5, 0))
        
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

    def fetch_episodes_logic(self, rss_url):
        try:
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
            response = requests.get(rss_url, headers=headers, timeout=60)
            response.raise_for_status()
            root = ET.fromstring(response.content)
            channel = root.find('channel')
            
            if channel is None:
                self.after(0, lambda: messagebox.showerror("Error", "Invalid RSS feed"))
                return

            self.episodes = []
            items = channel.findall('item')
            
            for item in items:
                title = item.findtext('title', 'Untitled')
                pubDate = item.findtext('pubDate', '')
                
                # Extract URL
                mp3_url = None
                enclosure = item.find('enclosure')
                if enclosure is not None:
                    mp3_url = enclosure.get('url')
                
                if not mp3_url:
                    link = item.findtext('link')
                    if link and link.lower().endswith('.mp3'):
                        mp3_url = link
                
                if mp3_url:
                     self.episodes.append({
                        'title': title,
                        'date': pubDate[:16] if pubDate else "Unknown", # Simple truncation for now
                        'url': mp3_url,
                        'original_item': item
                    })
            
            self.after(0, self.update_list)
            
        except Exception as e:
            self.after(0, lambda: messagebox.showerror("Error", f"Failed to fetch feed: {e}"))
            self.after(0, lambda: self.status_var.set("Ready"))
        finally:
            self.after(0, lambda: self.list_btn.config(state='normal'))

    def update_list(self):
        # Clear existing
        for item in self.tree.get_children():
            self.tree.delete(item)
            
        for i, ep in enumerate(self.episodes):
            self.tree.insert('', 'end', iid=i, values=(ep['date'], ep['title']))
            
        self.status_var.set(f"Found {len(self.episodes)} episodes.")
        self.start_btn.config(state='normal')

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
            self.after(0, lambda: messagebox.showerror("Error", str(e)))
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
        
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}

        for i, ep in enumerate(episodes):
            if self.stop_event.is_set(): break
            
            title = ep['title']
            url = ep['url']
            safe_title = slugify(title)
            file_path = os.path.join(folder, f"{safe_title}.mp3")

            # Check if exists
            if os.path.exists(file_path):
                self.log_safe(f"[-] Exists: {title}")
                continue

            # Download
            try:
                self.log_safe(f"[+] Downloading ({i+1}/{len(episodes)}): {title}...")
                with requests.get(url, headers=headers, stream=True, timeout=60) as r:
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
            except Exception as e:
                self.log_safe(f" [!] Failed {title}: {e}")
                if os.path.exists(file_path):
                    try:
                        os.remove(file_path)
                    except:
                        pass
        
        self.log_safe("=" * 40)
        if not self.stop_event.is_set():
            self.log_safe(f"[*] Process complete.")

if __name__ == "__main__":
    app = RSSDownloaderApp()
    app.mainloop()
