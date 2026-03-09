# meta developer: @shaatimi
# requires: telethon

from .. import loader, utils
import os
import re
from telethon.tl.types import User, Channel

@loader.tds
class DownloadHistoryMod(loader.Module):
    strings_ru = {
        "name": "DownloadHistory",
        "usage": "Использование:\n.download chat history -f \"текст\" (весь чат)\n.download history -f \"текст\" (юзер/ЛС)",
        "no_target": "Ответьте на сообщение или укажите ID/username.",
        "user_not_found": "Пользователь не найден.",
        "collecting": "Сбор данных...",
        "none_found": "Сообщения не найдены.",
        "error": "Ошибка: {e}",
    }

    strings = {
        "name": "DownloadHistory",
        "usage": "Usage:\n.download chat history -f \"text\" (full chat)\n.download history -f \"text\" (user/PM)",
        "no_target": "Reply to a message or specify ID/username.",
        "user_not_found": "User not found.",
        "collecting": "Collecting data...",
        "none_found": "No messages found.",
        "error": "Error: {e}",
    }

    def get_content_type(self, msg):
        if msg.text:
            return msg.text.replace("\n", " ")
        if msg.photo:
            return "PHOTO"
        if msg.gif:
            return "GIF"
        if msg.video:
            return "ROUND_VIDEO" if msg.video_note else "VIDEO"
        if msg.audio:
            return f"AUDIO: {getattr(msg.file, 'title', 'Track')}"
        if msg.voice:
            return "VOICE"
        if msg.sticker:
            emoji = getattr(msg.file, 'emoji', '')
            return f"STICKER: {emoji}" if emoji else "STICKER"
        if msg.document:
            name = getattr(msg.file, 'name', 'Unnamed')
            return f"FILE: {name}"
        return "OTHER"

    async def collect_messages(self, client, chat_id, from_user, query, status):
        buffer = []
        count = 0
        async for msg in client.iter_messages(chat_id, from_user=from_user, search=query):
            date = msg.date.strftime("%d/%m/%Y %H:%M:%S")
            content = self.get_content_type(msg)
            sender = await msg.get_sender()
            uid = getattr(sender, 'id', 0)
            uname = "Unknown"
            if isinstance(sender, User):
                uname = sender.first_name or "NoName"
            elif isinstance(sender, Channel):
                uname = sender.title or "Channel"

            link = (
                f"https://t.me/c/{str(chat_id)[4:]}/{msg.id}"
                if str(chat_id).startswith("-100")
                else f"tg://openmessage?user_id={chat_id}&message_id={msg.id}"
            )
            buffer.append(f"{uid} | {uname} | {date} | {content} | {link}\n")
            count += 1

            if count % 200 == 0:
                await status.edit(f"{self.strings['collecting']} {count}")

        return buffer, count

    @loader.command(
        ru_doc="Выгрузка истории с фильтрами",
        en_doc="Export history with filters",
    )
    async def download(self, message):
        raw_text = utils.get_args_raw(message) or ""
        match = re.search(r'-f\s+"(.*?)"|"(.*?)"', raw_text)
        query = match.group(1) or match.group(2) if match else None

        client = message.client
        chat = await message.get_chat()
        args = raw_text.split()
        mode = "chat" if "chat" in args and "history" in args else "user"

        from_user = None
        target_chat_id = chat.id

        # Если режим user, ищем конкретного пользователя
        if mode == "user":
            if message.is_reply:
                reply = await message.get_reply_message()
                sender = await reply.get_sender()
                from_user = sender.id if sender else None
            else:
                try:
                    target_str = args[1] if len(args) > 1 else args[0]
                    entity = await client.get_entity(target_str)
                    from_user = entity.id
                    # Если чат приватный, меняем target_chat_id на ЛС
                    if isinstance(entity, User):
                        target_chat_id = entity.id
                except:
                    await utils.answer(message, self.strings["no_target"])
                    return

            if not from_user:
                await utils.answer(message, self.strings["no_target"])
                return

        status = await utils.answer(message, self.strings["collecting"])
        filename = f"history_{target_chat_id}_{from_user or 'all'}.txt"

        try:
            buffer, count = await self.collect_messages(client, target_chat_id, from_user, query, status)
            if count == 0:
                await status.edit(self.strings["none_found"])
                return

            with open(filename, "w", encoding="utf-8") as f:
                f.writelines(buffer)

            caption = f"History Export\nTarget: {target_chat_id}\nFilter: {query or 'None'}\nTotal: {count}"
            await client.send_file(message.peer_id, filename, caption=caption)
            await status.delete()

        except Exception as e:
            await status.edit(self.strings["error"].format(e=str(e)))
        finally:
            if os.path.exists(filename):
                os.remove(filename)
