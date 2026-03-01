# meta developer: @shaatimi
# requires: yt_dlp aiohttp Pillow

from .. import loader, utils
import asyncio
import aiohttp
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
from yt_dlp import YoutubeDL
import os

@loader.tds
class MusicDLModule(loader.Module):
    """Music downloader and last track info module"""
    strings = {
        "name": "MusicDL",
        "no_query": "❌ Укажи название трека.",
        "not_found": "❌ Трек не найден.",
        "downloading": "⏳ Скачиваю трек: <b>{name}</b>",
        "sent": "✅ Трек отправлен",
        "error": "❌ Ошибка:\n<code>{e}</code>",
        "last_text_empty": "❌ Нет информации о последнем треке.",
    }

    def __init__(self):
        self.last_track = {} 

    @loader.command(
        ru_doc=".mfind <название> — найти трек и прислать в Telegram с обложкой",
        en_doc=".mfind <track name> — find track and send audio with cover"
    )
    async def mfind(self, message):
        query = utils.get_args_raw(message)
        if not query:
            await utils.answer(message, self.strings["no_query"])
            return

        status = await utils.answer(message, self.strings["downloading"].format(name=query))
        file_name = f"{query}.m4a"
        card_name = "cover.jpg"

        try:
            ydl_opts = {
                "format": "bestaudio/best",
                "outtmpl": file_name,
                "quiet": True,
                "noplaylist": True,
            }

            with YoutubeDL(ydl_opts) as ydl:
                info = await asyncio.to_thread(ydl.extract_info, f"ytsearch1:{query}", download=True)

            track_info = info['entries'][0]
            track_title = track_info.get('title', query)
            track_artist = track_info.get('uploader', "Unknown Artist")
            thumbnail_url = track_info.get('thumbnails', [{}])[-1].get('url', None)
            track_url = track_info.get('webpage_url', None)

            self.last_track[message.chat.id] = {
                "title": track_title,
                "artist": track_artist,
                "url": track_url
            }

            if thumbnail_url:
                async with aiohttp.ClientSession() as session:
                    async with session.get(thumbnail_url) as resp:
                        img_data = await resp.read()
                img = Image.open(BytesIO(img_data)).convert("RGB")
                draw = ImageDraw.Draw(img)
                font = ImageFont.load_default()
                draw.rectangle([(0, img.height-40), (img.width, img.height)], fill=(0,0,0,180))
                draw.text((10, img.height-35), f"{track_title} - {track_artist}", font=font, fill="white")
                card = BytesIO()
                card.name = card_name
                img.save(card, "JPEG")
                card.seek(0)
            else:
                card = None

            caption = f"Исполнитель: {track_artist}\n<a href='{track_url}'>Открыть на YouTube</a>"

            await message.client.send_file(
                message.chat.id,
                file=file_name,
                thumb=card,
                caption=caption,
                reply_to=message.reply_to_msg_id
            )

            await status.delete()
            if os.path.exists(file_name):
                os.remove(file_name)

        except Exception as e:
            await utils.answer(message, self.strings["error"].format(e=e))

    @loader.command(
        ru_doc=".mtext — показать текст последнего трека в формате quote",
        en_doc=".mtext — show last track info in quote format"
    )
    async def mtext(self, message):
        info = self.last_track.get(message.chat.id)
        if not info:
            await utils.answer(message, self.strings["last_text_empty"])
            return

        lines = [
            f"<b>Название:</b> {info.get('title')}",
            f"<b>Исполнитель:</b> {info.get('artist')}",
            f"<b>Ссылка:</b> {info.get('url')}"
        ]
        quote_text = "\n".join([f"<code>{line}</code>" for line in lines])
        await utils.answer(message, quote_text)
