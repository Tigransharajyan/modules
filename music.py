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
    """Music downloader"""
    strings = {
        "name": "MusicDL",
        "no_query": "❌ Укажи название трека.",
        "not_found": "❌ Трек не найден.",
        "downloading": "⏳ Скачиваю трек: <b>{name}</b>",
        "sent": "✅ Трек отправлен",
        "error": "❌ Ошибка:\n<code>{e}</code>",
    }

    @loader.command(
        ru_doc="<название> — найти трек и прислать в Telegram с обложкой",
        en_doc="<track name> — find track and send audio with cover"
    )
    async def mfind(self, message):
        query = utils.get_args_raw(message)
        if not query:
            await utils.answer(message, self.strings["no_query"])
            return

        status = await utils.answer(message, self.strings["downloading"].format(name=query))
        file_temp = f"temp_track.m4a"
        card_name = "cover.jpg"

        try:
            ydl_opts = {
                "format": "bestaudio/best",
                "outtmpl": file_temp,
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

            display_name = f"{track_title} - {track_artist}"

            if thumbnail_url:
                async with aiohttp.ClientSession() as session:
                async with session.get(thumbnail_url) as resp:
                    img_data = await resp.read()

                img = Image.open(BytesIO(img_data)).convert("RGB")

                new_height = img.height + 50
                new_img = Image.new("RGB", (img.width, new_height), (0,0,0))
                new_img.paste(img, (0,0))
                draw = ImageDraw.Draw(new_img)
                font = ImageFont.load_default()
                text = display_name

                bbox = draw.textbbox((0,0), text, font=font)
                text_width = bbox[2] - bbox[0]
                text_height = bbox[3] - bbox[1]

                draw.rectangle([(0, img.height), (img.width, new_height)], fill=(0,0,0,200))
                draw.text(((img.width - text_width)//2, img.height + (50 - text_height)//2), text, font=font, fill="white")

                card = BytesIO()
                card.name = card_name
                new_img.save(card, "JPEG")
                card.seek(0)
            else:
                card = None

            await message.client.send_file(
                message.chat.id,
                file=file_temp,
                thumb=card,
                caption=f"<b>{display_name}</b>\n<a href='{track_url}'>Открыть на YouTube</a>",
                reply_to=message.reply_to_msg_id,
                force_document=True,
            )

            await status.delete()
            if os.path.exists(file_temp):
                os.remove(file_temp)

        except Exception as e:
            await utils.answer(message, self.strings["error"].format(e=e))
