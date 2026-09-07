"""Run with RUN_BROWSER_TESTS=1 after playwright install chromium."""
import os
import asyncio
import sys
from io import BytesIO
from PIL import Image
from pathlib import Path
from unittest import skipUnless

from channels.testing import ChannelsLiveServerTestCase
from django.test import override_settings
from django.utils import timezone
from playwright.sync_api import sync_playwright, expect

from .models import Household, User


@skipUnless(os.environ.get("RUN_BROWSER_TESTS") == "1", "Enable RUN_BROWSER_TESTS for Chromium UI tests")
class BrowserTests(ChannelsLiveServerTestCase):
    def setUp(self):
        Household.objects.get_or_create(pk=1)
        User.objects.create_user(username="Admin", password="123456", role="primary_admin")
        User.objects.create_user(username="Alex", password="234567")

    def flow(self, width):
        # Daphne selects a Windows selector loop; Playwright needs subprocess support.
        if sys.platform == "win32":
            policy = asyncio.get_event_loop_policy()
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
            self.addCleanup(asyncio.set_event_loop_policy, policy)
        with sync_playwright() as runtime:
            browser = runtime.chromium.launch(headless=True)
            browser.on("disconnected", lambda: None)
            admin_context = browser.new_context(viewport={"width": width, "height": 900})
            member_context = browser.new_context(viewport={"width": width, "height": 900})
            admin = admin_context.new_page()
            member = member_context.new_page()
            for page, username, pin in ((admin, "Admin", "123456"), (member, "Alex", "234567")):
                page.goto(self.live_server_url + "/login/")
                page.get_by_label("Username").fill(username)
                page.get_by_label("PIN").fill(pin)
                page.get_by_role("button", name="Log in", exact=True).click()
                expect(page.get_by_role("link", name="Dashboard", exact=True)).to_be_visible()
            admin.get_by_role("link", name="Create and assign chore", exact=True).click()
            admin.get_by_label("Title").fill("Browser dishes")
            admin.get_by_label("Category").select_option("kitchen")
            admin.get_by_label("Priority").select_option("high")
            admin.get_by_label("Assignee").select_option(label="Alex")
            admin.get_by_label("Due date").fill(timezone.localdate().isoformat())
            admin.get_by_label("Requires approval").check()
            admin.get_by_label("Requires photo").check()
            admin.get_by_role("button", name="Save chore", exact=True).click()
            expect(admin.get_by_role("heading", name="Browser dishes", exact=True)).to_be_visible()
            chore_url = admin.url
            expect(member.get_by_role("link", name="Browser dishes", exact=True)).to_be_visible()
            member.get_by_label("Category").select_option("bathroom")
            member.get_by_role("button", name="Apply filters").click()
            expect(member.get_by_role("link", name="Browser dishes", exact=True)).to_have_count(0)
            member.get_by_label("Category").select_option("kitchen")
            member.get_by_label("Priority").select_option("high")
            member.get_by_role("button", name="Apply filters").click()
            member.get_by_role("link", name="Browser dishes", exact=True).click()
            member.get_by_label("Completion note (optional)").fill("First attempt")
            image = BytesIO()
            Image.new("RGB", (8, 8), "green").save(image, "PNG")
            proof = {"name": "proof.png", "mimeType": "image/png", "buffer": image.getvalue()}
            member.get_by_label("Completion photo (JPEG, PNG, WebP; up to 5 MB)").set_input_files(proof)
            member.get_by_role("button", name="Submit completion", exact=True).click()
            expect(member.get_by_text("Submitted on time", exact=True)).to_be_visible()
            admin.reload()
            admin.get_by_label("Rejection reason").fill("Clean the edges")
            admin.get_by_role("button", name="Reject", exact=True).click()
            member.reload()
            expect(member.get_by_text("Rejection reason: Clean the edges", exact=True)).to_be_visible()
            member.get_by_label("Completion photo (JPEG, PNG, WebP; up to 5 MB)").set_input_files(proof)
            member.get_by_role("button", name="Submit completion", exact=True).click()
            admin.goto(chore_url)
            admin.get_by_role("button", name="Approve", exact=True).click()
            member.get_by_role("link", name="Dashboard", exact=True).click()
            expect(member.get_by_role("link", name="Browser dishes", exact=True)).to_have_count(0)
            admin.get_by_role("link", name="Dashboard", exact=True).click()
            admin.get_by_label("Sort members").select_option("workload")
            admin.get_by_role("button", name="Apply filters").click()
            expect(admin.get_by_role("region", name="Member workload")).to_contain_text("Alex")
            self.assertTrue(admin.evaluate("document.documentElement.scrollWidth <= window.innerWidth"))
            target = Path(".artifacts")
            target.mkdir(exist_ok=True)
            admin.screenshot(path=str(target / f"dashboard-{width}.png"), full_page=True)
            browser.close()


    def test_desktop_flow(self):
        self.flow(1280)

    def test_mobile_flow(self):
        self.flow(390)
