from datetime import timedelta
from io import BytesIO
from tempfile import TemporaryDirectory

from PIL import Image
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone
from drf_spectacular.generators import SchemaGenerator
from rest_framework.test import APIClient

from .models import User, Chore, Notification
from .api import CHORE_EXAMPLE, USER_EXAMPLE
from .api_serializers import ChoreOutput, UserOutput


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class APITests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(username="Admin", role="primary_admin", password="123456")
        self.member = User.objects.create_user(username="Alex", password="234567")
        self.other = User.objects.create_user(username="Sam", password="345678")
        self.client = APIClient()
        self.actor(self.admin)

    def actor(self, actor):
        self.client.credentials(HTTP_X_DEMO_ACTOR=str(actor.pk))

    def create(self, **extra):
        response = self.client.post("/api/chores/", {"title": "Dishes", "assignee": self.member.pk, "due_date": timezone.localdate().isoformat(), **extra}, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        return response.data["id"]

    def test_local_demo_boundary_and_member_roles(self):
        self.client.credentials()
        self.assertEqual(self.client.get("/api/chores/").status_code, 400)
        self.actor(self.admin)
        result = self.client.post("/api/members/", {"username": "New", "pin": "456789"}, format="json")
        self.assertEqual(result.status_code, 201)
        pk = result.data["id"]
        self.assertNotIn("password", result.data)
        self.assertEqual(self.client.get(f"/api/members/{pk}/").status_code, 200)
        self.assertEqual(self.client.post(f"/api/members/{pk}/role/", {"role": "admin"}, format="json").status_code, 200)
        self.actor(User.objects.get(pk=pk))
        self.assertEqual(self.client.post(f"/api/members/{self.other.pk}/role/", {"role": "admin"}, format="json").status_code, 403)
        self.actor(self.admin)
        self.client.post(f"/api/members/{pk}/role/", {"role": "member"}, format="json")
        reset = self.client.post(f"/api/members/{pk}/reset/", {}, format="json")
        self.assertRegex(reset.data["pin"], r"^[1-9][0-9]{5}$")
        self.assertEqual(reset["Cache-Control"], "no-store")
        User.objects.filter(pk=pk).update(locked_at=timezone.now(), failed_login_attempts=10)
        self.assertEqual(self.client.post(f"/api/members/{pk}/unlock/", {}, format="json").status_code, 200)
        self.actor(self.member)
        self.assertEqual(self.client.get("/api/members/").status_code, 403)
        self.assertEqual(self.client.post("/api/me/pin/", {"current_pin": "234567", "new_pin": "567891"}, format="json").status_code, 200)

    def test_chore_crud_ownership_and_audit(self):
        pk = self.create()
        url = f"/api/chores/{pk}/"
        self.assertEqual(self.client.patch(url, {"priority": "high"}, format="json").status_code, 400)
        self.assertEqual(self.client.patch(url, {"priority": "high", "note": "Guests"}, format="json").status_code, 200)
        self.assertEqual(len(self.client.get("/api/chores/?q=Dishes").data), 1)
        self.actor(self.other)
        self.assertEqual(self.client.get(url).status_code, 404)
        self.actor(self.member)
        self.assertEqual(self.client.get(url).status_code, 200)
        self.assertEqual(self.client.delete(url).status_code, 403)
        self.actor(self.admin)
        copy = self.client.post(url + "duplicate/", {"assignee": self.other.pk, "due_date": timezone.localdate().isoformat()}, format="json")
        self.assertEqual(copy.status_code, 201)
        self.assertEqual(self.client.delete(url).status_code, 200)
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertTrue(any(item["action"] == "chore_deleted" for item in self.client.get("/api/history/").data))

    def test_completion_review_undo_reactivate_and_attempts(self):
        pk = self.create(requires_approval=True)
        url = f"/api/chores/{pk}/"
        self.actor(self.member)
        self.assertEqual(self.client.post(url + "submit/", {"note": "First"}, format="json").data["status"], "pending")
        self.assertEqual(self.client.post(url + "submit/", {}, format="json").status_code, 400)
        self.actor(self.admin)
        self.assertEqual(self.client.post(url + "reject/", {}, format="json").status_code, 400)
        self.assertEqual(self.client.post(url + "reject/", {"reason": "Again"}, format="json").status_code, 200)
        self.actor(self.member)
        self.client.post(url + "submit/", {}, format="json")
        self.actor(self.admin)
        self.assertEqual(self.client.post(url + "approve/", {}, format="json").data["status"], "completed")
        self.assertEqual(len(self.client.get(url + "attempts/").data), 2)
        self.assertEqual(self.client.post(url + "reactivate/", {"note": "Repeat"}, format="json").data["status"], "open")
        pk = self.create()
        self.actor(self.member)
        url = f"/api/chores/{pk}/"
        self.client.post(url + "submit/", {}, format="json")
        self.assertEqual(self.client.post(url + "undo/", {}, format="json").data["status"], "open")

    def test_recurrence_dashboards_reminders_and_notifications(self):
        result = self.client.post("/api/chores/bulk/", {"title": "Laundry", "assignees": [self.member.pk, self.other.pk], "frequency": "daily", "due_date": (timezone.localdate() - timedelta(days=2)).isoformat()}, format="json")
        self.assertEqual(result.status_code, 201, result.data)
        pk = result.data[0]["id"]
        url = f"/api/chores/{pk}/"
        self.assertEqual(self.client.post(url + "pause/", {}, format="json").status_code, 400)
        self.assertEqual(self.client.post(url + "pause/", {"reason": "Away"}, format="json").status_code, 200)
        self.assertEqual(self.client.post(url + "resume/", {}, format="json").status_code, 200)
        self.client.post(url + "submit/", {}, format="json")
        self.assertEqual(self.client.post(url + "catchup/", {"choice": "all"}, format="json").status_code, 200)
        for endpoint in ("schedule", "dashboard", "workload", "history", "notifications"):
            self.assertEqual(self.client.get(f"/api/{endpoint}/").status_code, 200)
        self.actor(self.member)
        notification = self.client.get("/api/notifications/").data[0]
        self.assertIsNotNone(self.client.get(f"/api/notifications/{notification['id']}/").data["read_at"])
        self.actor(self.other)
        self.assertEqual(self.client.get(f"/api/notifications/{notification['id']}/").status_code, 404)

    def test_multipart_photo_and_access(self):
        pk = self.create(requires_photo=True)
        with TemporaryDirectory() as directory, override_settings(MEDIA_ROOT=directory):
            image = BytesIO()
            Image.new("RGB", (3, 3)).save(image, "PNG")
            self.actor(self.member)
            result = self.client.post(f"/api/chores/{pk}/submit/", {"photo": SimpleUploadedFile("proof.png", image.getvalue(), content_type="image/png")}, format="multipart")
            self.assertEqual(result.status_code, 200, result.data)
            attempt = Chore.objects.get(pk=pk).attempts.get()
            response = self.client.get(f"/api/photos/{attempt.pk}/")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(b"".join(response.streaming_content), image.getvalue())
            response.close()
            self.actor(self.other)
            self.assertEqual(self.client.get(f"/api/photos/{attempt.pk}/").status_code, 404)

    def test_schema_examples_cover_every_operation(self):
        schema = SchemaGenerator().get_schema(request=None, public=True)
        count = 0
        for path, methods in schema["paths"].items():
            for method, operation in methods.items():
                if method not in {"get", "post", "patch", "delete"}:
                    continue
                count += 1
                self.assertTrue(any(param["name"] == "X-Demo-Actor" for param in operation["parameters"]), path)
                response = operation["responses"].get("200", operation["responses"].get("201"))
                self.assertTrue(any(content.get("examples") for content in response["content"].values()), path)
                if method in {"post", "patch"}:
                    self.assertIn("requestBody", operation, path)
                    self.assertTrue(any(content.get("examples") for content in operation["requestBody"]["content"].values()), path)
        self.assertGreaterEqual(count, 30)
        self.assertEqual(set(CHORE_EXAMPLE), set(ChoreOutput().fields))
        self.assertEqual(set(USER_EXAMPLE), set(UserOutput().fields))
        self.assertEqual(self.client.get("/api/docs/").status_code, 200)
