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

# ==============================================================
# 🎶 YouTube Playlist Radio SECTION
# ==============================================================

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



}

STREAMS_RADIO = {}
MAX_QUEUE = 128
REFRESH_INTERVAL = 1800  # 30 min

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

def load_playlist_ids_radio(name, force=False):
    now = time.time()
    cached = CACHE_RADIO.get(name, {})
    if not force and cached and now - cached.get("time", 0) < REFRESH_INTERVAL:
        return cached["ids"]

    url = PLAYLISTS[name]
    try:
        logging.info(f"[{name}] Refreshing playlist...")
        res = subprocess.run(
            ["yt-dlp", "--flat-playlist", "-J", url, "--cookies", COOKIES_PATH],
            capture_output=True, text=True, check=True
        )
        data = json.loads(res.stdout)
        ids = [e["id"] for e in data.get("entries", []) if "id" in e][::-1]
        CACHE_RADIO[name] = {"ids": ids, "time": now}
        save_cache_radio(CACHE_RADIO)
        logging.info(f"[{name}] Cached {len(ids)} videos.")
        return ids
    except Exception as e:
        logging.error(f"[{name}] Playlist error: {e}")
        return cached.get("ids", [])

def stream_worker_radio(name):
    s = STREAMS_RADIO[name]
    while True:
        try:
            ids = s["IDS"]
            if not ids:
                ids = load_playlist_ids_radio(name, True)
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
                f'--user-agent "Mozilla/5.0 (Windows NT 10.0; Win64; x64)" '
                f'-o - --quiet --no-warnings "{url}" | '
                f'ffmpeg -loglevel quiet -i pipe:0 -ac 1 -ar 44100 -b:a 64k -f mp3 pipe:1'
            )

            proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)

            while True:
                chunk = proc.stdout.read(4096)
                if not chunk:
                    break
                # 🟢 Instead of skipping when queue is full, block until space
                while len(s["QUEUE"]) >= MAX_QUEUE:
                    time.sleep(0.05)
                s["QUEUE"].append(chunk)

            proc.wait()
            logging.info(f"[{name}] ✅ Track completed.")
            time.sleep(2)  # small delay before next video

        except Exception as e:
            logging.error(f"[{name}] Worker error: {e}")
            time.sleep(5)

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

# ==============================================================
# 🔀 Playlist Order Control (Add-only, no modification to core)
# ==============================================================
PLAYLIST_ORDER = {name: "normal" for name in PLAYLISTS}  # store current mode

def reorder_playlist(name, mode="normal"):
    """Reorder playlist entries without affecting the cache logic."""
    if name not in CACHE_RADIO or "ids" not in CACHE_RADIO[name]:
        return
    ids = CACHE_RADIO[name]["ids"]
    if mode == "shuffle":
        random.shuffle(ids)
    elif mode == "reverse":
        ids = list(reversed(ids))
    CACHE_RADIO[name]["ids"] = ids
    CACHE_RADIO[name]["time"] = time.time()
    save_cache_radio(CACHE_RADIO)
    PLAYLIST_ORDER[name] = mode
    logging.info(f"[{name}] Playlist set to {mode} mode with {len(ids)} videos.")

@app.route("/mode/<name>/<mode>")
def set_playlist_mode(name, mode):
    """Switch between shuffle, reverse, and normal modes."""
    if name not in PLAYLISTS:
        abort(404)
    if mode not in ["shuffle", "reverse", "normal"]:
        return f"❌ Invalid mode. Use /mode/<name>/shuffle | reverse | normal"
    reorder_playlist(name, mode)
    return f"✅ {name} playlist set to {mode} mode."

@app.route("/status")
def show_status():
    """Show current playlist modes."""
    html = "<h3>🎶 Playlist Modes</h3><ul>"
    for k, v in PLAYLIST_ORDER.items():
        html += f"<li>{k}: {v}</li>"
    html += "</ul>"
    return html

# ==============================================================
# 🚀 START SERVER
# ==============================================================

if __name__ == "__main__":
    for pname in PLAYLISTS:
        STREAMS_RADIO[pname] = {
            "IDS": load_playlist_ids_radio(pname),
            "INDEX": 0,
            "QUEUE": deque(),
            "LAST_REFRESH": time.time(),
        }
        threading.Thread(target=stream_worker_radio, args=(pname,), daemon=True).start()

    logging.info("🚀 YouTube Playlist Radio server running at http://0.0.0.0:8000")
    app.run(host="0.0.0.0", port=8000)
