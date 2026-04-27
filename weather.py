# meta developer: @shaatimi
# requires: requests

from .. import loader, utils
import asyncio
import html
import requests
import time
from datetime import datetime
from urllib.parse import quote


@loader.tds
class Weather(loader.Module):
    strings = {
        "name": "Weather",
        "invalid": "<b>❌ Укажите город.</b>",
        "error": "<b>Ошибка:</b> <code>{}</code>",
        "notfound": "<b>Город не найден:</b> <code>{}</code>",
        "badjson": "<b>Ошибка:</b> <code>Некорректный ответ сервиса</code>",
        "weather_info": """{icon} <b>{location}</b>

<blockquote>
<b>{desc}</b>

🌡 <b>Сейчас:</b> <code>{temp}°C</code> {temp_emoji}
🤍 <b>Ощущается:</b> <code>{feels}°C</code> {feels_emoji}
📈 <b>Средняя сегодня:</b> <code>{avg}°C</code>
📉 <b>Мин / макс:</b> <code>{min}°C / {max}°C</code>

💧 <b>Влажность:</b> <code>{humidity}%</code>
📊 <b>Давление:</b> <code>{pressure} hPa</code>
🌬 <b>Ветер:</b> <code>{wind_ms} м/с</code> (<code>{wind_kmh} км/ч</code>) {wind_emoji}
🧭 <b>Направление:</b> <code>{winddir}</code>
☁️ <b>Облачность:</b> <code>{clouds}%</code>
👁 <b>Видимость:</b> <code>{visibility} км</code>
☔ <b>Осадки:</b> <code>{precip} мм</code>
☀️ <b>UV:</b> <code>{uv}</code>
</blockquote>

<blockquote>
🌅 <b>Восход:</b> <code>{sunrise}</code>
🌇 <b>Закат:</b> <code>{sunset}</code>
🕒 <b>Наблюдение:</b> <code>{obstime}</code>
</blockquote>""",
    }

    strings_ru = strings

    _desc_map = {
        "Light drizzle": "Лёгкая морось",
        "Patchy light drizzle": "Местами лёгкая морось",
        "Patchy rain possible": "Возможен местами дождь",
        "Light rain": "Слабый дождь",
        "Moderate rain": "Умеренный дождь",
        "Heavy rain": "Сильный дождь",
        "Patchy light rain": "Местами слабый дождь",
        "Light rain shower": "Кратковременный слабый дождь",
        "Moderate rain at times": "Местами умеренный дождь",
        "Heavy rain at times": "Местами сильный дождь",
        "Thundery outbreaks possible": "Возможны грозовые разряды",
        "Thunderstorm": "Гроза",
        "Light snow": "Лёгкий снег",
        "Moderate snow": "Умеренный снег",
        "Heavy snow": "Сильный снег",
        "Patchy snow possible": "Возможен местами снег",
        "Blizzard": "Метель",
        "Sleet": "Мокрый снег",
        "Ice pellets": "Ледяная крупа",
        "Fog": "Туман",
        "Mist": "Дымка",
        "Freezing fog": "Гололёдный туман",
        "Cloudy": "Облачно",
        "Overcast": "Пасмурно",
        "Partly cloudy": "Переменная облачность",
        "Clear": "Ясно",
        "Sunny": "Солнечно",
        "Patchy light snow": "Местами лёгкий снег",
        "Patchy moderate snow": "Местами умеренный снег",
        "Patchy heavy snow": "Местами сильный снег",
        "Light sleet": "Лёгкий мокрый снег",
        "Moderate or heavy sleet": "Умеренный или сильный мокрый снег",
        "Light sleet showers": "Кратковременный лёгкий мокрый снег",
        "Moderate or heavy sleet showers": "Кратковременный умеренный или сильный мокрый снег",
        "Light showers of ice pellets": "Кратковременные слабые осадки ледяной крупы",
        "Moderate or heavy showers of ice pellets": "Кратковременные умеренные или сильные осадки ледяной крупы",
    }

    def _get_session(self):
        session = getattr(self, "_weather_session", None)
        if session is None:
            session = requests.Session()
            session.headers.update(
                {
                    "User-Agent": "Mozilla/5.0",
                    "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
                }
            )
            self._weather_session = session
        return session

    def _cache_get(self, key):
        cache = getattr(self, "_weather_cache", None)
        if not cache:
            return None
        item = cache.get(key)
        if not item:
            return None
        ts, data = item
        if time.monotonic() - ts > 120:
            cache.pop(key, None)
            return None
        return data

    def _cache_set(self, key, data):
        cache = getattr(self, "_weather_cache", None)
        if cache is None:
            cache = {}
            self._weather_cache = cache
        cache[key] = (time.monotonic(), data)

    def _first_value(self, value, default=None):
        if isinstance(value, list) and value:
            value = value[0]
        if isinstance(value, dict):
            return value.get("value", default)
        if value is None:
            return default
        return value

    def _text(self, value, default="—"):
        if value is None or value == "":
            return default
        return html.escape(str(value))

    def _num(self, value, digits=0, default="—"):
        try:
            value = float(value)
        except (TypeError, ValueError):
            return default
        if digits <= 0:
            return str(int(round(value)))
        return f"{value:.{digits}f}"

    def _temp_emoji(self, temp):
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

    def _feels_emoji(self, temp, feels):
        diff = feels - temp
        if diff >= 5:
            return "🥵"
        if diff <= -5:
            return "🥶"
        return "🙂"

    def _wind_emoji(self, speed_ms):
        if speed_ms <= 2:
            return "🍃"
        if speed_ms <= 5:
            return "🌬"
        if speed_ms <= 9:
            return "💨"
        return "🌪"

    def _cloud_emoji(self, clouds):
        if clouds <= 20:
            return "☀️"
        if clouds <= 50:
            return "🌤"
        if clouds <= 80:
            return "⛅"
        return "☁️"

    def _location_title(self, data, fallback):
        nearest = (data.get("nearest_area") or [{}])[0]
        parts = [
            self._first_value(nearest.get("areaName")),
            self._first_value(nearest.get("region")),
            self._first_value(nearest.get("country")),
        ]
        cleaned = []
        seen = set()
        for part in parts:
            if not part:
                continue
            key = str(part).strip().casefold()
            if key in seen:
                continue
            seen.add(key)
            cleaned.append(str(part).strip())
        if cleaned:
            return ", ".join(html.escape(x) for x in cleaned[:3])
        return html.escape(fallback)

    def _translate_desc(self, desc):
        text = (desc or "").strip()
        if not text:
            return "—"
        return self._desc_map.get(text, text).capitalize()

    def _parse_time(self, value):
        if not value:
            return "—"
        value = str(value).strip()
        formats = (
            "%Y-%m-%d %I:%M %p",
            "%Y-%m-%d %H:%M",
            "%I:%M %p",
            "%H:%M",
        )
        for fmt in formats:
            try:
                dt = datetime.strptime(value, fmt)
                if "%Y" in fmt:
                    return dt.strftime("%d.%m.%Y %H:%M")
                return dt.strftime("%H:%M")
            except ValueError:
                pass
        return value

    def _fetch_weather(self, city):
        key = city.casefold()
        cached = self._cache_get(key)
        if cached is not None:
            return cached

        session = self._get_session()
        url = f"https://wttr.in/{quote(city, safe='')}"
        response = session.get(
            url,
            params={"format": "j1", "lang": "ru"},
            timeout=(4, 10),
        )
        response.raise_for_status()
        data = response.json()
        self._cache_set(key, data)
        return data

    @loader.command(ru_doc="Показать погоду без API-ключа")
    async def weather(self, message):
        city = utils.get_args_raw(message).strip()
        if not city:
            await utils.answer(message, self.strings["invalid"])
            return

        try:
            data = await asyncio.to_thread(self._fetch_weather, city)
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

        current_list = data.get("current_condition") or []
        weather_list = data.get("weather") or []

        if not current_list or not weather_list:
            await utils.answer(message, self.strings["notfound"].format(html.escape(city)))
            return

        current = current_list[0]
        day = weather_list[0]
        astronomy = (day.get("astronomy") or [{}])[0]

        try:
            temp = int(float(current.get("temp_C", 0)))
            feels = int(float(current.get("FeelsLikeC", temp)))
            avg = int(float(day.get("avgtempC", temp)))
            min_temp = int(float(day.get("mintempC", temp)))
            max_temp = int(float(day.get("maxtempC", temp)))
            humidity = int(float(current.get("humidity", 0)))
            pressure = int(float(current.get("pressure", 0)))
            wind_kmh = float(current.get("windspeedKmph", 0))
            wind_ms = wind_kmh / 3.6
            clouds = int(float(current.get("cloudcover", 0)))
            visibility = float(current.get("visibility", 0))
            precip = float(current.get("precipMM", 0))
            uv = current.get("uvIndex", "—")
            winddir = current.get("winddir16Point") or current.get("winddirDegree") or "—"
            desc = self._translate_desc((current.get("weatherDesc") or [{}])[0].get("value", "—"))
            obstime = current.get("localObsDateTime") or current.get("observation_time") or "—"
            sunrise = astronomy.get("sunrise") or "—"
            sunset = astronomy.get("sunset") or "—"
        except Exception as e:
            await utils.answer(message, self.strings["error"].format(html.escape(str(e))))
            return

        location = self._location_title(data, city)
        icon = self._cloud_emoji(clouds)
        temp_emoji = self._temp_emoji(temp)
        feels_emoji = self._feels_emoji(temp, feels)
        wind_emoji = self._wind_emoji(wind_ms)

        text = self.strings["weather_info"].format(
            icon=icon,
            location=location,
            desc=self._text(desc),
            temp=temp,
            feels=feels,
            avg=avg,
            min=min_temp,
            max=max_temp,
            humidity=humidity,
            pressure=pressure,
            wind_ms=self._num(wind_ms, 1),
            wind_kmh=self._num(wind_kmh, 0),
            winddir=self._text(winddir),
            clouds=clouds,
            visibility=self._num(visibility, 0),
            precip=self._num(precip, 1),
            uv=self._text(uv),
            sunrise=self._parse_time(sunrise),
            sunset=self._parse_time(sunset),
            obstime=self._parse_time(obstime),
            temp_emoji=temp_emoji,
            feels_emoji=feels_emoji,
            wind_emoji=wind_emoji,
        )

        await utils.answer(message, text)
