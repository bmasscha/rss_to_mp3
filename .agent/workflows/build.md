---
description: how to build the RSS to MP3 executable
---
1. Ensure all dependencies are installed:
// turbo

```powershell
pip install -r requirements.txt
```

1. Run PyInstaller to create the single-file executable:
// turbo

```powershell
pyinstaller --noconsole --onefile --name "RSS_Audio_Grabber" --clean rss_to_mp3_gui.py
```

1. Find your executable in the `dist` folder.
