# meta developer: @shaatimi
# requires: requests funstat-api

from .. import loader, utils

import asyncio
import html
import textwrap
import urllib3
from datetime import datetime

from funstat_api import FunstatClient, FunstatError, ResolveError, ApiError

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


@loader.tds
class FunstatWhois(loader.Module):
    strings = {
        "name": "FunstatWhois",
        "no_token": "<b>❌ Токен не задан.</b>\n\n<b>Используй:</b> <code>?settoken токен</code>",
        "saved": "<b>✅ Токен сохранён.</b>",
        "invalid": "<b>❌ Укажи ответ на сообщение или юзернейм / ID / ссылку.</b>",
        "not_found": "<b>❌ Пользователь не найден.</b>",
        "error": "<b>Ошибка:</b> <code>{}</code>",
        "need_arg": "<b>❌ Укажи токен.</b>\n\n<b>Пример:</b> <code>?settoken abc123</code>",
        "loading": "<b>⏳ Получаю данные...</b>",
    }

    strings_ru = {
        "whois_title": "<b>👤 WHOIS • {target}</b>",
        "profile": "<b>Профиль</b>",
        "stats": "<b>Статистика</b>",
        "history": "<b>История</b>",
        "usage": "<b>Использование ника</b>",
        "yes": "Да",
        "no": "Нет",
        "none": "нет",
        "unknown": "неизвестно",
    }

    def _esc(self, value):
        if value is None:
            return "-"
        text = str(value).strip()
        return html.escape(text if text else "-")

    def _fmt_bool(self, value):
        if value is True:
            return self.strings_ru["yes"]
        if value is False:
            return self.strings_ru["no"]
        return self.strings_ru["unknown"]

    def _fmt_pct(self, value):
        try:
            if value is None:
                return "-"
            return f"{float(value):.2f}%"
        except Exception:
            return self._esc(value)

    def _fmt_dt(self, value):
        if value is None:
            return "-"
        text = str(value).strip()
        if not text:
            return "-"
        try:
            dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
            return dt.strftime("%d.%m.%Y %H:%M UTC")
        except Exception:
            return self._esc(text)

    def _short(self, value, width=90):
        text = "" if value is None else str(value).strip()
        if not text:
            return "-"
        return html.escape(textwrap.shorten(text, width=width, placeholder="..."))

    def _g(self, obj, name, default=None):
        return getattr(obj, name, default)

    def _first(self, data):
        if isinstance(data, list):
            return data[0] if data else None
        return data

    def _normalize_target(self, raw):
        q = (raw or "").strip()
        q = q.split("?")[0].strip()

        for prefix in ("https://t.me/", "http://t.me/", "t.me/", "https://telegram.me/", "http://telegram.me/", "telegram.me/"):
            if q.startswith(prefix):
                q = q[len(prefix):].strip("/")

        if q.startswith("@"):
            q = q[1:]

        return q

    def _display_target(self, raw, resolved):
        if resolved is not None:
            username = self._g(resolved, "username")
            if username:
                return f"@{username}"
            rid = self._g(resolved, "id")
            if rid is not None:
                return str(rid)
        raw = self._normalize_target(raw)
        if raw.isdigit():
            return raw
        return f"@{raw}" if raw else "unknown"

    def _format_history_items(self, items, kind="user"):
        if not items:
            return f"• {self.strings_ru['none']}"
        lines = []
        for item in items[:5]:
            dt = self._fmt_dt(self._g(item, "date_time", self._g(item, "created_at", self._g(item, "date"))))
            name = self._g(item, "name", self._g(item, "username", self._g(item, "title", "-")))
            if kind == "user":
                username = self._g(item, "username")
                if username:
                    name = f"@{username}"
            lines.append(f"• <code>{self._esc(dt)}</code> → <code>{self._esc(name)}</code>")
        return "\n".join(lines)

    def _build_report(self, query, resolved, min_stats, full_stats, names, usernames, usage):
        target = self._display_target(query, resolved)

        profile_lines = []
        if resolved is not None:
            profile_lines.append(f"• <b>ID:</b> <code>{self._esc(self._g(resolved, 'id'))}</code>")
            profile_lines.append(f"• <b>Юзернейм:</b> <code>{self._esc('@' + self._g(resolved, 'username')) if self._g(resolved, 'username') else '-'}</code>")
            name = f"{self._g(resolved, 'first_name', '')} {self._g(resolved, 'last_name', '')}".strip()
            profile_lines.append(f"• <b>Имя:</b> <code>{self._esc(name if name else '-')}</code>")
            profile_lines.append(f"• <b>Активен:</b> <code>{self._fmt_bool(self._g(resolved, 'is_active'))}</code>")
            profile_lines.append(f"• <b>Бот:</b> <code>{self._fmt_bool(self._g(resolved, 'is_bot'))}</code>")
            profile_lines.append(f"• <b>Premium:</b> <code>{self._fmt_bool(self._g(resolved, 'has_premium'))}</code>")
            about = self._g(resolved, "about")
            if about is not None:
                profile_lines.append(f"• <b>О себе:</b> <code>{self._short(about, 90)}</code>")
        else:
            profile_lines.append(f"• <b>Запрос:</b> <code>{self._esc(query)}</code>")

        min_lines = []
        if min_stats is not None:
            min_lines.extend([
                f"• <b>Первое сообщение:</b> <code>{self._fmt_dt(self._g(min_stats, 'first_msg_date'))}</code>",
                f"• <b>Последнее сообщение:</b> <code>{self._fmt_dt(self._g(min_stats, 'last_msg_date'))}</code>",
                f"• <b>Всего сообщений:</b> <code>{self._esc(self._g(min_stats, 'total_msg_count'))}</code>",
                f"• <b>Сообщений в группах:</b> <code>{self._esc(self._g(min_stats, 'msg_in_groups_count'))}</code>",
                f"• <b>Админ в группах:</b> <code>{self._esc(self._g(min_stats, 'adm_in_groups'))}</code>",
                f"• <b>Групп найдено:</b> <code>{self._esc(self._g(min_stats, 'total_groups'))}</code>",
                f"• <b>Юзернеймов:</b> <code>{self._esc(self._g(min_stats, 'usernames_count'))}</code>",
                f"• <b>Имен:</b> <code>{self._esc(self._g(min_stats, 'names_count'))}</code>",
            ])
        else:
            min_lines.append("• <b>Нет данных</b>")

        full_lines = []
        if full_stats is not None:
            full_lines.extend([
                f"• <b>Язык:</b> <code>{self._esc(self._g(full_stats, 'lang_code'))}</code>",
                f"• <b>Кириллица основная:</b> <code>{self._fmt_bool(self._g(full_stats, 'is_cyrillic_primary'))}</code>",
                f"• <b>Уникальность:</b> <code>{self._fmt_pct(self._g(full_stats, 'unique_percent'))}</code>",
                f"• <b>Reply:</b> <code>{self._fmt_pct(self._g(full_stats, 'reply_percent'))}</code>",
                f"• <b>Медиа:</b> <code>{self._fmt_pct(self._g(full_stats, 'media_percent'))}</code>",
                f"• <b>Ссылки:</b> <code>{self._fmt_pct(self._g(full_stats, 'link_percent'))}</code>",
                f"• <b>Голосовые:</b> <code>{self._esc(self._g(full_stats, 'voice_count'))}</code>",
                f"• <b>Кружки:</b> <code>{self._esc(self._g(full_stats, 'circle_count'))}</code>",
                f"• <b>Подарки:</b> <code>{self._esc(self._g(full_stats, 'gift_count'))}</code>",
                f"• <b>Stars value:</b> <code>{self._esc(self._g(full_stats, 'stars_val'))}</code>",
            ])

            fav = self._g(full_stats, "favorite_chat")
            if fav is not None:
                full_lines.append(f"• <b>Любимый чат:</b> <code>{self._esc(self._g(fav, 'title'))}</code>")
                if self._g(fav, "username"):
                    full_lines.append(f"• <b>Юзернейм чата:</b> <code>@{self._esc(self._g(fav, 'username'))}</code>")

            media_usage = self._g(full_stats, "media_usage")
            if media_usage is not None:
                if isinstance(media_usage, list):
                    media_usage = ", ".join(map(str, media_usage))
                full_lines.append(f"• <b>Media usage:</b> <code>{self._esc(media_usage)}</code>")

            about = self._g(full_stats, "about")
            if about is not None:
                full_lines.append(f"• <b>Bio:</b> <code>{self._short(about, 90)}</code>")
        else:
            full_lines.append("• <b>Нет данных</b>")

        history_lines = []
        history_lines.append("• <b>Юзернеймы:</b>")
        history_lines.append(self._format_history_items(usernames, kind="user"))
        history_lines.append("")
        history_lines.append("• <b>Имена:</b>")
        history_lines.append(self._format_history_items(names, kind="name"))

        usage_lines = []
        if usage is not None:
            actual_users = self._g(usage, "actual_users", []) or []
            past_users = self._g(usage, "usage_by_users_in_the_past", []) or []
            actual_groups = self._g(usage, "actual_groups_or_channels", []) or []
            mentions = self._g(usage, "mention_by_channel_or_group_desc", []) or []

            usage_lines.extend([
                f"• <b>Актуальные пользователи:</b> <code>{len(actual_users)}</code>",
                f"• <b>Прошлые пользователи:</b> <code>{len(past_users)}</code>",
                f"• <b>Группы/каналы:</b> <code>{len(actual_groups)}</code>",
                f"• <b>Упоминания в описаниях:</b> <code>{len(mentions)}</code>",
            ])
        else:
            usage_lines.append("• <b>Нет данных</b>")

        text = (
            f"<b>👤 WHOIS • {self._esc(target)}</b>\n\n"
            f"<blockquote expandable>\n"
            f"<b>Профиль</b>\n"
            + "\n".join(profile_lines) +
            f"\n</blockquote>\n"
            f"<blockquote expandable>\n"
            f"<b>Статистика</b>\n"
            + "\n".join(min_lines) +
            "\n"
            + "\n".join(full_lines) +
            f"\n</blockquote>\n"
            f"<blockquote expandable>\n"
            f"<b>Использование ника</b>\n"
            + "\n".join(usage_lines) +
            f"\n</blockquote>\n"
            f"<blockquote expandable>\n"
            f"<b>История</b>\n"
            + "\n".join(history_lines) +
            f"\n</blockquote>"
        )
        return text

    def _fetch_info(self, query):
        token = self.get("funstat_token")
        if not token:
            return {"error": "no_token"}

        normalized = self._normalize_target(query)

        resolved = None
        min_stats = None
        full_stats = None
        names = None
        usernames = None
        usage = None
        error = None

        try:
            with FunstatClient(token) as api:
                api._session.verify = False

                stats_target = normalized

                try:
                    rr = api.resolve_username(normalized)
                    resolved = self._first(self._g(rr, "data", None))
                    if resolved is not None and self._g(resolved, "id", None) is not None:
                        stats_target = str(self._g(resolved, "id"))
                except Exception:
                    resolved = None

                try:
                    mr = api.stats_min(stats_target)
                    min_stats = self._g(mr, "data", None)
                except Exception as e:
                    error = error or str(e)

                try:
                    fr = api.stats(stats_target)
                    full_stats = self._g(fr, "data", None)
                except Exception as e:
                    error = error or str(e)

                try:
                    nr = api.get_names(stats_target)
                    names = self._g(nr, "data", None)
                except Exception:
                    names = None

                try:
                    ur = api.get_usernames(stats_target)
                    usernames = self._g(ur, "data", None)
                except Exception:
                    usernames = None

                if normalized and not normalized.isdigit():
                    try:
                        uu = api.username_usage(normalized.lstrip("@"))
                        usage = self._g(uu, "data", None)
                    except Exception:
                        usage = None

        except Exception as e:
            return {"error": str(e)}

        return {
            "error": error,
            "query": query,
            "normalized": normalized,
            "resolved": resolved,
            "min_stats": min_stats,
            "full_stats": full_stats,
            "names": names,
            "usernames": usernames,
            "usage": usage,
        }

    @loader.command(ru_doc="Сохранить токен Funstat")
    async def settoken(self, message):
        args = utils.get_args_raw(message).strip()
        if not args:
            await utils.answer(message, self.strings["need_arg"])
            return

        self.set("funstat_token", args)
        await utils.answer(message, self.strings["saved"])

    @loader.command(ru_doc="Показать информацию о пользователе из Funstat")
    async def whois(self, message):
        query = utils.get_args_raw(message).strip()

        if not query:
            try:
                reply = await message.get_reply_message()
            except Exception:
                reply = None

            if reply is not None:
                sender = None
                try:
                    sender = await reply.get_sender()
                except Exception:
                    sender = None

                if sender is not None:
                    username = getattr(sender, "username", None)
                    if username:
                        query = f"@{username}"
                    else:
                        sid = getattr(sender, "id", None)
                        if sid is not None:
                            query = str(sid)
                if not query:
                    sid = getattr(reply, "sender_id", None)
                    if sid is not None:
                        query = str(sid)

        if not query:
            await utils.answer(message, self.strings["invalid"])
            return

        token = self.get("funstat_token")
        if not token:
            await utils.answer(message, self.strings["no_token"])
            return

        await utils.answer(message, self.strings["loading"])

        data = await asyncio.to_thread(self._fetch_info, query)

        if data.get("error") == "no_token":
            await utils.answer(message, self.strings["no_token"])
            return

        if data.get("resolved") is None and data.get("min_stats") is None and data.get("full_stats") is None:
            err = data.get("error")
            if err:
                await utils.answer(message, self.strings["error"].format(self._esc(err)))
            else:
                await utils.answer(message, self.strings["not_found"])
            return

        report = self._build_report(
            query=data.get("query") or query,
            resolved=data.get("resolved"),
            min_stats=data.get("min_stats"),
            full_stats=data.get("full_stats"),
            names=data.get("names"),
            usernames=data.get("usernames"),
            usage=data.get("usage"),
        )

        await utils.answer(message, report)
