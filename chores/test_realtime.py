from asgiref.sync import sync_to_async
from channels.testing import WebsocketCommunicator
from channels.layers import get_channel_layer
from django.test import Client, TransactionTestCase, TestCase, override_settings
from django.db import transaction
from unittest.mock import patch

from config.asgi import application
from .models import User, Household


@override_settings(ALLOWED_HOSTS=["localhost"], PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class RealtimeTests(TransactionTestCase):
    def setUp(self):
        Household.objects.get_or_create(pk=1)
        self.member = User.objects.create_user(username="Alex", password="234567")
        self.other = User.objects.create_user(username="Sam", password="345678")
        self.admin = User.objects.create_user(username="Admin", password="123456", role="primary_admin")
        self.cookies = {}
        for user in (self.member, self.other, self.admin):
            client = Client()
            client.force_login(user)
            self.cookies[user.pk] = f"sessionid={client.session.session_key}".encode()

    def connection(self, user=None, path="/ws/household/", origin=b"http://localhost"):
        headers = [(b"origin", origin)]
        if user:
            headers.append((b"cookie", self.cookies[user.pk]))
        return WebsocketCommunicator(application, path, headers=headers)

    async def test_anonymous_and_foreign_origin_rejected(self):
        for socket in (self.connection(), self.connection(self.member, origin=b"https://evil.example")):
            connected, _ = await socket.connect()
            self.assertFalse(connected)
            await socket.disconnect()

    async def test_personal_groups_cannot_be_changed_by_client(self):
        socket = self.connection(self.other)
        self.assertTrue((await socket.connect())[0])
        await socket.send_json_to({"subscribe": f"user.{self.member.pk}"})
        self.assertEqual(await socket.receive_json_from(), {"type": "pong"})
        await get_channel_layer().group_send(f"user.{self.member.pk}", {"type": "household.changed"})
        self.assertTrue(await socket.receive_nothing(timeout=.1))
        await get_channel_layer().group_send(f"user.{self.other.pk}", {"type": "household.changed"})
        self.assertEqual(await socket.receive_json_from(), {"type": "refresh"})
        await socket.disconnect()

    async def test_admin_group_and_pin_invalidation(self):
        socket = self.connection(self.admin)
        self.assertTrue((await socket.connect())[0])
        await get_channel_layer().group_send("admins.1", {"type": "household.changed"})
        self.assertEqual(await socket.receive_json_from(), {"type": "refresh"})
        await sync_to_async(User.objects.filter(pk=self.admin.pk).update)(session_version=99, password="invalidated")
        await socket.send_json_to({"type": "ping"})
        self.assertEqual((await socket.receive_output())["type"], "websocket.close")
        await socket.disconnect()


class PublishTests(TestCase):
    def test_publish_waits_for_commit_and_rollback_discards(self):
        from .realtime import publish
        with patch("chores.realtime.async_to_sync") as send:
            with self.captureOnCommitCallbacks(execute=True):
                publish({123}, 1)
                self.assertFalse(send.called)
            self.assertTrue(send.called)
            send.reset_mock()
            with self.captureOnCommitCallbacks(execute=True):
                try:
                    with transaction.atomic():
                        publish({123}, 1)
                        raise ValueError
                except ValueError:
                    pass
            self.assertFalse(send.called)
