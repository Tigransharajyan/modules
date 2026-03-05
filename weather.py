# meta developer: @shaatimi
# requires: aiohttp

from .. import loader, utils
import aiohttp
import datetime

@loader.tds
class Weather(loader.Module):
    strings = {
        "name": "Weather",
        "invalid_args": "<emoji document_id=5019523782004441717>❌</emoji> <b>Укажи город.</b>",
        "error": "<b>Error:</b> <code>{e}</code>",
    }

    API = "https://api.openweathermap.org/data/2.5/weather?q={city}&appid={key}&units=metric&lang=ru"
    API_KEY = "934e9392018dd900103f54e50b870c02"

    async def fetch(self, city):
        async with aiohttp.ClientSession() as session:
            async with session.get(self.API.format(city=city, key=self.API_KEY)) as resp:
                return await resp.json()

    @loader.command(ru_doc="Погода в городе")
    async def weather(self, message):
        city = utils.get_args_raw(message)
        if not city:
            await utils.answer(message, self.strings["invalid_args"])
            return

        try:
            data = await self.fetch(city)

            if data.get("cod") != 200:
                await utils.answer(
                    message,
                    f"<emoji document_id=5019523782004441717>❌</emoji> <b>Город не найден:</b> <code>{city}</code>",
                )
                return

            main = data["main"]
            wind = data["wind"]
            sys = data["sys"]
            clouds = data.get("clouds", {})
            visibility = data.get("visibility", 0) / 1000

            sunrise = datetime.datetime.fromtimestamp(sys["sunrise"]).strftime("%H:%M")
            sunset = datetime.datetime.fromtimestamp(sys["sunset"]).strftime("%H:%M")

            text = f"""
<emoji document_id=5884330496619450755>🌤</emoji> <b>{city.capitalize()}, {sys["country"]}</b>

<blockquote expandable>

<emoji document_id=5199707727475007907>🌡</emoji> <b>Температура:</b> <code>{main["temp"]}°C</code>
<emoji document_id=5470065809807003162>🤔</emoji> <b>Ощущается:</b> <code>{main["feels_like"]}°C</code>

<emoji document_id=6050944866580435869>💧</emoji> <b>Влажность:</b> <code>{main["humidity"]}%</code>
<emoji document_id=5305633803285823050>🧭</emoji> <b>Давление:</b> <code>{main["pressure"]} hPa</code>

<emoji document_id=5415843564280107382>🌀</emoji> <b>Ветер:</b> <code>{wind["speed"]} м/с</code>
<emoji document_id=5417937876232983047>☁️</emoji> <b>Облачность:</b> <code>{clouds.get("all",0)}%</code>

<emoji document_id=5370705313512225423>👁</emoji> <b>Видимость:</b> <code>{visibility} км</code>

<emoji document_id=5345981066311802120>🌅</emoji> <b>Восход:</b> <code>{sunrise}</code>
<emoji document_id=5345981066311802121>🌇</emoji> <b>Закат:</b> <code>{sunset}</code>

<emoji document_id=5210952531676504517>📋</emoji> <b>Описание:</b> <code>{data["weather"][0]["description"].capitalize()}</code>

</blockquote>
"""

            await utils.answer(message, text)

        except Exception as e:
            await utils.answer(message, self.strings["error"].format(e=e))
