#!/usr/bin/env python
# twitter_media_scraper.py   ⓒ2025

import asyncio, itertools, json, logging, os, pathlib, re, sys
import aiofiles, certifi, httpx
from dotenv import load_dotenv
from twscrape import API
from twscrape.logger import set_log_level
from yt_dlp import YoutubeDL

# ─────────────────────────  basic setup ─────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)

SCRIPT_DIR = pathlib.Path(__file__).resolve().parent
dotenv_path = SCRIPT_DIR / ".env"
load_dotenv(dotenv_path=dotenv_path)

COOKIE = os.getenv("TWS_COOKIE")
USER   = os.getenv("TWS_USERNAME", "cookie_user")

os.environ["SSL_CERT_FILE"]      = certifi.where()
os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()

# ─────────────────────────  choose output folder ─────────────────────────
import tkinter as tk
from tkinter import filedialog, simpledialog, messagebox
root = tk.Tk(); root.withdraw()
BASE = pathlib.Path(filedialog.askdirectory(
    title="Choose folder for downloads") or ".")
BASE.mkdir(exist_ok=True)

# ─────────────────────────  interactive inputs ─────────────────────────
def ask_cli(prompt: str, default: str) -> str:
    try:
        val = input(prompt).strip()
        return val or default
    except EOFError:   # no console (double‑click run)
        return simpledialog.askstring("Input required", prompt, initialvalue=default) or default

media_choice = ask_cli("Download images, videos, or both?  [i/v/b] ", "b").lower()[:1]
tab_choice   = ask_cli("Search Top or Latest tab?          [top/latest] ", "top").lower()
product      = "Top" if tab_choice.startswith("t") else "Latest"

# ─────────────────────────  constants & helpers ─────────────────────────
IMG_MAX, VID_MAX = 20, 20

async def download_img(url, path):
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(url)
        r.raise_for_status()
        async with aiofiles.open(path, "wb") as f:
            await f.write(r.content)

async def download_vid(url, pattern):
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, lambda: YoutubeDL({
        "quiet": True,
        "outtmpl": pattern,
        "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best"
    }).download([url]))

def next_index(prefix: str) -> int:
    rx = re.compile(rf"{prefix}_(\d+)")
    nums = [int(m.group(1)) for p in BASE.glob(f"{prefix}_*")
            if (m := rx.search(p.name))]
    return max(nums, default=0) + 1

# ─────────────────────────  core worker ─────────────────────────
async def grab(api, query, kind):
    logging.info("▶ '%s'  [%s]  (%s)", query, product, kind)
    collected = set()

    async for tw in api.search(
            query, limit=1000, kv={"product": product, "count": 100}):
        if not tw.media:
            continue
        for m in (tw.media if isinstance(tw.media, (list, tuple, set)) else [tw.media]):
            if kind == "images":
                for p in getattr(m, "photos", []):
                    if p.url:
                        collected.add(p.url)
            else:
                for v in getattr(m, "videos", []) + getattr(m, "animated", []):
                    mp4s = [vv for vv in getattr(v, "variants", []) or []
                            if getattr(vv, "contentType", "").startswith("video/mp4")]
                    if mp4s:
                        collected.add(max(mp4s, key=lambda vv: getattr(vv, "bitrate", 0)).url)
        if (kind == "images" and len(collected) >= IMG_MAX) or \
           (kind == "videos" and len(collected) >= VID_MAX):
            break

    if not collected:
        logging.warning("  no %s found", kind)
        return

    start = next_index("img" if kind == "images" else "vid")
    tasks = []
    if kind == "images":
        for i, url in enumerate(collected, start):
            ext = pathlib.Path(url).suffix or ".jpg"
            tasks.append(download_img(url, BASE / f"img_{i:03d}{ext}"))
            if i - start + 1 >= IMG_MAX:
                break
    else:
        for i, url in enumerate(collected, start):
            tasks.append(download_vid(url, str(BASE / f"vid_{i:03d}.%(ext)s")))
            if i - start + 1 >= VID_MAX:
                break

    await asyncio.gather(*tasks)
    logging.info("✓ saved %d %s → %s", len(collected), kind, BASE)

# ─────────────────────────  main ─────────────────────────
async def main():
    # read queries.json  (array of strings)
    try:
        with open(SCRIPT_DIR / "queries.json", encoding="utf-8") as f:
            queries = [q.strip() for q in json.load(f) if q.strip()]
    except Exception as e:
        messagebox.showerror("Error", f"Cannot read queries.json: {e}")
        return
    if not queries:
        messagebox.showinfo("Nothing to do", "queries.json is empty.")
        return

    set_log_level("INFO")
    api = API(str(SCRIPT_DIR / "accounts.db"))
    if COOKIE:
        try:
            await api.pool.add_account(USER, "x", "x@mail.com", "x", cookies=COOKIE)
        except Exception:
            pass
    await api.pool.login_all()

    tasks = []
    for q in queries:
        if media_choice in {"i", "b"}:
            tasks.append(grab(api, f"{q} filter:images", "images"))
        if media_choice in {"v", "b"}:
            tasks.append(grab(api, f"{q} filter:native_video", "videos"))

    if tasks:
        await asyncio.gather(*tasks)

if __name__ == "__main__":
    asyncio.run(main())
