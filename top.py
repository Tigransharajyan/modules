# meta developer: @shaatimi
# scope: hikka_min 1.6.2
# requires: matplotlib

from hikkatl.types import Message, PeerUser, PeerChat, PeerChannel
from .. import loader, utils

from collections import defaultdict
import matplotlib.pyplot as plt
import io
import asyncio
import warnings
import numpy as np
from matplotlib.colors import LinearSegmentedColormap
from telethon.tl.functions.messages import GetHistoryRequest
from telethon.tl.types import InputMessagesFilterEmpty

plt.style.use('dark_background')

@loader.tds
class Top(loader.Module):
    """Module for viewing the top list in chat"""
    strings = {
        "name": "Top",
        "top": "Top users by message count",
        "topchat": "<emoji document_id=5323538339062628165>💬</emoji><b>Top users in</b>",
        "msgcount": "Message count",
        "loading": "<emoji document_id=5780543148782522693>🕒</emoji><b>Message counting has started, please wait, it may take a long time if there are a lot of messages in the chat</b>",
        "private_chat": "<emoji document_id=5323538339062628165>💬</emoji><b>Message count in private chat with</b>"
    }

    strings_ru = {
        "top": "Топ пользователей по количеству сообщений",
        "topchat": "<emoji document_id=5323538339062628165>💬</emoji><b>Топ пользователей в</b>",
        "msgcount": "Количество сообщений",
        "loading": "<emoji document_id=5780543148782522693>🕒</emoji><b>Подсчет сообщений начался, пожалуйста подождите, это может занять много времени если в чате много сообщений</b>",
        "private_chat": "<emoji document_id=5323538339062628165>💬</emoji><b>Количество сообщений в личном чате с</b>"
    }

    @loader.command(ru_doc="Посмотреть топ в чате")
    async def top(self, m: Message):
        await utils.answer(m, self.strings['loading'])
        client = self.client

        if isinstance(m.peer_id, PeerUser):
            chat_type = 'private'
            chat_id = m.peer_id.user_id
        elif isinstance(m.peer_id, PeerChat) or isinstance(m.peer_id, PeerChannel):
            chat_type = 'chat'
            chat_id = m.chat.id
        else:
            await utils.answer(m, "Unsupported chat type.")
            return

        if chat_type == 'chat':
            participants = await client.get_participants(chat_id)
            user_dict = {p.id: (p.first_name or p.username or "Unknown", getattr(p, 'bot', False)) for p in participants}
            message_counts = defaultdict(int)
            offset_id = 0
            limit = 100

            while True:
                history = await client(GetHistoryRequest(
                    peer=chat_id,
                    limit=limit,
                    offset_id=offset_id,
                    add_offset=0,
                    max_id=0,
                    min_id=0,
                    hash=0
                ))

                if not history.messages:
                    break

                for msg in history.messages:
                    if msg.sender_id and msg.sender_id in user_dict and not user_dict[msg.sender_id][1]:
                        message_counts[msg.sender_id] += 1

                offset_id = history.messages[-1].id
                if len(history.messages) < limit:
                    break

            sorted_counts = sorted(message_counts.items(), key=lambda x: x[1], reverse=True)[:20]
            usernames = [user_dict[uid][0] for uid, _ in sorted_counts]
            counts = [cnt for _, cnt in sorted_counts]

            fig, ax = plt.subplots(figsize=(10, 5))
            colors = self._generate_gradient('#8A2BE2', '#4B0082', len(usernames))
            bars = ax.barh(usernames, counts, color=colors, edgecolor='black', linewidth=0.5)
            for bar in bars:
                bar.set_alpha(0.8)
                bar.set_hatch('///')

            ax.set_xlabel(self.strings['msgcount'], fontsize=12, color='white')
            ax.set_title(self.strings['top'], fontsize=14, color='white', pad=20)
            ax.invert_yaxis()
            ax.spines['top'].set_visible(False)
            ax.spines['right'].set_visible(False)
            ax.spines['left'].set_color('#8A2BE2')
            ax.spines['bottom'].set_color('#8A2BE2')
            ax.grid(True, linestyle='--', alpha=0.6, color='gray')

            for i, (bar, username) in enumerate(zip(bars, usernames)):
                if i < 3:
                    bar.set_color('#FFD700')
                    ax.text(bar.get_width() + 5, bar.get_y() + bar.get_height() / 2,
                            f'#{i+1}', va='center', ha='left', color='#FFD700', fontsize=12)

            buf = io.BytesIO()
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore")
                plt.savefig(buf, format='png', bbox_inches='tight', dpi=100)
            buf.seek(0)

            caption = f"{self.strings['topchat']} <b>{m.chat.title}:</b>\n"
            caption += "\n".join([f"{i+1}. {user} - {count}" for i, (user, count) in enumerate(zip(usernames, counts))])
            await utils.answer_file(m, buf, caption, force_document=False)

        else:
            # private chat
            me = await client.get_me()
            target = await client.get_entity(chat_id)

            offset_id = 0
            limit = 100
            counts = {me.id: 0, target.id: 0}

            while True:
                history = await client(GetHistoryRequest(
                    peer=chat_id,
                    offset_id=offset_id,
                    offset_date=None,
                    add_offset=0,
                    limit=limit,
                    max_id=0,
                    min_id=0,
                    hash=0
                ))
                if not history.messages:
                    break

                for msg in history.messages:
                    if msg.sender_id in counts:
                        counts[msg.sender_id] += 1

                offset_id = history.messages[-1].id
                if len(history.messages) < limit:
                    break

            sorted_counts = sorted(counts.items(), key=lambda x: x[1], reverse=True)
            usernames = [me.first_name if uid == me.id else target.first_name for uid, _ in sorted_counts]
            counts_list = [cnt for _, cnt in sorted_counts]

            fig, ax = plt.subplots(figsize=(10, 5))
            colors = self._generate_gradient('#8A2BE2', '#4B0082', len(usernames))
            bars = ax.barh(usernames, counts_list, color=colors, edgecolor='black', linewidth=0.5)
            for bar in bars:
                bar.set_alpha(0.8)
                bar.set_hatch('///')

            ax.set_xlabel(self.strings['msgcount'], fontsize=12, color='white')
            ax.set_title(self.strings['top'], fontsize=14, color='white', pad=20)
            ax.invert_yaxis()
            ax.spines['top'].set_visible(False)
            ax.spines['right'].set_visible(False)
            ax.spines['left'].set_color('#8A2BE2')
            ax.spines['bottom'].set_color('#8A2BE2')
            ax.grid(True, linestyle='--', alpha=0.6, color='gray')

            for i, (bar, username) in enumerate(zip(bars, usernames)):
                if i < 3:
                    bar.set_color('#FFD700')
                    ax.text(bar.get_width() + 5, bar.get_y() + bar.get_height() / 2,
                            f'#{i+1}', va='center', ha='left', color='#FFD700', fontsize=12)

            buf = io.BytesIO()
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore")
                plt.savefig(buf, format='png', bbox_inches='tight', dpi=100)
            buf.seek(0)

            caption = f"{self.strings['private_chat']} <b>{target.first_name}:</b>\n"
            caption += "\n".join([f'"{user}" - {count}' for user, count in zip(usernames, counts_list)])
            await utils.answer_file(m, buf, caption, force_document=False)

    def _generate_gradient(self, start_color, end_color, n):
        cmap = LinearSegmentedColormap.from_list('custom_gradient', [start_color, end_color], N=n)
        return [cmap(i) for i in np.linspace(0, 1, n)]
