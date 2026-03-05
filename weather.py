# meta developer: @shaatimi
# requires: aiohttp

from .. import loader, utils
import aiohttp
import datetime


@loader.tds
class Weather(loader.Module):
    strings = {
        "name": "Weather",
        "invalid_args": "<emoji document_id=5019523782004441717>❌</emoji> <b>Укажите город.</b>",
        "error": "<b>Ошибка:</b> <code>{e}</code>",
        "api_error": "<b>Город не найден:</b> <code>{city}</code>"
    }

    API = "https://api.openweathermap.org/data/2.5/weather"
    API_KEY = "934e9392018dd900103f54e50b870c02"

    @loader.command(
        ru_doc="Посмотреть погоду в указанном городе"
    )
    async def weather(self, message):
        city = utils.get_args_raw(message)

        if not city:
            await utils.answer(message, self.strings["invalid_args"])
            return

        params = {
            "q": city,
            "appid": self.API_KEY,
            "units": "metric",
            "lang": "ru"
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(self.API, params=params) as resp:
                    data = await resp.json()

            if data.get("cod") != 200:
                await utils.answer(
                    message,
                    self.strings["api_error"].format(city=city)
                )
                return

            name = data["name"]
            country = data["sys"]["country"]

            main = data["main"]
            temp = main["temp"]
            feels = main["feels_like"]
            humidity = main["humidity"]
            pressure = main["pressure"]

            wind = data["wind"]["speed"]
            clouds = data["clouds"]["all"]

            visibility = data.get("visibility", 0) / 1000

            description = data["weather"][0]["description"].capitalize()

            lat = data["coord"]["lat"]
            lon = data["coord"]["lon"]

            sunrise = datetime.datetime.fromtimestamp(
                data["sys"]["sunrise"]
            ).strftime("%H:%M")

            sunset = datetime.datetime.fromtimestamp(
                data["sys"]["sunset"]
            ).strftime("%H:%M")

            text = f"""
<blockquote expandable>

<emoji document_id=5884330496619450755>🌍</emoji> <b>{name}, {country}</b>

<emoji document_id=5199707727475007907>🌡️</emoji> <b>Температура:</b> <code>{temp}°C</code>  
🥶 <b>Ощущается как:</b> <code>{feels}°C</code>

<emoji document_id=6050944866580435869>💧</emoji> <b>Влажность:</b> <code>{humidity}%</code>  
🌬 <b>Ветер:</b> <code>{wind} м/с</code>

☁️ <b>Облачность:</b> <code>{clouds}%</code>  
👁 <b>Видимость:</b> <code>{visibility} км</code>

📊 <b>Давление:</b> <code>{pressure} hPa</code>

🌅 <b>Восход:</b> <code>{sunrise}</code>  
🌇 <b>Закат:</b> <code>{sunset}</code>

📍 <b>Координаты:</b> <code>{lat}, {lon}</code>

⛅ <b>Описание:</b> {description}

</blockquote>
"""

            await utils.answer(message, text)

        except Exception as e:
            await utils.answer(
                message,
                self.strings["error"].format(e=e)
            )
