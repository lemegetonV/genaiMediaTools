import asyncio
import os
import json
import re
import pathlib
import itertools
import logging
logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
    level=logging.INFO
)
logging.getLogger("twscrape").setLevel(logging.DEBUG)
logging.getLogger("httpx").setLevel(logging.DEBUG)

import certifi
import httpx
import aiofiles
from dotenv import load_dotenv
from datetime import datetime, timedelta, timezone
from yt_dlp import YoutubeDL
from twscrape import API
from twscrape.logger import set_log_level

import tkinter as tk
from tkinter import filedialog

# ──────────────────────────────────────────────────────────────────────────
# Resolve the directory this script lives in (so we can find .env, JSON, DB)
SCRIPT_DIR = pathlib.Path(__file__).resolve().parent

# A) TLS bundle so httpx trusts certs on Windows/proxy
os.environ["SSL_CERT_FILE"]      = certifi.where()
os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()

# B) Load .env from the script folder
dotenv_path = SCRIPT_DIR / ".env"
load_dotenv(dotenv_path=dotenv_path)

COOKIE = os.getenv("TWS_COOKIE")
USER   = os.getenv("TWS_USERNAME", "cookie_user")

# C) Ask user where to put the scraped media
root = tk.Tk(); root.withdraw()
BASE = pathlib.Path(filedialog.askdirectory(
    title="Choose folder for downloads") or ".")
BASE.mkdir(exist_ok=True)

# D) Config constants
SINCE = "2024-01-01"
UNTIL = (datetime.now(timezone.utc) + timedelta(days=1))\
            .strftime("%Y-%m-%d")
IMG_N, VID_N = 100, 50
slug = lambda s: re.sub(r"[^\w\-]+", "_", s)[:80]

# E) Helpers
async def download_img(url, path):
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(url)
        r.raise_for_status()
        async with aiofiles.open(path, "wb") as f:
            await f.write(r.content)

async def download_vid(url, pattern):
    loop = asyncio.get_running_loop()
    ydl_opts = {
        "quiet": True,
        "outtmpl": pattern,
        "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best"
    }
    await loop.run_in_executor(
        None,
        lambda: YoutubeDL(ydl_opts).download([url])
    )

# F) Logging setup
logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s %(message)s"
)

logging.getLogger("twscrape").setLevel(logging.DEBUG)

async def process_query(api, query):
    folder = BASE / slug(query)
    folder.mkdir(exist_ok=True)
    imgs, vids = set(), set()

    # text = f"{query} since:{SINCE} until:{UNTIL}"
    text = f"{query}"
    logging.info(f"▶ Search {text!r}")

    async for tw in api.search(text, limit=1000, kv={"product": "Media", "count": 100}):
    # async for tw in api.search(text, kv={"product": "Media"}):
        mgroups = tw.media
        if mgroups is None:
            continue
        if not isinstance(mgroups, (list, tuple, set)):
            mgroups = [mgroups]

        for g in mgroups:
            # photos
            for p in getattr(g, "photos", []):
                if url := getattr(p, "url", None):
                    imgs.add(url)
            # videos + animated
            for v in getattr(g, "videos", []) + getattr(g, "animated", []):
                variants = getattr(v, "variants", []) or []
                # pick highest-bitrate mp4
                mp4_variants = [
                    vv for vv in variants
                    if getattr(vv, "contentType", "").startswith("video/mp4")
                ]
                if mp4_variants:
                    best = max(mp4_variants, key=lambda vv: getattr(vv, "bitrate", 0))
                    vids.add(best.url)

        if len(imgs) >= IMG_N and len(vids) >= VID_N:
            logging.info("  reached target counts, stopping search")
            break

    logging.info(f"Collected {len(imgs)} photos, {len(vids)} videos")

    if not imgs and not vids:
        logging.warning(f"No media found for query {query!r}")
        return

    # download concurrently
    tasks = []
    for i, u in enumerate(itertools.islice(imgs, IMG_N), 1):
        ext = pathlib.Path(u).suffix or ".jpg"
        tasks.append(download_img(u, folder / f"img_{i:03d}{ext}"))
    for i, u in enumerate(itertools.islice(vids, VID_N), 1):
        tasks.append(download_vid(u, str(folder / f"vid_{i:03d}.%(ext)s")))

    await asyncio.gather(*tasks)
    logging.info(f"✓ {query}: {len(imgs)} imgs · {len(vids)} vids → {folder}")

# G) Driver
async def main():
    set_log_level("INFO")
    db_path = SCRIPT_DIR / "accounts.db"
    api = API(str(db_path))

    if COOKIE:
        try:
            await api.pool.add_account(
                USER, "x", "x@mail.com", "x", cookies=COOKIE
            )
        except Exception as e:
            pass
    await api.pool.login_all()

    queries_path = SCRIPT_DIR / "queries.json"
    queries = json.load(open(queries_path, encoding="utf-8"))

    tasks = [process_query(api, q) for q in queries]
    await asyncio.gather(*tasks)

    # await api.aclose()

if __name__ == "__main__":
    asyncio.run(main())