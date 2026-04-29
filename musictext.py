# meta developer: @shaatimi
# requires: requests

from .. import loader, utils

import asyncio
import html
import re
import requests
import time
import unicodedata
from bs4 import BeautifulSoup
from urllib.parse import quote, quote_plus, parse_qs, urlparse, unquote


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

    _latin_map = str.maketrans(
        {
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
        }
    )

    _lyrics_domains = (
        "lyricstranslate.com",
        "muztext.com",
        "text-lyrics.ru",
        "mp3party.net",
        "seven.muzyet.com",
        "my.mail.ru",
    )

    def _session(self):
        session = getattr(self, "_mtext_session", None)
        if session is None:
            session = requests.Session()
            session.headers.update(
                {
                    "User-Agent": "Mozilla/5.0",
                    "Accept": "application/json,text/plain,text/html,*/*",
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
        if time.monotonic() - ts > 600:
            cache.pop(key, None)
            return None
        return value

    def _cache_set(self, key, value):
        cache = getattr(self, "_mtext_cache", None)
        if cache is None:
            cache = {}
            self._mtext_cache = cache
        cache[key] = (time.monotonic(), value)

    def _norm(self, text):
        text = unicodedata.normalize("NFKD", str(text)).casefold().replace("ё", "е")
        text = re.sub(r"[^0-9a-zа-я]+", " ", text)
        return re.sub(r"\s+", " ", text).strip()

    def _lat(self, text):
        return self._norm(text).translate(self._latin_map)

    def _split_query(self, query):
        query = " ".join(query.split()).strip()
        if " - " in query:
            artist, title = query.split(" - ", 1)
            artist = artist.strip()
            title = title.strip()
            if artist and title:
                return artist, title
        return "", query

    def _clean_lines(self, text, limit):
        result = []
        seen = set()
        for raw in str(text).replace("\r\n", "\n").replace("\r", "\n").split("\n"):
            line = re.sub(r"\s+", " ", raw).strip()
            if not line:
                continue
            if len(line) <= 1:
                continue
            if re.fullmatch(r"[\W\d_]+", line):
                continue
            key = self._norm(line)
            if key in seen:
                continue
            seen.add(key)
            result.append(line)
            if len(result) >= limit:
                break
        return result

    def _score_item(self, query, artist, title):
        q = self._norm(query)
        a = self._norm(artist)
        t = self._norm(title)
        combo = self._norm(f"{artist} {title}")
        q_tokens = [x for x in q.split() if len(x) > 1]
        combo_tokens = set(combo.split())
        score = 0

        for tok in q_tokens:
            if tok in combo_tokens:
                score += 4
            if tok in t:
                score += 2
            if tok in a:
                score += 2

        if q == combo:
            score += 10
        if q and q in combo:
            score += 8
        if t and (t == q or t in q or q in t):
            score += 6
        if a and (a == q or a in q or q in a):
            score += 4

        return score

    def _pick_best_item(self, items, query):
        best = None
        best_score = 0

        for item in items:
            if not isinstance(item, dict):
                continue

            artist = item.get("artist_name") or item.get("artist") or ""
            title = item.get("track_name") or item.get("title") or item.get("name") or ""

            if isinstance(artist, dict):
                artist = artist.get("name") or artist.get("value") or ""
            if isinstance(title, dict):
                title = title.get("name") or title.get("value") or ""

            score = self._score_item(query, str(artist), str(title))
            if score > best_score:
                best_score = score
                best = item

        return best if best_score > 0 else None

    def _get_item_lyrics(self, item):
        if not isinstance(item, dict):
            return None
        for key in ("plainLyrics", "syncedLyrics", "lyrics", "text"):
            value = item.get(key)
            if value:
                return value
        return None

    def _json_get(self, url, params=None):
        r = self._session().get(url, params=params, timeout=(4, 10))
        r.raise_for_status()
        return r.json()

    def _lyrics_ovh_suggest(self, term):
        key = f"ovh_suggest:{term.casefold()}"
        cached = self._cache_get(key)
        if cached is not None:
            return cached

        try:
            data = self._json_get(f"https://api.lyrics.ovh/suggest/{quote(term, safe='')}")
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

        best = self._pick_best_item(items, term)
        if not best:
            self._cache_set(key, None)
            return None

        artist = best.get("artist") or {}
        if isinstance(artist, dict):
            artist = artist.get("name") or ""
        title = best.get("title") or best.get("name") or ""

        result = (str(artist).strip(), str(title).strip())
        self._cache_set(key, result)
        return result

    def _lyrics_ovh_get(self, artist, title):
        key = f"ovh_get:{artist.casefold()}:{title.casefold()}"
        cached = self._cache_get(key)
        if cached is not None:
            return cached

        url = f"https://api.lyrics.ovh/v1/{quote(artist, safe='')}/{quote(title, safe='')}"
        try:
            data = self._json_get(url)
        except requests.HTTPError as e:
            if e.response is not None and e.response.status_code == 404:
                self._cache_set(key, None)
                return None
            raise

        lyrics = data.get("lyrics") if isinstance(data, dict) else None
        self._cache_set(key, lyrics)
        return lyrics

    def _lrclib_search(self, query):
        key = f"lrclib_search:{query.casefold()}"
        cached = self._cache_get(key)
        if cached is not None:
            return cached

        data = self._json_get("https://lrclib.net/api/search", params={"query": query})
        items = data if isinstance(data, list) else data.get("data") if isinstance(data, dict) else []
        best = self._pick_best_item(items or [], query)

        if not best:
            self._cache_set(key, None)
            return None

        lyrics = self._get_item_lyrics(best)
        if lyrics:
            self._cache_set(key, lyrics)
            return lyrics

        artist = best.get("artist_name") or best.get("artist") or ""
        title = best.get("track_name") or best.get("title") or best.get("name") or ""
        if isinstance(artist, dict):
            artist = artist.get("name") or artist.get("value") or ""
        if isinstance(title, dict):
            title = title.get("name") or title.get("value") or ""

        if artist and title:
            lyrics = self._lrclib_get(str(artist), str(title))
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
            data = self._json_get(
                "https://lrclib.net/api/get",
                params={"artist_name": artist, "track_name": title},
            )
        except requests.HTTPError as e:
            if e.response is not None and e.response.status_code == 404:
                self._cache_set(key, None)
                return None
            raise

        lyrics = self._get_item_lyrics(data) if isinstance(data, dict) else None
        self._cache_set(key, lyrics)
        return lyrics

    def _ddg_unpack(self, href):
        if not href:
            return None
        if href.startswith("http://") or href.startswith("https://"):
            return href
        if href.startswith("/l/?"):
            qs = parse_qs(urlparse(href).query)
            target = qs.get("uddg", [None])[0]
            if target:
                return unquote(target)
        return None

    def _is_lyrics_url(self, url):
        url = url or ""
        return any(domain in url for domain in self._lyrics_domains)

    def _ddg_search(self, query):
        key = f"ddg:{query.casefold()}"
        cached = self._cache_get(key)
        if cached is not None:
            return cached

        r = self._session().get(
            "https://duckduckgo.com/html/",
            params={"q": query},
            timeout=(4, 10),
        )
        r.raise_for_status()

        soup = BeautifulSoup(r.text, "html.parser")
        results = []
        seen = set()

        for a in soup.select("a.result__a"):
            url = self._ddg_unpack(a.get("href"))
            if not url or not self._is_lyrics_url(url):
                continue
            if url in seen:
                continue
            seen.add(url)
            results.append((url, a.get_text(" ", strip=True)))

        if not results:
            for a in soup.find_all("a", href=True):
                url = self._ddg_unpack(a.get("href"))
                if not url or not self._is_lyrics_url(url):
                    continue
                if url in seen:
                    continue
                seen.add(url)
                results.append((url, a.get_text(" ", strip=True)))

        self._cache_set(key, results[:8])
        return results[:8]

    def _block_score(self, text):
        lines = [re.sub(r"\s+", " ", x).strip() for x in str(text).splitlines()]
        lines = [x for x in lines if len(x) > 1 and not re.fullmatch(r"[\W\d_]+", x)]
        if not lines:
            return 0
        unique_ratio = len(set(self._norm(x) for x in lines)) / max(len(lines), 1)
        return len(lines) * 10 + int(min(len(str(text)) / 80, 120)) + int(unique_ratio * 10)

    def _extract_page_text(self, url):
        key = f"page:{url}"
        cached = self._cache_get(key)
        if cached is not None:
            return cached

        r = self._session().get(url, timeout=(4, 12))
        r.raise_for_status()

        soup = BeautifulSoup(r.text, "html.parser")
        for tag in soup(["script", "style", "noscript", "svg", "footer", "header", "nav"]):
            tag.decompose()

        selectors = [
            "[itemprop='lyrics']",
            ".lyrics",
            ".lyric",
            ".lyrics-body",
            ".lyrics-content",
            ".lyric-body",
            ".lyric-text",
            ".songLyricsV14",
            ".song-lyrics",
            "[class*='lyrics']",
            "[class*='lyric']",
            "article",
            "main",
        ]

        candidates = []

        for sel in selectors:
            for node in soup.select(sel):
                txt = node.get_text("\n", strip=True)
                if txt:
                    candidates.append(txt)

        body = soup.body.get_text("\n", strip=True) if soup.body else soup.get_text("\n", strip=True)
        if body:
            candidates.append(body)

        best = None
        best_score = 0
        for cand in candidates:
            score = self._block_score(cand)
            if score > best_score:
                best_score = score
                best = cand

        self._cache_set(key, best)
        return best

    def _variants(self, query):
        q = " ".join(query.split()).strip()
        words = q.split()
        seen = set()
        result = []

        def add(value):
            value = " ".join(str(value).split()).strip()
            if not value:
                return
            key = self._norm(value)
            if not key or key in seen:
                return
            seen.add(key)
            result.append(value)

        add(q)
        add(self._lat(q))

        if len(words) >= 2:
            add(" ".join(reversed(words)))
            add(self._lat(" ".join(reversed(words))))

        if len(words) >= 3:
            for size in (4, 3, 2):
                if len(words) < size:
                    continue
                for i in range(len(words) - size + 1):
                    chunk = " ".join(words[i : i + size])
                    add(chunk)
                    add(self._lat(chunk))

        return result[:12]

    def _web_queries(self, query):
        queries = []
        seen = set()

        def add(value):
            value = " ".join(str(value).split()).strip()
            if not value:
                return
            key = self._norm(value)
            if not key or key in seen:
                return
            seen.add(key)
            queries.append(value)

        add(query)
        add(f"{query} lyrics")
        add(f"{query} текст песни")
        add(self._lat(query))
        add(f"{self._lat(query)} lyrics")
        return queries[:5]

    async def _find_lyrics(self, raw_query):
        variants = self._variants(raw_query)

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

        for variant in self._web_queries(raw_query):
            try:
                results = await asyncio.to_thread(self._ddg_search, variant)
            except Exception:
                continue

            for url, title in results:
                try:
                    page_text = await asyncio.to_thread(self._extract_page_text, url)
                except Exception:
                    continue

                if not page_text:
                    continue

                page_score = self._block_score(page_text)
                title_score = self._score_item(variant, "", title or "")
                if page_score > 0 and title_score >= 0:
                    return page_text

        return None

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
            lyrics = await self._find_lyrics(query)
            if not lyrics:
                await utils.answer(message, self.strings["notfound"])
                return

            lines = self._clean_lines(lyrics, count)
            if not lines:
                await utils.answer(message, self.strings["notfound"])
                return

            await utils.answer(message, "\n".join(html.escape(x) for x in lines))

        except requests.Timeout:
            await utils.answer(message, self.strings["error"].format("Timeout"))
        except requests.RequestException as e:
            await utils.answer(message, self.strings["error"].format(html.escape(str(e))))
        except Exception as e:
            await utils.answer(message, self.strings["error"].format(html.escape(str(e))))
