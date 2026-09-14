from django.db.models import Count, Q
from django.utils import timezone

from .completion import status_label
from .models import Chore, User
from .services import visible_chores


def workload(actor, sort=""):
    if not actor.is_household_admin:
        return User.objects.none()
    active = Q(assigned_chores__deleted_at__isnull=True) & ~Q(assigned_chores__status="completed")
    members = User.objects.filter(household=actor.household).annotate(
        low=Count("assigned_chores", filter=active & Q(assigned_chores__priority="low")),
        medium=Count("assigned_chores", filter=active & Q(assigned_chores__priority="medium")),
        high=Count("assigned_chores", filter=active & Q(assigned_chores__priority="high")),
        total=Count("assigned_chores", filter=active),
    )
    return members.order_by("-total", "username") if sort == "workload" else members.order_by("username")


def dashboard_data(actor, params):
    chores = visible_chores(actor=actor).exclude(status="completed").select_related("assignee").order_by("due_date", "pk")
    if params.get("category") in Chore.Category.values:
        chores = chores.filter(category=params["category"])
    if params.get("priority") in Chore.Priority.values:
        chores = chores.filter(priority=params["priority"])
    sections = {"Today": [], "Upcoming": [], "Overdue": [], "Pending approval": []}
    today = timezone.localdate()
    for chore in chores:
        chore.display_status = status_label(chore)
        if chore.status == "pending":
            section = "Overdue" if chore.display_status == "Rejected — overdue" else "Pending approval"
        else:
            section = "Today" if chore.due_date == today else "Overdue" if chore.due_date < today else "Upcoming"
        sections[section].append(chore)
    return {
        "sections": sections,
        "counts": {key: len(value) for key, value in sections.items()},
        "categories": Chore.Category.choices,
        "priorities": Chore.Priority.choices,
        "workload": workload(actor, params.get("sort")),
        "locked_count": User.objects.filter(household=actor.household, role="member", locked_at__isnull=False).count() if actor.is_household_admin else 0,
        "catchups": visible_chores(actor=actor).filter(catchup_pending=True, status="completed") if actor.is_household_admin else [],
    }
