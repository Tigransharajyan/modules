# meta developer: @shaatimi
# requires: requests

from .. import loader, utils
import asyncio
import requests
from io import BytesIO
from html import escape
from difflib import SequenceMatcher, get_close_matches
from urllib.parse import quote_plus

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
        self.cache = {}

    async def safe_send(self, message, text, parse_mode="html", file=None, reply_to=None):
        try:
            if file:
                return await message.client.send_file(message.chat_id, file, caption=text, parse_mode=parse_mode, reply_to=reply_to)
            else:
                return await message.client.send_message(message.chat_id, text, parse_mode=parse_mode, reply_to=reply_to)
        except Exception:
            try:
                if file:
                    return await message.client.send_file(message.chat_id, file, caption=text, parse_mode=parse_mode, reply_to=reply_to)
                else:
                    return await utils.answer(message, text)
            except Exception:
                return None

    async def safe_delete(self, msg_obj):
        try:
            if msg_obj and hasattr(msg_obj, "delete"):
                await msg_obj.delete()
        except Exception:
            pass

    @loader.command(ru_doc="<API_KEY> — сохранить OMDB API key")
    async def fauth(self, message):
        key = utils.get_args_raw(message).strip()
        if not key:
            await utils.answer(message, "Использование: .fauth <OMDB_API_KEY>")
            return
        self.config["OMDB_API_KEY"] = key
        await utils.answer(message, self.strings["saved"])

    @loader.command(ru_doc="— показать статус ключа")
    async def fkey(self, message):
        key = self.config.get("OMDB_API_KEY") or ""
        if not key:
            await utils.answer(message, self.strings["fkey_none"])
            return
        masked = (key[:4] + "..." + key[-4:]) if len(key) > 8 else ("*" * len(key))
        await utils.answer(message, self.strings["fkey_show"].format(masked=escape(masked)))

    @loader.command(ru_doc="— удалить ключ из конфигурации")
    async def funset(self, message):
        self.config["OMDB_API_KEY"] = ""
        await utils.answer(message, self.strings["funset_ok"])

    def translate_to_ru(self, text):
        try:
            if not text or text.strip() == "" or len(text) < 3:
                return text
            q = quote_plus(text)
            url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl=en&tl=ru&dt=t&q={q}"
            r = requests.get(url, timeout=6)
            if r.status_code == 200:
                js = r.json()
                parts = []
                for seg in js[0]:
                    if seg and seg[0]:
                        parts.append(seg[0])
                return "".join(parts).replace("  ", " ")
        except Exception:
            pass
        return text

    def best_match_from_search(self, query, search_results):
        titles = [r.get("Title", "") for r in search_results]
        if not titles:
            return None
        matches = get_close_matches(query, titles, n=1, cutoff=0.6)
        if matches:
            for r in search_results:
                if r.get("Title", "") == matches[0]:
                    return r
        best = None
        best_ratio = 0.0
        q = query.lower()
        for r in search_results:
            t = r.get("Title", "").lower()
            ratio = SequenceMatcher(None, q, t).ratio()
            if ratio > best_ratio:
                best_ratio = ratio
                best = r
        return best if best_ratio >= 0.4 else None

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
        try:
            params2 = {"apikey": api_key, "s": query, "r": "json"}
            r2 = requests.get(url, params=params2, timeout=10)
            if r2.status_code == 200:
                js2 = r2.json()
                if js2.get("Response") == "True" and js2.get("Search"):
                    candidate = self.best_match_from_search(query, js2.get("Search", []))
                    if candidate:
                        imdbid = candidate.get("imdbID")
                        if imdbid:
                            r3 = requests.get(url, params={"apikey": api_key, "i": imdbid, "plot": "full", "r": "json"}, timeout=10)
                            if r3.status_code == 200:
                                return r3.json()
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

    async def count_episodes(self, api_key, imdb_id, total_seasons):
        if not imdb_id or not str(total_seasons).isdigit():
            return "—"
        ts = int(total_seasons)
        if ts <= 0:
            return "—"
        if ts > 60:
            return "—"
        total = 0
        for s in range(1, ts + 1):
            season = await asyncio.to_thread(self.fetch_season, api_key, imdb_id, s)
            if season and season.get("Episodes"):
                total += len(season.get("Episodes"))
            else:
                pass
        return str(total) if total > 0 else "—"

    @loader.command(ru_doc=".film <название> — информация о фильме/сериале")
    async def film(self, message):
        q = utils.get_args_raw(message).strip()
        if not q:
            await utils.answer(message, self.strings["no_query"])
            return
        api_key = self.config.get("OMDB_API_KEY") or ""
        if not api_key:
            await utils.answer(message, self.strings["no_api"])
            return
        status = await self.safe_send(message, self.strings["searching"].format(q=escape(q)))
        try:
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
            
            title = data.get("Title", "—")
            year = data.get("Year", "—")
            kind = data.get("Type", "movie")
            runtime = data.get("Runtime", "—")
            genre = data.get("Genre", "—")
            director = data.get("Director", "—")
            writers = data.get("Writer", "—")
            country = data.get("Country", "—")
            language = data.get("Language", "—")
            awards = data.get("Awards", "—")
            imdb_rating = data.get("imdbRating", "—")
            metascore = data.get("Metascore", "—")
            rated = data.get("Rated", "—")
            production = data.get("Production", "—")
            boxoffice = data.get("BoxOffice", "—")
            website = data.get("Website", "—")
            poster = data.get("Poster", "")
            imdb_id = data.get("imdbID", "")
            total_seasons = data.get("totalSeasons", "—") if kind == "series" else "—"
            plot_en = data.get("Plot", "—")
            plot = await asyncio.to_thread(self.translate_to_ru, plot_en) if plot_en and plot_en != "N/A" else plot_en
            episodes_total = await self.count_episodes(api_key, imdb_id, total_seasons) if kind == "series" else "—"
            imdb_link = f"https://www.imdb.com/title/{imdb_id}/" if imdb_id else ""
            trailer_search = f"https://www.youtube.com/results?search_query={quote_plus(title + ' trailer')}"
            
            parts = []
            parts.append(f"<emoji document_id='5258217809250372293'>✨</emoji> <b>{escape(title)}</b> ({escape(year)})")
            parts.append(f"{'<b>Тип:</b> Сериал' if kind == 'series' else '<b>Тип:</b> Фильм'}")
            
            if plot and plot not in ("N/A", ""):
                parts.append("")
                parts.append(f"<blockquote expandable>{escape(plot)}</blockquote>")
            
            def add_if(v, label, emoji_id):
                if v and v not in ("N/A", "-", "—"):
                    parts.append(f"<emoji document_id='{emoji_id}'>•</emoji> {label}: {escape(v)}")

            add_if(genre, "Жанр", "5454156248813432363")
            add_if(director, "Режиссёр", "5375464961822695044")
            add_if(writers, "Сценарий", "5375464961822695044")
            
            if country or language:
                cl = f"{country or '—'} / {language or '—'}"
                add_if(cl, "Страна / Язык", "5188381825701021648")
            
            add_if(awards, "Награды", "5359664288241829619")
            add_if(runtime, "Длительность", "5454074580010295588")
            add_if(total_seasons if kind == "series" else None, "Сезонов", "5258396243666681152")
            add_if(episodes_total if kind == "series" else None, "Эпизодов", "5258396243666681152")
            add_if(imdb_rating if imdb_rating and imdb_rating != "N/A" else None, "IMDb", "5363926570836699898")
            add_if(metascore if metascore and metascore != "N/A" else None, "Metascore", "5363926570836699898")
            add_if(rated, "Рейтинг", "5274046919809704653")
            
            if imdb_id:
                parts.append(f"<emoji document_id='5271604874419647061'>🔗</emoji> <b>Ссылка:</b> <a href='{imdb_link}'>IMDb</a>")
            parts.append(f"<emoji document_id='5271604874419647061'>🎬</emoji> <b>Трейлер:</b> <a href='{trailer_search}'>Поиск на YouTube</a>")
            
            details = "\n".join(parts)
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
            await self.safe_send(message, details, reply_to=message.reply_to_msg_id)
            await self.safe_delete(status)
        except Exception as e:
            await self.safe_delete(status)
            await self.safe_send(message, self.strings["error"].format(e=escape(str(e))))
