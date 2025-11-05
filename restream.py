import os
import time
import random
import json
import threading
import subprocess
import logging
from logging.handlers import RotatingFileHandler
from collections import deque
from flask import Flask, Response, render_template_string, abort, stream_with_context

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
app = Flask(__name__)

LOG_PATH = "/mnt/data/radio.log"
COOKIES_PATH = "/mnt/data/cookies.txt"
CACHE_FILE = "/mnt/data/playlist_cache.json"
os.makedirs(DOWNLOAD_DIR := "/mnt/data/radio_cache", exist_ok=True)
os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)

handler = RotatingFileHandler(LOG_PATH, maxBytes=5*1024*1024, backupCount=3)
logging.getLogger().addHandler(handler)

PLAYLISTS = {
    "kas_ranker": "https://youtube.com/playlist?list=PLS2N6hORhZbuZsS_2u5H_z6oOKDQT1NRZ",
    "ca": "https://youtube.com/playlist?list=PLYKzjRvMAyci_W5xYyIXHBoR63eefUadL",
    "samastha": "https://youtube.com/playlist?list=PLgkREi1Wpr-XgNxocxs3iPj61pqMhi9bv",
    "hindi_playlist": "https://youtube.com/playlist?list=PLlXSv-ic4-yJj2djMawc8XqqtCn1BVAc2",
    "eftguru": "https://youtube.com/playlist?list=PLYKzjRvMAycgYvPysx_tiv0q-ZHnDJx0y",


"std_10": "https://youtube.com/playlist?list=PLFMb-2_G0bMZMOWz-RvR9dk2Sj0UUnQTZ",



}

PLAY_MODES = {
    "kas_ranker": "normal",
    "ca": "shuffle",
    "samastha": "shuffle",
    "hindi_playlist": "shuffle",
    "eftguru": "shuffle",

    "std_10": "shuffle",

}

STREAMS_RADIO = {}
MAX_QUEUE = 128
REFRESH_INTERVAL = 10800  # 3 hr

# ==============================================================
# 🧩 Playlist Caching + Loader
# ==============================================================

def load_cache_radio():
    if os.path.exists(CACHE_FILE):
        try:
            return json.load(open(CACHE_FILE))
        except Exception:
            return {}
    return {}

def save_cache_radio(data):
    try:
        json.dump(data, open(CACHE_FILE, "w"))
    except Exception as e:
        logging.error(e)

CACHE_RADIO = load_cache_radio()


def get_playlist_ids(url):
    """Return list of YouTube video IDs from a playlist URL using yt-dlp."""
    try:
        cmd = [
            "yt-dlp",
            "--flat-playlist",
            "--dump-single-json",
            "--no-warnings",
            "--quiet",
            url
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        data = json.loads(result.stdout)
        return [entry["id"] for entry in data.get("entries", []) if "id" in entry]
    except Exception as e:
        logging.error(f"get_playlist_ids() failed for {url}: {e}")
        return []


def load_playlist_ids_radio(name, url):
    """Load and cache YouTube playlist IDs with safe mode handling."""
    try:
        ids = get_playlist_ids(url)
        if not ids:
            logging.warning(f"[{name}] ⚠️ No videos found in playlist — using empty list.")
            CACHE_RADIO[name] = []
            save_cache_radio(CACHE_RADIO)
            return []

        mode = PLAY_MODES.get(name, "normal").lower().strip()
        if mode == "shuffle":
            random.shuffle(ids)
        elif mode == "reverse":
            ids.reverse()

        CACHE_RADIO[name] = ids
        save_cache_radio(CACHE_RADIO)
        logging.info(f"[{name}] Cached {len(ids)} videos in {mode.upper()} mode.")
        return ids

    except Exception as e:
        logging.exception(f"[{name}] ❌ Failed to load playlist ({e}) — fallback to normal order.")
        return CACHE_RADIO.get(name, [])


# ==============================================================
# 🎧 Streaming Worker
# ==============================================================

def stream_worker_radio(name):
    s = STREAMS_RADIO[name]
    while True:
        try:
            ids = s["IDS"]
            if not ids:
                ids = load_playlist_ids_radio(name, PLAYLISTS[name])
                s["IDS"] = ids
            if not ids:
                logging.warning(f"[{name}] No playlist ids found; sleeping...")
                time.sleep(10)
                continue

            vid = ids[s["INDEX"] % len(ids)]
            s["INDEX"] += 1
            url = f"https://www.youtube.com/watch?v={vid}"
            logging.info(f"[{name}] ▶️ {url}")

            cmd = (
                f'yt-dlp -f "bestaudio/best" --cookies "{COOKIES_PATH}" '
                f'--user-agent "Mozilla/5.0" '
                f'-o - --quiet --no-warnings "{url}" | '
                f'ffmpeg -loglevel quiet -i pipe:0 -ac 1 -ar 44100 -b:a 40k -f mp3 pipe:1'
            )

            proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)

            while True:
                chunk = proc.stdout.read(4096)
                if not chunk:
                    break
                while len(s["QUEUE"]) >= MAX_QUEUE:
                    time.sleep(0.05)
                s["QUEUE"].append(chunk)

            proc.wait()
            logging.info(f"[{name}] ✅ Track completed.")
            time.sleep(2)

        except Exception as e:
            logging.error(f"[{name}] Worker error: {e}")
            time.sleep(5)

# ==============================================================
# 🌐 Flask Routes
# ==============================================================

@app.route("/")
def home():
    playlists = list(PLAYLISTS.keys())
    html = """<!doctype html><html><head>
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>🎧 YouTube Radio</title>
<style>
body{background:#000;color:#0f0;font-family:Arial,Helvetica,sans-serif;text-align:center;margin:0;padding:12px}
a{display:block;color:#0f0;text-decoration:none;border:1px solid #0f0;padding:10px;margin:8px;border-radius:8px;font-size:18px}
a:hover{background:#0f0;color:#000}
</style></head><body>
<h2>🎶 YouTube Playlist Radio</h2>
<a href="/mcq">🧠 Go to MCQ Converter</a>
{% for p in playlists %}
  <a href="/listen/{{p}}">▶ {{p|capitalize}}</a>
{% endfor %}
</body></html>"""
    return render_template_string(html, playlists=playlists)


@app.route("/listen/<name>")
def listen_radio_download(name):
    if name not in STREAMS_RADIO:
        abort(404)
    s = STREAMS_RADIO[name]
    def gen():
        while True:
            if s["QUEUE"]:
                yield s["QUEUE"].popleft()
            else:
                time.sleep(0.05)
    headers = {"Content-Disposition": f"attachment; filename={name}.mp3"}
    return Response(stream_with_context(gen()), mimetype="audio/mpeg", headers=headers)


@app.route("/stream/<name>")
def stream_audio(name):
    if name not in STREAMS_RADIO:
        abort(404)
    s = STREAMS_RADIO[name]
    def gen():
        while True:
            if s["QUEUE"]:
                yield s["QUEUE"].popleft()
            else:
                time.sleep(0.05)
    return Response(stream_with_context(gen()), mimetype="audio/mpeg")

def cache_refresher():
    while True:
        for name, url in PLAYLISTS.items():
            last = STREAMS_RADIO[name]["LAST_REFRESH"]
            if time.time() - last > REFRESH_INTERVAL:
                logging.info(f"[{name}] 🔁 Refreshing playlist cache...")
                STREAMS_RADIO[name]["IDS"] = load_playlist_ids_radio(name, url)
                STREAMS_RADIO[name]["LAST_REFRESH"] = time.time()
        time.sleep(1800)


# ==============================================================
# 🚀 START SERVER
# ==============================================================

if __name__ == "__main__":
    for pname, url in PLAYLISTS.items():
        STREAMS_RADIO[pname] = {
            "IDS": load_playlist_ids_radio(pname, url),
            "INDEX": 0,
            "QUEUE": deque(),
            "LAST_REFRESH": time.time(),
        }
        threading.Thread(target=stream_worker_radio, args=(pname,), daemon=True).start()

    # ✅ Start cache refresher thread properly
    threading.Thread(target=cache_refresher, daemon=True).start()

    logging.info("🚀 Unified Flask App (Radio + MCQ Converter) running at http://0.0.0.0:8000")
    app.run(host="0.0.0.0", port=8000)