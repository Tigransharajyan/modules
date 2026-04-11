# meta developer: @shaatimi

from .. import loader, utils


@loader.tds
class PMFilter(loader.Module):
    strings = {
        "name": "PMFilter",
        "no_target": "<b>❌ Не удалось определить пользователя.</b>",
        "denied": "<b>Давай пиши пиши</b>",
        "allowed": "<b>Ладно пиши</b>",
        "already_denied": "<b>ℹ️ Этот пользователь уже в списке.</b>",
        "not_denied": "<b>ℹ️ Этот пользователь не был в списке.</b>",
        "need_arg": "<b>❌ Укажи пользователя, либо используй команду в личке или ответом на сообщение.</b>",
    }

    def _denylist(self):
        return set(self.get("deny_pm", []))

    def _save_denylist(self, denyset):
        self.set("deny_pm", sorted(list(denyset)))

    async def _resolve_target(self, message, args):
        args = (args or "").strip()

        if args:
            try:
                entity = await self._client.get_entity(args)
                return getattr(entity, "id", None)
            except Exception:
                pass

        if message.is_private:
            peer = getattr(message, "peer_id", None)
            uid = getattr(peer, "user_id", None) if peer is not None else None
            if uid is not None:
                return uid

        try:
            reply = await message.get_reply_message()
        except Exception:
            reply = None

        if reply is not None:
            sender_id = getattr(reply, "sender_id", None)
            if sender_id is not None:
                return sender_id

        return None

    async def _toggle_pm(self, message, allow: bool):
        args = utils.get_args_raw(message)
        target_id = await self._resolve_target(message, args)

        if target_id is None:
            await utils.answer(message, self.strings["no_target"])
            return

        denyset = self._denylist()

        if allow:
            if target_id not in denyset:
                await utils.answer(message, self.strings["not_denied"])
                return
            denyset.discard(target_id)
            self._save_denylist(denyset)
            await utils.answer(message, self.strings["allowed"])
        else:
            if target_id in denyset:
                await utils.answer(message, self.strings["already_denied"])
                return
            denyset.add(target_id)
            self._save_denylist(denyset)
            await utils.answer(message, self.strings["denied"])

    @loader.command(ru_doc="Запретить ЛС от пользователя")
    async def denypm(self, message):
        await self._toggle_pm(message, allow=False)

    @loader.command(ru_doc="Разрешить ЛС от пользователя")
    async def allowpm(self, message):
        await self._toggle_pm(message, allow=True)

    @loader.watcher()
    async def watcher(self, message):
        if not getattr(message, "is_private", False):
            return

        if getattr(message, "out", False):
            return

        sender_id = getattr(message, "sender_id", None)
        if sender_id is None:
            peer = getattr(message, "peer_id", None)
            sender_id = getattr(peer, "user_id", None) if peer is not None else None

        if sender_id is None:
            return

        if sender_id in self._denylist():
            try:
                await message.delete()
            except Exception:
                try:
                    await self._client.delete_messages(message.chat_id, [message.id], revoke=True)
                except Exception:
                    pass
