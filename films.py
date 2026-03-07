# meta developer: @shaatimi
# requires: requests Pillow

from .. import loader, utils
import asyncio
import os
import requests
from io import BytesIO
from PIL import Image
from html import escape
import json

@loader.tds
class FilmModule(loader.Module):
    strings = {
        "name": "Film",
        "no_query": "❌ Укажи название фильма или сериала. Пример: .film Inception",
        "no_api": "❌ Не указан OMDB API key. Сохрани ключ командой .fauth <API_KEY> или установи OMDB_API_KEY в окружении.",
        "not_found": "❌ Ничего не найдено по запросу: <code>{q}</code>.",
        "error": "❌ Ошибка: <code>{e}</code>",
        "result_prefix": "<b>{title}</b> ({year})\n{type_line}\n\n",
        "details_template": (
            "{plot}\n\n"
            "<b>Жанр:</b> {genre}\n"
            "<b>Режиссёр:</b> {director}\n"
            "<b>Актёры:</b> {actors}\n"
            "<b>Страна / Язык:</b> {country} / {language}\n"
            "<b>Награды:</b> {awards}\n"
            "<b>Длительность:</b> {runtime}\n"
            "<b>Сезонов:</b> {seasons}\n"
            "<b>IMDb:</b> {imdb_rating} ({imdb_votes} голосов)\n"
            "<b>Metascore:</b> {metascore}\n"
            "<b>Ссылка:</b> <a href='{imdb_link}'>IMDb</a>\n"
        ),
        "fauth_set": "✅ Ключ сохранён локально.",
        "fauth_usage": "Использование: .fauth <OMDB_API_KEY>",
        "fkey_none": "🔒 Ключ не установлен (ни в окружении, ни в локальном файле).",
        "fkey_show": "🔑 Ключ установлен: <code>{masked}</code> (источник: {source})",
        "funset_ok": "✅ Локальный ключ удалён.",
    }

    def __init__(self):
        self.config_file = os.path.join(os.path.dirname(__file__), "film_config.json")
        self.omdb_key = None
        self.load_config()

    def load_config(self):
        env_key = os.getenv("OMDB_API_KEY")
        if env_key:
            self.omdb_key = env_key
            self.config_source = "env"
            return
        # fallback to local file
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, "r", encoding="utf-8") as f:
                    js = json.load(f)
                key = js.get("omdb_key")
                if key:
                    self.omdb_key = key
                    self.config_source = "file"
                    return
        except Exception:
            pass
        self.omdb_key = None
        self.config_source = None

    def save_config(self, key):
        try:
            js = {"omdb_key": key}
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(js, f)
            os.chmod(self.config_file, 0o600)
            self.omdb_key = key
            self.config_source = "file"
            return True
        except Exception:
            return False

    def remove_config(self):
        try:
            if os.path.exists(self.config_file):
                os.remove(self.config_file)
            # if env has key, keep using env on reload
            env_key = os.getenv("OMDB_API_KEY")
            if env_key:
                self.omdb_key = env_key
                self.config_source = "env"
            else:
                self.omdb_key = None
                self.config_source = None
            return True
        except Exception:
            return False

    @loader.command(ru_doc=".fauth <API_KEY> — сохранить OMDB API key локально")
    async def fauth(self, message):
        args = utils.get_args_raw(message).strip()
        if not args:
            await utils.answer(message, self.strings["fauth_usage"])
            return
        key = args.split()[0].strip()
        ok = await asyncio.to_thread(self.save_config, key)
        if ok:
            await utils.answer(message, self.strings["fauth_set"])
        else:
            await utils.answer(message, self.strings["error"].format(e="Не удалось сохранить ключ (права/файловая система)"))

    @loader.command(ru_doc=".fkey — показать статус ключа (скрытую форму)")
    async def fkey(self, message):
        self.load_config()
        if not self.omdb_key:
            await utils.answer(message, self.strings["fkey_none"])
            return
        masked = self.omdb_key[:4] + "..." + self.omdb_key[-4:] if len(self.omdb_key) > 8 else "****"
        await utils.answer(message, self.strings["fkey_show"].format(masked=escape(masked), source=self.config_source or "unknown"))

    @loader.command(ru_doc=".funset — удалить локально сохранённый ключ")
    async def funset(self, message):
        ok = await asyncio.to_thread(self.remove_config)
        if ok:
            await utils.answer(message, self.strings["funset_ok"])
        else:
            await utils.answer(message, self.strings["error"].format(e="Не удалось удалить локальный файл"))

    @loader.command(ru_doc=".film <название> — информация о фильме/сериале")
    async def film(self, message):
        q = utils.get_args_raw(message).strip()
        if not q:
            await utils.answer(message, self.strings["no_query"])
            return
        # reload config every call to pick up env changes or saved file
        self.load_config()
        if not self.omdb_key:
            await utils.answer(message, self.strings["no_api"])
            return
        status = await utils.answer(message, f"🔎 Ищу: <b>{escape(q)}</b>")
        try:
            data = await asyncio.to_thread(self.fetch_omdb, q)
            if not data or data.get("Response") == "False":
                await status.delete()
                await utils.answer(message, self.strings["not_found"].format(q=escape(q)))
                return
            title = data.get("Title", "—")
            year = data.get("Year", "—")
            kind = data.get("Type", "movie")
            runtime = data.get("Runtime", "—")
            genre = data.get("Genre", "—")
            director = data.get("Director", "—")
            actors = data.get("Actors", "—")
            plot = data.get("Plot", "—")
            country = data.get("Country", "—")
            language = data.get("Language", "—")
            awards = data.get("Awards", "—")
            imdb_rating = data.get("imdbRating", "—")
            imdb_votes = data.get("imdbVotes", "—")
            metascore = data.get("Metascore", "—")
            imdb_id = data.get("imdbID", "")
            total_seasons = data.get("totalSeasons", "—") if kind == "series" else "—"
            poster = data.get("Poster", "")
            imdb_link = f"https://www.imdb.com/title/{imdb_id}/" if imdb_id else ""
            type_line = "<b>Тип:</b> Сериал" if kind == "series" else "<b>Тип:</b> Фильм"

            caption = self.strings["result_prefix"].format(title=escape(title), year=escape(year), type_line=type_line)
            caption += self.strings["details_template"].format(
                plot=escape(plot),
                genre=escape(genre),
                director=escape(director),
                actors=escape(actors),
                country=escape(country),
                language=escape(language),
                awards=escape(awards),
                runtime=escape(runtime),
                seasons=escape(str(total_seasons)),
                imdb_rating=escape(imdb_rating),
                imdb_votes=escape(imdb_votes),
                metascore=escape(metascore),
                imdb_link=imdb_link
            )

            if poster and poster != "N/A":
                try:
                    resp = await asyncio.to_thread(requests.get, poster, {"timeout": 8})
                    if getattr(resp, "status_code", None) == 200:
                        bio = BytesIO(resp.content)
                        bio.name = f"{title}.jpg"
                        bio.seek(0)
                        await message.client.send_file(message.chat_id, bio, caption=caption, parse_mode='html', reply_to=message.reply_to_msg_id)
                        await status.delete()
                        return
                except Exception:
                    pass

            await utils.answer(message, caption)
            await status.delete()
        except Exception as e:
            await status.delete()
            await utils.answer(message, self.strings["error"].format(e=escape(str(e))))

    def fetch_omdb(self, q):
        url = "http://www.omdbapi.com/"
        params = {"apikey": self.omdb_key, "t": q, "plot": "full", "r": "json"}
        r = requests.get(url, params=params, timeout=8)
        if r.status_code != 200:
            params2 = {"apikey": self.omdb_key, "s": q, "type": "movie", "r": "json"}
            r2 = requests.get(url, params=params2, timeout=8)
            if r2.status_code == 200:
                js = r2.json()
                if js.get("Response") == "True" and js.get("Search"):
                    first = js["Search"][0]
                    imdbid = first.get("imdbID")
                    if imdbid:
                        r3 = requests.get(url, params={"apikey": self.omdb_key, "i": imdbid, "plot": "full", "r": "json"}, timeout=8)
                        if r3.status_code == 200:
                            return r3.json()
            return None
        return r.json()
