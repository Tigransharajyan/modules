# meta developer: @shaatimi
# requires: yt-dlp

from .. import loader, utils
import os
import time
import asyncio
from yt_dlp import YoutubeDL

@loader.tds
class Music(loader.Module):
    strings_ru = {
        "name": "Music",
        "no_args": "❌ Укажи название музыки.",
        "downloading": "🚀 <code>{query}</code>",
        "blocked": "❌ YouTube заблокировал IP. Обнови yt-dlp.",
        "error": "❌ Ошибка: {e}",
    }

    strings = {
        "name": "Music",
        "no_args": "❌ Specify a song name.",
        "downloading": "🚀 <code>{query}</code>",
        "blocked": "❌ YouTube blocked server IP. Update yt-dlp.",
        "error": "❌ Error: {e}",
    }

    @loader.command(
        ru_doc="Быстро скачать музыку по названию",
        en_doc="Fast music download by name",
    )
    async def music(self, message):
        query = utils.get_args_raw(message)
        if not query:
            await utils.answer(message, self.strings["no_args"])
            return

        status = await utils.answer(
            message,
            self.strings["downloading"].format(query=query)
        )

        file = f"m_{message.id}.m4a"

        ydl_opts = {
            "format": "bestaudio/best",
            "default_search": "ytsearch1",
            "outtmpl": file,
            "quiet": True,
            "noprogress": True,
            "nocheckcertificate": True,
            "extractor_args": {
                "youtube": {
                    "player_client": ["android", "ios"],
                    "skip": ["webpage", "hls"],
                }
            },
            "user_agent": "com.google.android.youtube/19.29.37 (Linux; Android 11)",
        }

        async def progress(current, total):
            if not hasattr(progress, "l"):
                progress.l = 0
            now = time.time()
            if now - progress.l < 2.5:
                return
            percent = int(current * 100 / total)
            bar = int(percent / 10)
            try:
                await status.edit(
                    f"📤 {'▰'*bar}{'▱'*(10-bar)} {percent}%"
                )
            except:
                pass
            progress.l = now

        try:
            def extract():
                with YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(
                        f"ytsearch1:{query}",
                        download=True
                    )
                    if "entries" in info:
                        info = info["entries"][0]
                    return info

            info = await asyncio.to_thread(extract)

            await message.client.send_file(
                message.chat_id,
                file,
                voice=False,
                attributes=None,
                caption=info.get("title", "Unknown"),
                reply_to=message.reply_to_msg_id,
                progress_callback=progress,
            )

            await status.delete()

        except Exception as e:
            text = str(e)
            if "403" in text or "PO-Token" in text:
                await status.edit(self.strings["blocked"])
            else:
                await status.edit(
                    self.strings["error"].format(e=text[:80])
                )
        finally:
            if os.path.exists(file):
                os.remove(file)
