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
        "badjson": "<b>❌ Некорректный ответ API.</b>",
        "error": "<b>Ошибка:</b> <code>{}</code>",
    }

    strings_ru = strings

    def _session(self):
        s = getattr(self, "_mtext_session", None)
        if s is None:
            s = requests.Session()
            s.headers.update(
                {
                    "User-Agent": "Mozilla/5.0",
                    "Accept": "application/json,text/plain,*/*",
                }
            )
            self._mtext_session = s
        return s

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
        session = self._session()
        r = session.get(url, params=params, timeout=(4, 12))
        r.raise_for_status()
        return r.json()

    def _normalize_lines(self, lyrics, limit):
        lines = []
        for line in str(lyrics).splitlines():
            line = line.strip()
            if line:
                lines.append(line)
            if len(lines) >= limit:
                break
        return lines

    def _split_query(self, query):
        if " - " in query:
            artist, title = query.split(" - ", 1)
            artist = artist.strip()
            title = title.strip()
            if artist and title:
                return artist, title
        return "", query.strip()

    def _suggest_track(self, term):
        cache_key = f"suggest:{term.casefold()}"
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached

        data = self._get_json(f"https://api.lyrics.ovh/suggest/{quote(term, safe='')}")
        items = []

        if isinstance(data, dict):
            items = data.get("data") or data.get("items") or data.get("results") or []
        elif isinstance(data, list):
            items = data

        if not items:
            self._cache_set(cache_key, None)
            return None

        first = items[0] or {}
        artist = ""
        title = ""

        if isinstance(first, dict):
            artist_val = first.get("artist")
            if isinstance(artist_val, dict):
                artist = artist_val.get("name") or ""
            elif isinstance(artist_val, str):
                artist = artist_val

            title = first.get("title") or first.get("name") or ""
        elif isinstance(first, str):
            title = first

        if not title:
            title = term

        result = (artist.strip(), title.strip())
        self._cache_set(cache_key, result)
        return result

    def _get_lyrics(self, artist, title):
        key = f"lyrics:{artist.casefold()}:{title.casefold()}"
        cached = self._cache_get(key)
        if cached is not None:
            return cached

        data = self._get_json(
            f"https://api.lyrics.ovh/v1/{quote(artist, safe='')}/{quote(title, safe='')}"
        )

        lyrics = None
        if isinstance(data, dict):
            lyrics = data.get("lyrics")
            if not lyrics and data.get("error"):
                lyrics = None

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

            if not artist:
                suggested = await asyncio.to_thread(self._suggest_track, query)
                if not suggested:
                    await utils.answer(message, self.strings["notfound"])
                    return
                artist, title = suggested

            lyrics = await asyncio.to_thread(self._get_lyrics, artist, title)
            if not lyrics:
                await utils.answer(message, self.strings["notfound"])
                return

            lines = self._normalize_lines(lyrics, count)
            if not lines:
                await utils.answer(message, self.strings["notfound"])
                return

            text = "\n".join(html.escape(line) for line in lines)
            await utils.answer(message, text)

        except requests.Timeout:
            await utils.answer(message, self.strings["error"].format("Timeout"))
        except requests.RequestException as e:
            await utils.answer(message, self.strings["error"].format(html.escape(str(e))))
        except ValueError:
            await utils.answer(message, self.strings["badjson"])
        except Exception as e:
            await utils.answer(message, self.strings["error"].format(html.escape(str(e))))
