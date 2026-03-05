# meta developer: @shaatimi
# requires: requests

from .. import loader, utils
import requests
from datetime import datetime

@loader.tds
class Weather(loader.Module):

    strings = {
        "name": "Weather",
        "invalid": "<b>❌ Укажите город.</b>",
        "error": "<b>Ошибка:</b> <code>{}</code>",
        "notfound": "<b>Город не найден:</b> <code>{}</code>",
    }

    strings_ru = {
        "weather_info": """{cloud_emoji} <b>Погода в {city}, {country}</b>

{temp_emoji} <b>Температура:</b> <code>{temp}°C</code>
{feels_emoji} <b>Ощущается:</b> <code>{feels}°C</code>

<blockquote expandable>
💧 <b>Влажность:</b> <code>{humidity}%</code>
{wind_emoji} <b>Ветер:</b> <code>{wind} м/с</code>
☁️ <b>Облачность:</b> <code>{clouds}%</code>
👁 <b>Видимость:</b> <code>{visibility} км</code>
📊 <b>Давление:</b> <code>{pressure} hPa</code>
🌅 <b>Восход:</b> <code>{sunrise}</code>
🌇 <b>Закат:</b> <code>{sunset}</code>
</blockquote>

<b>{description}</b>"""
    }

    strings_en = {
        "weather_info": """{cloud_emoji} <b>Weather in {city}, {country}</b>

{temp_emoji} <b>Temperature:</b> <code>{temp}°C</code>
{feels_emoji} <b>Feels like:</b> <code>{feels}°C</code>

<blockquote expandable>
💧 <b>Humidity:</b> <code>{humidity}%</code>
{wind_emoji} <b>Wind:</b> <code>{wind} m/s</code>
☁️ <b>Clouds:</b> <code>{clouds}%</code>
👁 <b>Visibility:</b> <code>{visibility} km</code>
📊 <b>Pressure:</b> <code>{pressure} hPa</code>
🌅 <b>Sunrise:</b> <code>{sunrise}</code>
🌇 <b>Sunset:</b> <code>{sunset}</code>
</blockquote>

<b>{description}</b>"""
    }

    def get_temp_emoji(self, temp):
        if temp <= -10:
            return "🥶"
        elif temp <= 0:
            return "❄️"
        elif temp <= 10:
            return "🌬"
        elif temp <= 20:
            return "🌤"
        elif temp <= 30:
            return "☀️"
        else:
            return "🔥"

    def get_feels_emoji(self, temp, feels):
        diff = feels - temp
        if diff >= 5:
            return "🥵"
        elif diff <= -5:
            return "🥶"
        else:
            return "🙂"

    def get_wind_emoji(self, speed):
        if speed <= 2:
            return "🍃"
        elif speed <= 7:
            return "🌬"
        elif speed <= 15:
            return "💨"
        else:
            return "🌪"

    def get_cloud_emoji(self, clouds):
        if clouds <= 20:
            return "☀️"
        elif clouds <= 50:
            return "🌤"
        elif clouds <= 80:
            return "⛅"
        else:
            return "☁️"

    @loader.command(
        ru_doc="Посмотреть погоду в указанном городе",
        en_doc="Check the weather in the specified city",
    )
    async def weather(self, message):
        args = utils.get_args_raw(message)
        if not args:
            await utils.answer(message, self.strings["invalid"])
            return

        lang = self.get_lang(message) 
        city = args
        api_key = "934e9392018dd900103f54e50b870c02"

        try:
            r = requests.get(
                "https://api.openweathermap.org/data/2.5/weather",
                params={"q": city, "appid": api_key, "units": "metric", "lang": "en"},
                timeout=5
            )
            data = r.json()
            if data.get("cod") != 200:
                await utils.answer(message, self.strings["notfound"].format(city))
                return

            name = data["name"]
            country = data["sys"]["country"]

            temp = round(data["main"]["temp"])
            feels = round(data["main"]["feels_like"])
            humidity = data["main"]["humidity"]
            pressure = data["main"]["pressure"]
            wind = data["wind"]["speed"]
            clouds = data["clouds"]["all"]
            visibility = data.get("visibility", 0) // 1000
            description = data["weather"][0]["description"].capitalize()
            sunrise = datetime.fromtimestamp(data["sys"]["sunrise"]).strftime("%H:%M")
            sunset = datetime.fromtimestamp(data["sys"]["sunset"]).strftime("%H:%M")

            temp_emoji = self.get_temp_emoji(temp)
            feels_emoji = self.get_feels_emoji(temp, feels)
            wind_emoji = self.get_wind_emoji(wind)
            cloud_emoji = self.get_cloud_emoji(clouds)

            if lang == "ru":
                template = self.strings_ru["weather_info"]
            else:
                template = self.strings_en["weather_info"]

            text = template.format(
                city=name,
                country=country,
                temp=temp,
                feels=feels,
                humidity=humidity,
                pressure=pressure,
                wind=wind,
                clouds=clouds,
                visibility=visibility,
                description=description,
                sunrise=sunrise,
                sunset=sunset,
                temp_emoji=temp_emoji,
                feels_emoji=feels_emoji,
                wind_emoji=wind_emoji,
                cloud_emoji=cloud_emoji
            )

            await utils.answer(message, text)

        except Exception as e:
            await utils.answer(message, self.strings["error"].format(e))

    def get_lang(self, message):
        if hasattr(message.client, "lang"):
            lang = getattr(message.client, "lang", "en")
            if lang.lower().startswith("ru"):
                return "ru"
            elif lang.lower().startswith("jp"):
                return "jp"
        return "en"
