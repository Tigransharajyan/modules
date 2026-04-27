# meta developer: @shaatimi
# requires: requests

from .. import loader, utils
import asyncio
import html
import os
import requests
from datetime import datetime


@loader.tds
class Weather(loader.Module):
    strings = {
        "name": "Weather",
        "invalid": "<b>❌ Укажите город.</b>",
        "nokey": "<b>❌ Не задан API ключ.</b>\n<code>OPENWEATHER_API_KEY</code>",
        "error": "<b>Ошибка:</b> <code>{}</code>",
        "notfound": "<b>Город не найден:</b> <code>{}</code>",
        "badjson": "<b>Ошибка:</b> <code>Некорректный ответ API</code>",
        "weather_info": """{cloud_emoji} <b>{city}, {country}</b>

<code>{description}</code>

🌡 <b>Температура:</b> <code>{temp}°C</code> {temp_emoji}
🤍 <b>Ощущается:</b> <code>{feels}°C</code> {feels_emoji}
📉 <b>Мин/макс:</b> <code>{temp_min}°C / {temp_max}°C</code>

💧 <b>Влажность:</b> <code>{humidity}%</code>
📊 <b>Давление:</b> <code>{pressure} hPa</code>
🌬 <b>Ветер:</b> <code>{wind} м/с</code>{gust_part}
🧭 <b>Направление:</b> <code>{wind_dir}</code>
☁️ <b>Облачность:</b> <code>{clouds}%</code>
👁 <b>Видимость:</b> <code>{visibility} км</code>
📍 <b>Координаты:</b> <code>{lat}, {lon}</code>

🌅 <b>Восход:</b> <code>{sunrise}</code>
🌇 <b>Закат:</b> <code>{sunset}</code>
🕒 <b>Обновлено:</b> <code>{updated}</code>""",
    }
    strings_ru = strings

    def _api_key(self):
        return os.getenv("OPENWEATHER_API_KEY") or os.getenv("WEATHER_API_KEY")

    def _get_temp_emoji(self, temp):
        if temp <= -10:
            return "🥶"
        if temp <= 0:
            return "❄️"
        if temp <= 10:
            return "🌬"
        if temp <= 20:
            return "🌤"
        if temp <= 30:
            return "☀️"
        return "🔥"

    def _get_feels_emoji(self, temp, feels):
        diff = feels - temp
        if diff >= 5:
            return "🥵"
        if diff <= -5:
            return "🥶"
        return "🙂"

    def _get_wind_emoji(self, speed):
        if speed <= 2:
            return "🍃"
        if speed <= 7:
            return "🌬"
        if speed <= 15:
            return "💨"
        return "🌪"

    def _get_cloud_emoji(self, clouds):
        if clouds <= 20:
            return "☀️"
        if clouds <= 50:
            return "🌤"
        if clouds <= 80:
            return "⛅"
        return "☁️"

    def _wind_dir(self, deg):
        if deg is None:
            return "—"
        dirs = ("N", "NE", "E", "SE", "S", "SW", "W", "NW")
        idx = int(((float(deg) + 22.5) % 360) // 45)
        return dirs[idx]

    def _fmt_time(self, ts, offset):
        return datetime.utcfromtimestamp(int(ts) + int(offset)).strftime("%H:%M")

    def _fmt_dt(self, ts, offset):
        return datetime.utcfromtimestamp(int(ts) + int(offset)).strftime("%d.%m.%Y %H:%M")

    def _fetch_weather(self, city, api_key):
        response = requests.get(
            "https://api.openweathermap.org/data/2.5/weather",
            params={
                "q": city,
                "appid": api_key,
                "units": "metric",
                "lang": "ru",
            },
            timeout=10,
        )
        try:
            return response.json()
        except Exception:
            raise ValueError("bad json")

    def _num(self, value, digits=0):
        if value is None:
            return "—"
        if digits == 0:
            return str(int(round(float(value))))
        return f"{float(value):.{digits}f}"

    @loader.command(ru_doc="Посмотреть погоду в указанном городе")
    async def weather(self, message):
        city = utils.get_args_raw(message).strip()
        if not city:
            await utils.answer(message, self.strings["invalid"])
            return

        api_key = self._api_key()
        if not api_key:
            await utils.answer(message, self.strings["nokey"])
            return

        try:
            data = await asyncio.to_thread(self._fetch_weather, city, api_key)
        except requests.Timeout:
            await utils.answer(message, self.strings["error"].format("Timeout"))
            return
        except requests.RequestException as e:
            await utils.answer(message, self.strings["error"].format(html.escape(str(e))))
            return
        except ValueError:
            await utils.answer(message, self.strings["badjson"])
            return
        except Exception as e:
            await utils.answer(message, self.strings["error"].format(html.escape(str(e))))
            return

        cod = data.get("cod")
        if str(cod) != "200":
            msg = data.get("message", city)
            await utils.answer(
                message,
                self.strings["notfound"].format(html.escape(str(msg))),
            )
            return

        try:
            name = html.escape(str(data.get("name", city)))
            country = html.escape(str(data.get("sys", {}).get("country", "—")))
            main = data.get("main", {})
            wind = data.get("wind", {})
            clouds = data.get("clouds", {})
            sys = data.get("sys", {})
            coord = data.get("coord", {})
            weather = (data.get("weather") or [{}])[0]
            timezone = int(data.get("timezone", 0))

            temp = round(float(main.get("temp", 0)))
            feels = round(float(main.get("feels_like", temp)))
            temp_min = round(float(main.get("temp_min", temp)))
            temp_max = round(float(main.get("temp_max", temp)))
            humidity = int(main.get("humidity", 0))
            pressure = int(main.get("pressure", 0))
            wind_speed = float(wind.get("speed", 0))
            wind_deg = wind.get("deg")
            wind_gust = wind.get("gust")
            cloudiness = int(clouds.get("all", 0))
            visibility_m = int(data.get("visibility", 0))
            visibility_km = f"{visibility_m / 1000:.1f}"

            description = html.escape(str(weather.get("description", "—")).capitalize())
            temp_emoji = self._get_temp_emoji(temp)
            feels_emoji = self._get_feels_emoji(temp, feels)
            wind_emoji = self._get_wind_emoji(wind_speed)
            cloud_emoji = self._get_cloud_emoji(cloudiness)
            gust_part = f" • <b>порывы:</b> <code>{self._num(wind_gust, 1)} м/с</code>" if wind_gust is not None else ""
            wind_dir = self._wind_dir(wind_deg)

            sunrise = self._fmt_time(sys.get("sunrise", 0), timezone) if sys.get("sunrise") else "—"
            sunset = self._fmt_time(sys.get("sunset", 0), timezone) if sys.get("sunset") else "—"
            updated = self._fmt_dt(data.get("dt", 0), timezone) if data.get("dt") else "—"

            text = self.strings["weather_info"].format(
                city=name,
                country=country,
                description=description,
                temp=temp,
                feels=feels,
                temp_min=temp_min,
                temp_max=temp_max,
                humidity=humidity,
                pressure=pressure,
                wind=self._num(wind_speed, 1),
                gust_part=gust_part,
                wind_dir=html.escape(str(wind_dir)),
                clouds=cloudiness,
                visibility=visibility_km,
                lat=self._num(coord.get("lat"), 2),
                lon=self._num(coord.get("lon"), 2),
                sunrise=sunrise,
                sunset=sunset,
                updated=updated,
                temp_emoji=temp_emoji,
                feels_emoji=feels_emoji,
                wind_emoji=wind_emoji,
                cloud_emoji=cloud_emoji,
            )

            await utils.answer(message, text)
        except Exception as e:
            await utils.answer(message, self.strings["error"].format(html.escape(str(e))))
