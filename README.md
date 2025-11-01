
# 🎧 Multi-Playlist YouTube Radio (MP3 Streaming)

A lightweight Python Flask application that streams audio from YouTube playlists as MP3, designed for **Internet radio use**. Supports multiple playlists with unique streaming URLs, caching, and automatic playlist refresh. Built with `yt-dlp` and `ffmpeg` for stable streaming.

---

## Features

- Stream **multiple YouTube playlists** simultaneously.
- **Download / force download MP3** via `/stream/<playlist>` endpoint.
- **Mobile-friendly web interface** to listen to playlists via `/listen/<playlist>`.
- **Automatic playlist refresh** every 30 minutes.
- **Caching of video IDs** to avoid repeated playlist scraping.
- **Direct audio streaming using `yt-dlp -g`** to reduce 403 Forbidden errors.
- Compatible with **small devices and Internet radio hardware**.
- Logs activity to `/mnt/data/radio.log`.

---

## Requirements

- Python 3.11+
- [Flask](https://flask.palletsprojects.com/)
- [yt-dlp](https://github.com/yt-dlp/yt-dlp)
- [ffmpeg](https://ffmpeg.org/)
- Cookies file from YouTube (`cookies.txt`) for logged-in sessions (optional, recommended for age-restricted content)

---

## Installation

1. Clone this repository:

```bash
git clone https://github.com/yourusername/youtube-radio.git
cd youtube-radio

2. Install Python dependencies:



pip install -r requirements.txt

3. Ensure yt-dlp and ffmpeg are installed and in your PATH.


4. Place your YouTube cookies file at /mnt/data/cookies.txt (optional but recommended).


5. Edit the PLAYLISTS dictionary in app.py to include your desired playlists.




---

Usage

Run the Flask app:

python app.py

Access the homepage: http://localhost:5000/

Listen to a playlist: http://localhost:5000/listen/<playlist_name>

Download MP3: http://localhost:5000/stream/<playlist_name>


The app will automatically start streaming all playlists in the background.


---

Configuration

PLAYLISTS: Add multiple playlists with unique names.

MAX_QUEUE_SIZE: Maximum chunks to hold in memory for streaming (default 100).

CACHE_FILE: Path to cache video IDs to avoid repeated scraping.

COOKIES_PATH: Path to YouTube cookies file.



---

Notes

The server uses Flask's development server; for production, deploy with a WSGI server like gunicorn.

Some videos may still fail due to region-locking, age restrictions, or YouTube restrictions.

Direct audio URLs are fetched with yt-dlp -g for stability.

Logs are written to /mnt/data/radio.log.



---

Example PLAYLISTS configuration

PLAYLISTS = {
    "Malayalam": "https://youtube.com/playlist?list=PLYKzjRvMAychqR_ysgXiHAywPUsVw0AzE",
    "Hindi": "https://youtube.com/playlist?list=PLlXSv-ic4-yJj2djMawc8XqqtCn1BVAc2",
}


---

License

MIT License – Free to use, modify, and distribute.


---

Acknowledgements

yt-dlp for YouTube extraction.

ffmpeg for audio streaming and conversion.

Flask for the lightweight web framework.


---
