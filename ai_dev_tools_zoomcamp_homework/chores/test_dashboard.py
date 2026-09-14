from datetime import timedelta
from django.test import TestCase
from django.utils import timezone
from .models import User
from . import completion, services
from .dashboard import dashboard_data


class DashboardTests(TestCase):
    def test_counts_pending_filter_and_workload(self):
        admin = User.objects.create_user(username="Admin", role="primary_admin")
        member = User.objects.create_user(username="Alex")
        other = User.objects.create_user(username="Sam")
        for delta in (-1, 0, 1):
            services.create_chore(actor=admin, assignee=member, due_date=timezone.localdate() + timedelta(days=delta), title=f"Chore {delta}", priority="high", category="kitchen")
        pending = services.create_chore(actor=admin, assignee=member, due_date=timezone.localdate() - timedelta(days=1), title="Pending", requires_approval=True)
        completion.submit(actor=member, chore=pending)
        data = dashboard_data(member, {})
        self.assertEqual(data["counts"], {"Today": 1, "Upcoming": 1, "Overdue": 1, "Pending approval": 1})
        self.assertEqual(sum(dashboard_data(other, {})["counts"].values()), 0)
        self.assertEqual(sum(dashboard_data(member, {"priority": "low"})["counts"].values()), 0)
        load = list(dashboard_data(admin, {"sort": "workload"})["workload"])
        self.assertEqual(load[0], member)
        self.assertEqual(load[0].high, 3)
        completion.review(actor=admin, chore=pending, approve=True)
        self.assertEqual(dashboard_data(member, {})["counts"]["Pending approval"], 0)
