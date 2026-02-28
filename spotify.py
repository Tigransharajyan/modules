# meta developer: @shaatimi
# requires: spotipy aiohttp yt_dlp Pillow

from .. import loader, utils
import asyncio
import aiohttp
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
from yt_dlp import YoutubeDL
from spotipy import Spotify
from spotipy.oauth2 import SpotifyOAuth
import os

@loader.tds
class SpotifyDLModule(loader.Module):
    strings = {
        "name": "SpotifyDL",
        "no_query": "❌ Укажи название трека.",
        "not_found": "❌ Трек не найден.",
        "downloading": "⏳ Скачиваю трек: <b>{name}</b>",
        "sent": "✅ Трек отправлен",
        "not_auth": "❌ Используй .sauth для авторизации",
        "error": "❌ Ошибка:\n<code>{e}</code>",
    }

    def __init__(self):
        self.sp = None
        self.auth_manager = None

    @loader.command(
        ru_doc=".sauth <client_id> <client_secret> <redirect_url> — авторизация в Spotify",
        en_doc=".sauth <client_id> <client_secret> <redirect_url> — authorize Spotify"
    )
    async def sauth(self, message):
        args = utils.get_args_raw(message).split()
        if len(args) != 3:
            await utils.answer(message, "❌ Используй: .sauth <client_id> <client_secret> <redirect_url>")
            return
        client_id, client_secret, redirect_uri = args
        try:
            self.auth_manager = SpotifyOAuth(
                client_id=client_id,
                client_secret=client_secret,
                redirect_uri=redirect_uri,
                scope="user-read-playback-state"
            )
            self.sp = Spotify(auth_manager=self.auth_manager)
            me = await asyncio.to_thread(self.sp.current_user)
            user = me["display_name"]
            await utils.answer(message, f"✅ Авторизация пройдена. Пользователь: {user}")
        except Exception as e:
            await utils.answer(message, self.strings["error"].format(e=e))

    @loader.command(
        ru_doc=".sfind <название> — найти трек и прислать в Telegram с обложкой",
        en_doc=".sfind <track name> — find track and send to Telegram with cover"
    )
    async def sfind(self, message):
        if not self.sp:
            await utils.answer(message, self.strings["not_auth"])
            return

        query = utils.get_args_raw(message)
        if not query:
            await utils.answer(message, self.strings["no_query"])
            return

        try:
            results = await asyncio.to_thread(self.sp.search, query, type="track", limit=1)
            items = results.get("tracks", {}).get("items", [])
            if not items:
                await utils.answer(message, self.strings["not_found"])
                return

            track = items[0]
            name = track["name"]
            artist = ", ".join([a["name"] for a in track["artists"]])
            album = track["album"]["name"]
            img_url = track["album"]["images"][0]["url"]
            spotify_url = track["external_urls"]["spotify"]
            yt_query = f"{name} {artist} audio"

            status = await utils.answer(message, self.strings["downloading"].format(name=name))

            file_name = f"{artist} - {name}.m4a"
            ydl_opts = {
                "format": "bestaudio/best",
                "outtmpl": file_name,
                "quiet": True,
                "noplaylist": True,
            }

            with YoutubeDL(ydl_opts) as ydl:
                await asyncio.to_thread(ydl.extract_info, f"ytsearch1:{yt_query}", download=True)

            async with aiohttp.ClientSession() as session:
                async with session.get(img_url) as resp:
                    img_data = await resp.read()

            img = Image.open(BytesIO(img_data)).convert("RGB")
            draw = ImageDraw.Draw(img)
            font = ImageFont.load_default()
            draw.rectangle([(0, img.height-40), (img.width, img.height)], fill=(0,0,0,180))
            draw.text((10, img.height-35), f"{artist} - {name}", font=font, fill="white")

            card = BytesIO()
            card.name = "cover.jpg"
            img.save(card, "JPEG")
            card.seek(0)

            caption = f"Исполнитель: {artist}\nАльбом: {album}\n<a href='{spotify_url}'>Открыть в Spotify</a>"

            await message.client.send_file(
                message.chat.id,
                file=file_name,
                thumb=card,
                caption=caption,
                voice=False,
                reply_to=message.reply_to_msg_id
            )

            await status.delete()
            if os.path.exists(file_name):
                os.remove(file_name)

        except Exception as e:
            await utils.answer(message, self.strings["error"].format(e=e))
