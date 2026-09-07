from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.contrib.sessions.backends.db import SessionStore
from django.utils.crypto import constant_time_compare

from .models import User


class HouseholdConsumer(AsyncJsonWebsocketConsumer):
    @database_sync_to_async
    def current_user(self):
        session = SessionStore(session_key=self.scope["session"].session_key).load()
        user = User.objects.filter(pk=session.get("_auth_user_id"), is_active=True, locked_at__isnull=True).first()
        if not user or not constant_time_compare(session.get("_auth_user_hash", ""), user.get_session_auth_hash()):
            return None
        if session.get("pin_session_version", user.session_version) != user.session_version:
            return None
        return user

    async def connect(self):
        self.joined = []
        user = await self.current_user()
        if not user:
            await self.close(code=4401)
            return
        self.user_id, self.role = user.pk, user.role
        self.joined = [f"user.{user.pk}"]
        if user.is_household_admin:
            self.joined.append(f"admins.{user.household_id}")
        for group in self.joined:
            await self.channel_layer.group_add(group, self.channel_name)
        await self.accept()

    async def disconnect(self, code):
        for group in self.joined:
            await self.channel_layer.group_discard(group, self.channel_name)

    async def authorized(self):
        user = await self.current_user()
        if not user or user.pk != self.user_id or user.role != self.role:
            await self.close(code=4401)
            return False
        return True

    async def receive_json(self, content, **kwargs):
        # Clients cannot choose another user, household, or subscription group.
        if await self.authorized():
            await self.send_json({"type": "pong"})

    async def household_changed(self, event):
        if await self.authorized():
            await self.send_json({"type": "refresh"})
