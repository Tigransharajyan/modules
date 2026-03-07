# meta developer: @shaatimi
# requires: requests

from .. import loader, utils
import asyncio
import requests
from io import BytesIO
from html import escape

@loader.tds
class FilmModule(loader.Module):
    strings = {
        "name": "Film",
        "no_query": "❌ Укажи название. Пример: .film Inception",
        "no_api": "❌ API ключ не установлен. Сохрани ключ: .fauth <API_KEY>",
        "saved": "✅ Ключ сохранён.",
        "fkey_none": "🔒 Ключ не установлен.",
        "fkey_show": "🔑 Ключ: <code>{masked}</code> (источник: config)",
        "funset_ok": "✅ Ключ удалён из конфигурации.",
        "searching": "🔎 Ищу: <b>{q}</b> ...",
        "not_found": "❌ Ничего не найдено по запросу: <code>{q}</code>.",
        "error": "❌ Ошибка: <code>{e}</code>"
    }

    def __init__(self):
        self.config = loader.ModuleConfig("OMDB_API_KEY", "", lambda: "OMDb API key")
        self.cache = {}  # simple in-memory cache: {query_lower: data}

    # ---- Helper safe send / delete ----
    async def safe_send(self, message, text, parse_mode="html", file=None, reply_to=None):
        """
        Пытаемся ответить через utils.answer (редактирует),
        при ошибке -- посылаем новое сообщение напрямую через client.send_message / send_file.
        Возвращаем объект сообщения (если удалось).
        """
        try:
            if file:
                # если есть файл, отправляем через client.send_file (utils.answer не поддерживает file reliably)
                return await message.client.send_file(message.chat_id, file, caption=text, parse_mode=parse_mode, reply_to=reply_to)
            else:
                return await utils.answer(message, text)
        except Exception:
            try:
                if file:
                    return await message.client.send_file(message.chat_id, file, caption=text, parse_mode=parse_mode, reply_to=reply_to)
                else:
                    return await message.client.send_message(message.chat_id, text, parse_mode=parse_mode, reply_to=reply_to)
            except Exception:
                return None

    async def safe_delete(self, msg_obj):
        try:
            if msg_obj and hasattr(msg_obj, "delete"):
                await msg_obj.delete()
        except Exception:
            pass

    # ---- Commands ----
    @loader.command(ru_doc="<API_KEY> — сохранить OMDB API key")
    async def fauth(self, message):
        key = utils.get_args_raw(message).strip()
        if not key:
            return await utils.answer(message, "Использование: .fauth <OMDB_API_KEY>")
        self.config["OMDB_API_KEY"] = key
        await utils.answer(message, self.strings["saved"])

    @loader.command(ru_doc="— показать статус ключа")
    async def fkey(self, message):
        key = self.config.get("OMDB_API_KEY") or ""
        if not key:
            return await utils.answer(message, self.strings["fkey_none"])
        masked = (key[:4] + "..." + key[-4:]) if len(key) > 8 else ("*" * len(key))
        await utils.answer(message, self.strings["fkey_show"].format(masked=escape(masked)))

    @loader.command(ru_doc="— удалить ключ из конфигурации")
    async def funset(self, message):
        self.config["OMDB_API_KEY"] = ""
        await utils.answer(message, self.strings["funset_ok"])

    @loader.command(ru_doc="<название> — информация о фильме/сериале")
    async def film(self, message):
        q = utils.get_args_raw(message).strip()
        if not q:
            return await utils.answer(message, self.strings["no_query"])

        api_key = self.config.get("OMDB_API_KEY") or ""
        if not api_key:
            return await utils.answer(message, self.strings["no_api"])

        status = await self.safe_send(message, self.strings["searching"].format(q=escape(q)))
        try:
            # check cache first
            cache_key = q.lower()
            if cache_key in self.cache:
                data = self.cache[cache_key]
            else:
                data = await asyncio.to_thread(self.fetch_omdb_full, api_key, q)
                if data:
                    self.cache[cache_key] = data

            if not data or data.get("Response") != "True":
                await self.safe_delete(status)
                return await self.safe_send(message, self.strings["not_found"].format(q=escape(q)))

            # extract fields
            title = data.get("Title", "—")
            year = data.get("Year", "—")
            kind = data.get("Type", "movie")
            runtime = data.get("Runtime", "—")
            genre = data.get("Genre", "—")
            director = data.get("Director", "—")
            writers = data.get("Writer", "—")
            actors = data.get("Actors", "—")
            country = data.get("Country", "—")
            language = data.get("Language", "—")
            awards = data.get("Awards", "—")
            imdb_rating = data.get("imdbRating", "—")
            imdb_votes = data.get("imdbVotes", "—")
            metascore = data.get("Metascore", "—")
            rated = data.get("Rated", "—")
            production = data.get("Production", "—")
            boxoffice = data.get("BoxOffice", "—")
            website = data.get("Website", "—")
            poster = data.get("Poster", "")
            imdb_id = data.get("imdbID", "")
            total_seasons = data.get("totalSeasons", "—") if kind == "series" else "—"

            # estimate episodes count for series (if reasonable)
            episodes_total = "—"
            try:
                if kind == "series" and str(total_seasons).isdigit():
                    ts = int(total_seasons)
                    if 1 <= ts <= 12:
                        total = 0
                        for s in range(1, ts + 1):
                            season_data = await asyncio.to_thread(self.fetch_season, api_key, imdb_id, s)
                            if season_data and season_data.get("Episodes"):
                                total += len(season_data.get("Episodes"))
                        episodes_total = str(total) if total > 0 else "—"
                    else:
                        episodes_total = "много"
            except Exception:
                episodes_total = "—"

            imdb_link = f"https://www.imdb.com/title/{imdb_id}/" if imdb_id else ""
            trailer_search = f"https://www.youtube.com/results?search_query={requests.utils.requote_uri(title + ' trailer')}"

            details = (
                f"<b>{escape(title)}</b> ({escape(year)})\n"
                f"{'<b>Тип:</b> Сериал' if kind == 'series' else '<b>Тип:</b> Фильм'}\n\n"
                f"{escape(data.get('Plot','—'))}\n\n"
                f"<b>Жанр:</b> {escape(genre)}\n"
                f"<b>Режиссёр:</b> {escape(director)}\n"
                f"<b>Сценарий:</b> {escape(writers)}\n"
                f"<b>Актёры:</b> {escape(actors)}\n"
                f"<b>Страна / Язык:</b> {escape(country)} / {escape(language)}\n"
                f"<b>Награды:</b> {escape(awards)}\n"
                f"<b>Длительность:</b> {escape(runtime)}\n"
                f"<b>Сезонов:</b> {escape(str(total_seasons))}\n"
                f"<b>Эпизодов (примерно):</b> {escape(str(episodes_total))}\n"
                f"<b>IMDb:</b> {escape(imdb_rating)} ({escape(imdb_votes)} голосов)\n"
                f"<b>Metascore:</b> {escape(metascore)}\n"
                f"<b>Rated:</b> {escape(rated)}\n"
                f"<b>Production:</b> {escape(production)}\n"
                f"<b>BoxOffice:</b> {escape(boxoffice)}\n"
                f"<b>Сайт:</b> {escape(website)}\n"
                f"<b>Ссылка:</b> <a href='{imdb_link}'>IMDb</a>\n"
                f"<b>Трейлер:</b> <a href='{trailer_search}'>Поиск на YouTube</a>\n"
            )

            # send poster if available
            if poster and poster != "N/A":
                try:
                    resp = await asyncio.to_thread(requests.get, poster, timeout=10)
                    if getattr(resp, "status_code", None) == 200 and getattr(resp, "content", None):
                        bio = BytesIO(resp.content)
                        bio.name = f"{title}.jpg"
                        bio.seek(0)
                        await self.safe_send(message, details, file=bio, reply_to=message.reply_to_msg_id)
                        await self.safe_delete(status)
                        return
                except Exception:
                    pass

            # fallback: just send text
            await self.safe_send(message, details, reply_to=message.reply_to_msg_id)
            await self.safe_delete(status)

        except Exception as e:
            await self.safe_delete(status)
            await self.safe_send(message, self.strings["error"].format(e=escape(str(e))))

    # ---- HTTP helpers ----
    def fetch_omdb_full(self, api_key, query):
        url = "http://www.omdbapi.com/"
        params = {"apikey": api_key, "t": query, "plot": "full", "r": "json"}
        try:
            r = requests.get(url, params=params, timeout=10)
            if r.status_code == 200:
                js = r.json()
                if js.get("Response") == "True":
                    return js
        except Exception:
            pass
        # fallback search -> take first result by imdbID
        try:
            params2 = {"apikey": api_key, "s": query, "r": "json"}
            r2 = requests.get(url, params=params2, timeout=10)
            if r2.status_code == 200:
                js2 = r2.json()
                if js2.get("Response") == "True" and js2.get("Search"):
                    first = js2["Search"][0]
                    imdbid = first.get("imdbID")
                    if imdbid:
                        r3 = requests.get(url, params={"apikey": api_key, "i": imdbid, "plot": "full", "r": "json"}, timeout=10)
                        if r3.status_code == 200:
                            return r3.json()
        except Exception:
            pass
        return None

    def fetch_season(self, api_key, imdb_id, season_number):
        url = "http://www.omdbapi.com/"
        params = {"apikey": api_key, "i": imdb_id, "Season": season_number, "r": "json"}
        try:
            r = requests.get(url, params=params, timeout=10)
            if r.status_code == 200:
                return r.json()
        except Exception:
            pass
        return None
