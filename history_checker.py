# meta developer: @shaatimi

from .. import loader, utils
import os
import re
import asyncio
from telethon.tl.types import User, Channel

@loader.tds
class Download(loader.Module):
    strings_ru = {
        "name": "Download",
        "usage": "ℹ️ Использование:\n.download history \"текст\" (реплай)\n.download chat history \"текст\" (чат)",
        "no_target": "❌ Ответь на сообщение или укажи id/@user.",
        "user_not_found": "❌ Пользователь не найден.",
        "collecting_user": "⏳ Сбор сообщений {name}{filter}...",
        "collecting_chat": "⏳ Выгрузка истории чата{filter}: {title}...",
        "none_found": "❌ Сообщений не найдено.",
        "error": "❌ Ошибка: {e}",
    }

    strings = {
        "name": "Download",
        "usage": "ℹ️ Usage:\n.download history \"text\" (reply)\n.download chat history \"text\" (chat)",
        "no_target": "❌ Reply to a message or specify id/@user.",
        "user_not_found": "❌ User not found.",
        "collecting_user": "⏳ Collecting messages from {name}{filter}...",
        "collecting_chat": "⏳ Exporting chat history{filter}: {title}...",
        "none_found": "❌ No messages found.",
        "error": "❌ Error: {e}",
    }

    @loader.command(
        ru_doc="Выгрузка истории чата или пользователя",
        en_doc="Export chat or user message history",
    )
    async def download(self, message):
        text = utils.get_args_raw(message)
        args = text.split()

        query = None
        if '"' in text:
            m = re.findall(r'"(.*?)"', text)
            if m:
                query = m[0]

        client = message.client
        chat = await message.get_chat()

        if args[:2] == ["chat", "history"]:
            title = getattr(chat, "title", None) or "Chat"
            ftext = f" '{query}'" if query else ""
            status = await utils.answer(
                message,
                self.strings["collecting_chat"].format(filter=ftext, title=title)
            )

            filename = f"chat_{chat.id}.txt"
            count = 0
            is_private = not str(chat.id).startswith("-100")

            try:
                with open(filename, "w", encoding="utf-8") as f:
                    async for msg in client.iter_messages(chat.id, search=query):
                        sender = await msg.get_sender()
                        date = msg.date.strftime("%d/%m/%Y %H:%M:%S")

                        if isinstance(sender, User):
                            uid = sender.id
                            uname = sender.first_name or "NoName"
                        elif isinstance(sender, Channel):
                            uid = sender.id
                            uname = sender.title
                        else:
                            uid = 0
                            uname = "Service"

                        if msg.text:
                            content = msg.text.replace("\n", " ")
                        elif msg.media:
                            content = "media"
                        else:
                            content = "other"

                        if is_private:
                            link = f"tg://openmessage?user_id={chat.id}&message_id={msg.id}"
                        else:
                            link = f"https://t.me/c/{str(chat.id)[4:]}/{msg.id}"

                        f.write(f"{uid} | {uname} | {date} | {content} | {link}\n")
                        count += 1

                        if count % 100 == 0:
                            await status.edit(f"⏳ {count}...")

                if count == 0:
                    await status.edit(self.strings["none_found"])
                else:
                    await client.send_file(
                        chat.id,
                        filename,
                        caption=f"📂 Chat history\n🔍 Filter: {query or 'NONE'}\n📊 Total: {count}",
                    )
                    await status.delete()

            except Exception as e:
                await status.edit(self.strings["error"].format(e=str(e)))
            finally:
                if os.path.exists(filename):
                    os.remove(filename)
            return

        if args[:1] == ["history"]:
            target = None

            if message.is_reply:
                reply = await message.get_reply_message()
                target = await reply.get_sender()
            elif len(args) >= 2:
                try:
                    target = await client.get_entity(args[1])
                except:
                    await utils.answer(message, self.strings["user_not_found"])
                    return

            if not target:
                await utils.answer(message, self.strings["no_target"])
                return

            ftext = f" '{query}'" if query else ""
            status = await utils.answer(
                message,
                self.strings["collecting_user"].format(
                    name=target.first_name or "User",
                    filter=ftext
                )
            )

            filename = f"user_{target.id}.txt"
            total = 0

            try:
                with open(filename, "w", encoding="utf-8") as f:
                    async for msg in client.iter_messages(
                        chat.id,
                        from_user=target.id,
                        search=query
                    ):
                        date = msg.date.strftime("%d/%m/%Y %H:%M:%S")
                        content = msg.text.replace("\n", " ") if msg.text else "media"

                        if str(chat.id).startswith("-100"):
                            link = f"https://t.me/c/{str(chat.id)[4:]}/{msg.id}"
                        else:
                            link = f"tg://openmessage?user_id={target.id}&message_id={msg.id}"

                        f.write(
                            f"{target.id} | {target.first_name} | {date} | {content} | {link}\n"
                        )
                        total += 1

                        if total % 100 == 0:
                            await status.edit(f"⏳ {total}...")

                if total == 0:
                    await status.edit(self.strings["none_found"])
                else:
                    await client.send_file(
                        chat.id,
                        filename,
                        caption=f"👤 User history\n🔍 Filter: {query or 'NONE'}\n📊 Total: {total}",
                    )
                    await status.delete()

            except Exception as e:
                await status.edit(self.strings["error"].format(e=str(e)))
            finally:
                if os.path.exists(filename):
                    os.remove(filename)
            return

        await utils.answer(message, self.strings["usage"])
