# meta developer: @shaatimi
# requires: requests

from .. import loader, utils
import asyncio
import html
import requests
import time
from urllib.parse import quote


@loader.tds
class MText(loader.Module):
    strings = {
        "name": "MText",
        "usage": "<b>❌ Использование:</b> <code>?mtext &lt;кол-во строк&gt; &lt;artist - title | title&gt;</code>",
        "empty": "<b>❌ Нет текста.</b>",
        "notfound": "<b>❌ Текст не найден.</b>",
        "error": "<b>Ошибка:</b> <code>{}</code>",
    }

    strings_ru = strings

    def _session(self):
        session = getattr(self, "_mtext_session", None)
        if session is None:
            session = requests.Session()
            session.headers.update(
                {
                    "User-Agent": "Mozilla/5.0",
                    "Accept": "application/json,text/plain,*/*",
                    "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
                }
            )
            self._mtext_session = session
        return session

    def _cache_get(self, key):
        cache = getattr(self, "_mtext_cache", None)
        if not cache:
            return None
        item = cache.get(key)
        if not item:
            return None
        ts, value = item
        if time.monotonic() - ts > 300:
            cache.pop(key, None)
            return None
        return value

    def _cache_set(self, key, value):
        cache = getattr(self, "_mtext_cache", None)
        if cache is None:
            cache = {}
            self._mtext_cache = cache
        cache[key] = (time.monotonic(), value)

    def _get_json(self, url, params=None):
        r = self._session().get(url, params=params, timeout=(4, 12))
        r.raise_for_status()
        return r.json()

    def _split_query(self, query):
        query = query.strip()
        if " - " in query:
            artist, title = query.split(" - ", 1)
            artist = artist.strip()
            title = title.strip()
            if artist and title:
                return artist, title
        return "", query

    def _clean_lines(self, text, limit):
        lines = []
        for raw in str(text).splitlines():
            line = raw.strip()
            if line:
                lines.append(line)
            if len(lines) >= limit:
                break
        return lines

    def _normalize_text(self, text):
        text = str(text or "").strip()
        return text.replace("\r\n", "\n").replace("\r", "\n")

    def _extract_lyrics_from_lrclib(self, payload):
        if not payload:
            return None

        if isinstance(payload, dict):
            for key in ("plainLyrics", "syncedLyrics", "lyrics", "text"):
                value = payload.get(key)
                if value:
                    return value

            if isinstance(payload.get("data"), dict):
                return self._extract_lyrics_from_lrclib(payload["data"])

            if isinstance(payload.get("results"), list) and payload["results"]:
                return self._extract_lyrics_from_lrclib(payload["results"][0])

        if isinstance(payload, list) and payload:
            for item in payload:
                found = self._extract_lyrics_from_lrclib(item)
                if found:
                    return found

        return None

    def _lyrics_ovh(self, artist, title):
        key = f"ovh:{artist.casefold()}:{title.casefold()}"
        cached = self._cache_get(key)
        if cached is not None:
            return cached

        url = f"https://api.lyrics.ovh/v1/{quote(artist, safe='')}/{quote(title, safe='')}"
        try:
            data = self._get_json(url)
        except requests.HTTPError as e:
            if e.response is not None and e.response.status_code == 404:
                self._cache_set(key, None)
                return None
            raise

        lyrics = None
        if isinstance(data, dict):
            lyrics = data.get("lyrics")

        self._cache_set(key, lyrics)
        return lyrics

    def _lrclib_get(self, artist, title):
        key = f"lrclib_get:{artist.casefold()}:{title.casefold()}"
        cached = self._cache_get(key)
        if cached is not None:
            return cached

        url = "https://lrclib.net/api/get"
        params = {
            "artist_name": artist,
            "track_name": title,
        }
        try:
            data = self._get_json(url, params=params)
        except requests.HTTPError as e:
            if e.response is not None and e.response.status_code == 404:
                self._cache_set(key, None)
                return None
            raise

        lyrics = self._extract_lyrics_from_lrclib(data)
        self._cache_set(key, lyrics)
        return lyrics

    def _lrclib_search(self, query):
        key = f"lrclib_search:{query.casefold()}"
        cached = self._cache_get(key)
        if cached is not None:
            return cached

        url = "https://lrclib.net/api/search"
        data = self._get_json(url, params={"query": query})

        lyrics = None
        if isinstance(data, list):
            for item in data:
                lyrics = self._extract_lyrics_from_lrclib(item)
                if lyrics:
                    break
        else:
            lyrics = self._extract_lyrics_from_lrclib(data)

        self._cache_set(key, lyrics)
        return lyrics

    @loader.command(ru_doc="Получить первые N строк текста песни")
    async def mtext(self, message):
        raw = utils.get_args_raw(message).strip()
        if not raw:
            await utils.answer(message, self.strings["usage"])
            return

        parts = raw.split(maxsplit=1)
        if len(parts) < 2:
            await utils.answer(message, self.strings["usage"])
            return

        try:
            count = int(parts[0])
        except ValueError:
            await utils.answer(message, self.strings["usage"])
            return

        if count <= 0:
            await utils.answer(message, self.strings["usage"])
            return

        query = parts[1].strip()
        if not query:
            await utils.answer(message, self.strings["empty"])
            return

        try:
            artist, title = self._split_query(query)

            lyrics = None
            if artist and title:
                lyrics = await asyncio.to_thread(self._lyrics_ovh, artist, title)
                if not lyrics:
                    lyrics = await asyncio.to_thread(self._lrclib_get, artist, title)

            if not lyrics:
                lyrics = await asyncio.to_thread(self._lrclib_search, query)

            if not lyrics:
                await utils.answer(message, self.strings["notfound"])
                return

            lines = self._clean_lines(self._normalize_text(lyrics), count)
            if not lines:
                await utils.answer(message, self.strings["notfound"])
                return

            text = "\n".join(html.escape(line) for line in lines)
            await utils.answer(message, text)

        except requests.Timeout:
            await utils.answer(message, self.strings["error"].format("Timeout"))
        except requests.RequestException as e:
            await utils.answer(message, self.strings["error"].format(html.escape(str(e))))
        except Exception as e:
            await utils.answer(message, self.strings["error"].format(html.escape(str(e))))
