# meta developer: @shaatimi

from .. import loader, utils
import asyncio
import random

@loader.tds
class TagAllModule(loader.Module):
    strings = {
        "name": "TagAll"
    }

    EMOJIS = [
        "❤️","🔥","⚡","🌟","💎","🚀","🎯","🖤","💥","✨",
        "🌈","🧩","🍀","🌊","☀️","🌙","⭐","🎵","🍓","🦋",
        "🐍","🐺","🦅","🐉","👑","🥷","🎭","🧠","🪐","🌌"
    ]

    @loader.command()
    async def tagall(self, message):
        text = utils.get_args_raw(message)
        chat = await message.get_chat()
        users = []

        async for user in message.client.iter_participants(chat):
            if not user.bot:
                users.append(user)

        chunk_size = 5
        chunks = [users[i:i+chunk_size] for i in range(0, len(users), chunk_size)]

        for chunk in chunks:
            emojis = random.sample(self.EMOJIS, k=min(len(chunk), len(self.EMOJIS)))
            msg = []

            for i, user in enumerate(chunk):
                mention = f"<a href='tg://user?id={user.id}'>{emojis[i]}</a>"
                msg.append(mention)

            if text:
                final_text = f"{', '.join(msg)} {text}"
            else:
                final_text = ", ".join(msg)

            await message.client.send_message(
                message.chat_id,
                final_text,
                parse_mode="html"
            )

            await asyncio.sleep(0.1)
