# meta developer: @shaatimi
# requires: aiohttp

import os
import time
import asyncio
from yt_dlp import YoutubeDL
from pyrogram import filters

TMP_DIR = "/tmp"

@app.on_message(dynamic_access_filter("music") & filters.command("music", prefixes="."))
async def music_turbo(client, message):
    if len(message.command) < 2:
        return

    query = " ".join(message.command[1:])
    status_msg = await message.edit(f"🚀 <code>{query}</code>")

    file = os.path.join(TMP_DIR, f"m_{message.id}.m4a")

    ydl_opts = {
        "format": "bestaudio/best",
        "default_search": "ytsearch1",
        "outtmpl": file,
        "quiet": True,
        "noprogress": True,
        "nocheckcertificate": True,
        "ffmpeg_location": "/app/vendor/ffmpeg/ffmpeg",
        "extractor_args": {
            "youtube": {
                "player_client": ["android", "ios"],
                "skip": ["webpage", "hls"]
            }
        },
        "user_agent": "com.google.android.youtube/19.29.37 (Linux; Android 11)",
    }

    async def p(current, total):
        if not hasattr(p, "l"):
            p.l = 0
        t = time.time()
        if t - p.l < 2.5:
            return
        done = int(current * 10 / total)
        try:
            await status_msg.edit(
                f"📤 {'▰'*done}{'▱'*(10-done)} {int(current*100/total)}%"
            )
        except:
            pass
        p.l = t

    try:
        with YoutubeDL(ydl_opts) as ydl:
            info = await asyncio.to_thread(
                ydl.extract_info,
                f"ytsearch1:{query}",
                download=True
            )
            if "entries" in info:
                info = info["entries"][0]

        await client.send_audio(
            chat_id=message.chat.id,
            audio=file,
            title=info.get("title", "Unknown"),
            performer=info.get("uploader", "YouTube"),
            reply_to_message_id=message.id,
            progress=p
        )

        await status_msg.delete()

    except Exception as e:
        text = str(e)
        if "403" in text or "PO-Token" in text:
            await status_msg.edit("ERROR: YouTube blocked Heroku IP. Update yt-dlp.")
        else:
            await status_msg.edit(f"ERROR: {text[:80]}")

    finally:
        if os.path.exists(file):
            os.remove(file)
