# meta developer: @shaatimi
# requires: requests

from .. import loader, utils
import asyncio
import html
import re
import requests
import time
import unicodedata
from urllib.parse import quote


@loader.tds
class MText(loader.Module):
    strings = {
        "name": "MText",
        "usage": "<b>❌ Использование:</b> <code>?mtext &lt;кол-во строк&gt; &lt;название песни&gt;</code>",
        "empty": "<b>❌ Нет текста.</b>",
        "notfound": "<b>❌ Текст не найден.</b>",
        "error": "<b>Ошибка:</b> <code>{}</code>",
    }

    strings_ru = strings

    _ru_to_lat = str.maketrans({
        "а": "a",
        "б": "b",
        "в": "v",
        "г": "g",
        "д": "d",
        "е": "e",
        "ё": "e",
        "ж": "zh",
        "з": "z",
        "и": "i",
        "й": "y",
        "к": "k",
        "л": "l",
        "м": "m",
        "н": "n",
        "о": "o",
        "п": "p",
        "р": "r",
        "с": "s",
        "т": "t",
        "у": "u",
        "ф": "f",
        "х": "h",
        "ц": "c",
        "ч": "ch",
        "ш": "sh",
        "щ": "sch",
        "ъ": "",
        "ы": "y",
        "ь": "",
        "э": "e",
        "ю": "yu",
        "я": "ya",
    })

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

    def _norm(self, text):
        text = unicodedata.normalize("NFKD", str(text)).casefold().replace("ё", "е")
        text = re.sub(r"[^0-9a-zа-я]+", " ", text)
        return re.sub(r"\s+", " ", text).strip()

    def _lat(self, text):
        return self._norm(text).translate(self._ru_to_lat)

    def _split_query(self, query):
        query = " ".join(query.split())
        if " - " in query:
            artist, title = query.split(" - ", 1)
            artist = artist.strip()
            title = title.strip()
            if artist and title:
                return artist, title
        return "", query

    def _clean_lines(self, text, limit):
        lines = []
        for raw in str(text).replace("\r\n", "\n").replace("\r", "\n").split("\n"):
            line = raw.strip()
            if line:
                lines.append(line)
            if len(lines) >= limit:
                break
        return lines

    def _get_artist_title(self, item):
        artist = item.get("artist_name") or item.get("artist") or ""
        title = item.get("track_name") or item.get("title") or item.get("name") or ""

        if isinstance(artist, dict):
            artist = artist.get("name") or artist.get("value") or ""
        if isinstance(title, dict):
            title = title.get("name") or title.get("value") or ""

        return str(artist).strip(), str(title).strip()

    def _get_lyrics_text(self, item):
        if not isinstance(item, dict):
            return None
        for key in ("plainLyrics", "syncedLyrics", "lyrics", "text"):
            value = item.get(key)
            if value:
                return value
        return None

    def _score_item(self, query, artist, title):
        q = self._norm(query)
        a = self._norm(artist)
        t = self._norm(title)
        combo = self._norm(f"{artist} {title}")
        q_tokens = set(q.split())
        combo_tokens = set(combo.split())
        score = 0

        score += sum(3 for tok in q_tokens if tok in combo_tokens)
        if q == combo:
            score += 10
        if t and (t == q or t in q or q in t):
            score += 5
        if a and (a == q or a in q or q in a):
            score += 4
        if len(q_tokens) >= 2 and q_tokens.issubset(combo_tokens):
            score += 3
        return score

    def _pick_best_item(self, items, query):
        best = None
        best_score = 0

        for item in items:
            if not isinstance(item, dict):
                continue
            artist, title = self._get_artist_title(item)
            score = self._score_item(query, artist, title)
            if score > best_score:
                best_score = score
                best = item

        if best_score <= 0:
            return None
        return best

    def _lyrics_ovh_get(self, artist, title):
        key = f"ovh_get:{artist.casefold()}:{title.casefold()}"
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

        lyrics = data.get("lyrics") if isinstance(data, dict) else None
        self._cache_set(key, lyrics)
        return lyrics

    def _lyrics_ovh_suggest(self, query):
        key = f"ovh_suggest:{query.casefold()}"
        cached = self._cache_get(key)
        if cached is not None:
            return cached

        try:
            data = self._get_json(f"https://api.lyrics.ovh/suggest/{quote(query, safe='')}")
        except requests.HTTPError as e:
            if e.response is not None and e.response.status_code == 404:
                self._cache_set(key, None)
                return None
            raise

        items = []
        if isinstance(data, dict):
            items = data.get("data") or []
        elif isinstance(data, list):
            items = data

        best = self._pick_best_item(items, query)
        if not best:
            self._cache_set(key, None)
            return None

        artist, title = self._get_artist_title(best)
        result = (artist, title)
        self._cache_set(key, result)
        return result

    def _lrclib_search(self, query):
        key = f"lrclib_search:{query.casefold()}"
        cached = self._cache_get(key)
        if cached is not None:
            return cached

        data = self._get_json("https://lrclib.net/api/search", params={"query": query})
        items = data if isinstance(data, list) else data.get("data") if isinstance(data, dict) else []
        best = self._pick_best_item(items or [], query)
        if not best:
            self._cache_set(key, None)
            return None

        lyrics = self._get_lyrics_text(best)
        if lyrics:
            self._cache_set(key, lyrics)
            return lyrics

        artist, title = self._get_artist_title(best)
        if artist and title:
            lyrics = self._lrclib_get(artist, title)
            if lyrics:
                self._cache_set(key, lyrics)
                return lyrics

        self._cache_set(key, None)
        return None

    def _lrclib_get(self, artist, title):
        key = f"lrclib_get:{artist.casefold()}:{title.casefold()}"
        cached = self._cache_get(key)
        if cached is not None:
            return cached

        try:
            data = self._get_json(
                "https://lrclib.net/api/get",
                params={"artist_name": artist, "track_name": title},
            )
        except requests.HTTPError as e:
            if e.response is not None and e.response.status_code == 404:
                self._cache_set(key, None)
                return None
            raise

        lyrics = self._get_lyrics_text(data) if isinstance(data, dict) else None
        self._cache_set(key, lyrics)
        return lyrics

    def _query_variants(self, query):
        query = " ".join(query.split())
        words = query.split()
        variants = []
        seen = set()

        def add(value):
            value = " ".join(str(value).split()).strip()
            if not value:
                return
            key = self._norm(value)
            if not key or key in seen:
                return
            seen.add(key)
            variants.append(value)

        def add_pack(value):
            add(value)
            add(self._lat(value))

        if len(words) == 2:
            add_pack(f"{words[1]} {words[0]}")
            add_pack(query)
        else:
            for size in range(min(4, len(words)), 1, -1):
                for i in range(0, len(words) - size + 1):
                    add_pack(" ".join(words[i : i + size]))

            if len(words) >= 3:
                add_pack(" ".join(reversed(words)))

            for i in range(len(words)):
                for j in range(i + 2, len(words)):
                    add_pack(f"{words[i]} {words[j]}")

            add_pack(query)

        return variants[:12]

    async def _find_lyrics(self, query):
        variants = self._query_variants(query)

        for variant in variants:
            lyrics = await asyncio.to_thread(self._lrclib_search, variant)
            if lyrics:
                return lyrics

        for variant in variants:
            pair = await asyncio.to_thread(self._lyrics_ovh_suggest, variant)
            if not pair:
                continue
            artist, title = pair
            if artist and title:
                lyrics = await asyncio.to_thread(self._lyrics_ovh_get, artist, title)
                if lyrics:
                    return lyrics
                lyrics = await asyncio.to_thread(self._lrclib_get, artist, title)
                if lyrics:
                    return lyrics

        return None

    @loader.command(ru_doc="Получить первые N строк текста песни по любому запросу")
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
            lyrics = await self._find_lyrics(query)
            if not lyrics:
                await utils.answer(message, self.strings["notfound"])
                return

            lines = self._clean_lines(lyrics, count)
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
