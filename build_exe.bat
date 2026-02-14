@echo off
echo [*] Installing dependencies...
pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org --default-timeout=100 -r requirements.txt
echo [*] Building executable...
pyinstaller --noconsole --onefile --name "RSS_Audio_Grabber" --collect-all PyQt6 --clean rss_to_mp3_gui.py
echo [*] Build complete! Check the 'dist' folder.
pause
