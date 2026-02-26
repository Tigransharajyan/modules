# meta developer: @shaatimi
# requires: aiohttp

from .. import loader, utils
import aiohttp
import io


@loader.tds
class TikTok(loader.Module):
    strings_ru = {
        "name": "TikTok",
        "no_args": "❌ Укажи ссылку на видео TikTok.",
        "downloading": "⏬ Скачиваю видео без водяного знака…",
        "error": "❌ Не удалось скачать видео.",
    }

    strings = {
        "name": "TikTok",
        "no_args": "❌ Specify a TikTok video link.",
        "downloading": "⏬ Downloading video without watermark…",
        "error": "❌ Failed to download the video.",
    }

    @loader.command(
        ru_doc="Скачать видео из TikTok без водяного знака",
        en_doc="Download TikTok video without watermark",
    )
    async def tt(self, message):
        url = utils.get_args_raw(message)
        if not url:
            await utils.answer(message, self.strings["no_args"])
            return

        await utils.answer(message, self.strings["downloading"])

        api_url = "https://tikwm.com/api/"
        params = {"url": url}

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(api_url, params=params, timeout=20) as resp:
                    if resp.status != 200:
                        raise Exception("API error")

                    data = await resp.json()
                    video_url = data["data"]["play"]

                async with session.get(video_url, timeout=20) as video_resp:
                    video_bytes = await video_resp.read()

            video = io.BytesIO(video_bytes)
            video.name = "tiktok.mp4"

            await message.client.send_file(
                message.chat_id,
                video,
                reply_to=message.reply_to_msg_id,
            )

            await message.delete()

        except Exception:
            await utils.answer(message, self.strings["error"])
