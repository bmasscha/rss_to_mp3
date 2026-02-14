import sys
import os
import re
import requests
import xml.etree.ElementTree as ET

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QPlainTextEdit, QFileDialog
)
from PyQt6.QtCore import QThread, pyqtSignal, Qt
from PyQt6.QtGui import QTextCursor, QFont

# Reusing original slugify
def slugify(text):
    """Creates a safe filename from text."""
    text = re.sub(r'[\\/*?Raw:"<>|]', "", text)
    text = re.sub(r'\s+', "_", text)
    return text.strip("_")

class DownloadWorker(QThread):
    progress_signal = pyqtSignal(str)
    finished_signal = pyqtSignal()

    def __init__(self, rss_url, folder, max_episodes=1000):
        super().__init__()
        self.rss_url = rss_url
        self.folder = folder
        self.max_episodes = max_episodes

    def run(self):
        if not os.path.exists(self.folder):
            try:
                os.makedirs(self.folder)
                self.progress_signal.emit(f"[*] Created folder: {self.folder}")
            except Exception as e:
                self.progress_signal.emit(f"[!] Error creating folder: {e}")
                self.finished_signal.emit()
                return

        self.progress_signal.emit(f"[*] Fetching feed: {self.rss_url}")
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            response = requests.get(self.rss_url, headers=headers, timeout=60)
            response.raise_for_status()
            root = ET.fromstring(response.content)
        except Exception as e:
            self.progress_signal.emit(f"[!] Error: {e}")
            self.finished_signal.emit()
            return

        channel = root.find('channel')
        if channel is None:
            self.progress_signal.emit("[!] Invalid RSS format.")
            self.finished_signal.emit()
            return

        podcast_title = channel.findtext('title', 'Unknown Podcast')
        self.progress_signal.emit(f"[*] Podcast: {podcast_title}")
        self.progress_signal.emit("=" * 40)

        items = channel.findall('item')
        if self.max_episodes:
            items = items[:self.max_episodes]

        count = 0
        for item in items:
            if self.isInterruptionRequested():
                break
                
            title = item.findtext('title', 'Untitled_Episode')
            safe_title = slugify(title)
            file_path = os.path.join(self.folder, f"{safe_title}.mp3")

            enclosure = item.find('enclosure')
            mp3_url = None
            if enclosure is not None:
                url = enclosure.get('url')
                ctype = enclosure.get('type', '')
                if 'audio' in ctype or url.lower().endswith('.mp3'):
                    mp3_url = url
            
            if not mp3_url:
                link = item.findtext('link', '')
                if link.lower().endswith('.mp3'):
                    mp3_url = link
                else:
                    self.progress_signal.emit(f"[-] Skipping: {title} (No MP3)")
                    continue

            if os.path.exists(file_path):
                self.progress_signal.emit(f"[-] Exists: {title}")
                continue

            try:
                self.progress_signal.emit(f"[+] Downloading: {title}...")
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                }
                response = requests.get(mp3_url, headers=headers, stream=True, timeout=60)
                response.raise_for_status()
                
                with open(file_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=16384):
                        if self.isInterruptionRequested():
                            f.close()
                            os.remove(file_path)
                            self.progress_signal.emit("[!] Cancelled.")
                            return
                        f.write(chunk)
                
                self.progress_signal.emit(f"    [DONE] {title}")
                count += 1

            except Exception as e:
                self.progress_signal.emit(f" [!] Failed {title}: {e}")
                if os.path.exists(file_path):
                    os.remove(file_path)

        self.progress_signal.emit("=" * 40)
        self.progress_signal.emit(f"[*] Process complete. {count} new episodes downloaded.")
        self.finished_signal.emit()

class ModernRSSDownloader(QMainWindow):
    def __init__(self):
        super().__init__()
        self.worker = None
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("RSS Audio Grabber")
        self.resize(700, 500)
        
        # Style sheet (PyQt6 compatible)
        self.setStyleSheet("""
            QMainWindow {
                background-color: #1e1e2e;
            }
            QLabel {
                color: #cdd6f4;
                font-size: 13px;
                font-weight: bold;
            }
            QLineEdit {
                background-color: #313244;
                border: 1px solid #45475a;
                border-radius: 5px;
                color: #cdd6f4;
                padding: 8px;
                font-size: 13px;
            }
            QPushButton {
                background-color: #45475a;
                color: #cdd6f4;
                border: none;
                border-radius: 5px;
                padding: 8px 15px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #585b70;
            }
            QPushButton#startBtn {
                background-color: #a6e3a1;
                color: #11111b;
            }
            QPushButton#startBtn:hover {
                background-color: #94e2d5;
            }
            QPlainTextEdit {
                background-color: #11111b;
                color: #a6e3a1;
                border: 1px solid #313244;
                border-radius: 8px;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 12px;
                padding: 10px;
            }
        """)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)

        header = QLabel("RSS TO MP3 DOWNLOADER")
        header.setStyleSheet("font-size: 20px; color: #89b4fa; margin-bottom: 10px;")
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(header)

        rss_layout = QVBoxLayout()
        rss_layout.addWidget(QLabel("RSS Feed URL"))
        self.rss_input = QLineEdit()
        self.rss_input.setPlaceholderText("Paste RSS feed URL here...")
        self.rss_input.setText("https://anchor.fm/s/d399ffec/podcast/rss")
        rss_layout.addWidget(self.rss_input)
        main_layout.addLayout(rss_layout)

        path_layout = QVBoxLayout()
        path_layout.addWidget(QLabel("Destination folder"))
        path_inner = QHBoxLayout()
        self.path_input = QLineEdit()
        default_path = os.path.join(os.getcwd(), "mijn_podcasts")
        self.path_input.setText(default_path)
        path_inner.addWidget(self.path_input)
        
        self.browse_btn = QPushButton("Browse")
        self.browse_btn.clicked.connect(self.browse_folder)
        path_inner.addWidget(self.browse_btn)
        path_layout.addLayout(path_inner)
        main_layout.addLayout(path_layout)

        self.start_btn = QPushButton("START DOWNLOAD")
        self.start_btn.setObjectName("startBtn")
        self.start_btn.setFixedHeight(45)
        self.start_btn.clicked.connect(self.start_download)
        main_layout.addWidget(self.start_btn)

        main_layout.addWidget(QLabel("Progress Output"))
        self.terminal = QPlainTextEdit()
        self.terminal.setReadOnly(True)
        main_layout.addWidget(self.terminal)

    def browse_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Output Directory", self.path_input.text())
        if folder:
            self.path_input.setText(folder)

    def log(self, text):
        self.terminal.appendPlainText(text)
        self.terminal.moveCursor(QTextCursor.MoveOperation.End)

    def start_download(self):
        rss_url = self.rss_input.text().strip()
        folder = self.path_input.text().strip()
        if not rss_url:
            self.log("[!] Missing RSS URL")
            return
        self.start_btn.setEnabled(False)
        self.terminal.clear()
        self.log(f"[*] Initializing session...")
        self.worker = DownloadWorker(rss_url, folder)
        self.worker.progress_signal.connect(self.log)
        self.worker.finished_signal.connect(self.on_finished)
        self.worker.start()

    def on_finished(self):
        self.start_btn.setEnabled(True)
        self.log("[*] Download session finished.")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setFont(QFont("Segoe UI", 10))
    window = ModernRSSDownloader()
    window.show()
    sys.exit(app.exec())
