import calendar
from datetime import timedelta

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .accounts import require_admin
from .models import Chore, RecurringSeries
from .services import DETAIL_FIELDS, create_chore, record, visible_chores


def interval(series):
    return timedelta(days=1 if series.frequency == "daily" else 7)


@transaction.atomic
def advance(chore, actor, choice=None):
    chore = Chore.objects.select_for_update().get(pk=chore.pk)
    if not chore.series_id or chore.recurrence_processed or chore.series.ended_at or chore.status != "completed":
        return []
    next_date = chore.scheduled_date + interval(chore.series)
    today = timezone.localdate()
    if next_date < today and choice is None:
        chore.catchup_pending = True
        chore.save(update_fields=["catchup_pending"])
        return []
    dates = []
    while next_date < today:
        if choice == "all":
            dates.append(next_date)
        next_date += interval(chore.series)
    dates.append(next_date)
    created = []
    for scheduled in dates:
        occurrence, new = Chore.objects.get_or_create(series=chore.series, scheduled_date=scheduled, defaults={"household": chore.household, "assignee": chore.assignee, "due_date": scheduled, **{key: getattr(chore, key) for key in DETAIL_FIELDS}})
        if new:
            record(actor, occurrence, "recurrence_created")
            created.append(occurrence)
    chore.recurrence_processed = True
    chore.catchup_pending = False
    chore.save(update_fields=["recurrence_processed", "catchup_pending"])
    return created


@transaction.atomic
def resolve_catchup(*, actor, chore, choice):
    require_admin(actor, chore)
    chore = Chore.objects.select_for_update().get(pk=chore.pk, deleted_at__isnull=True)
    if choice not in {"all", "skip"}:
        raise ValidationError("Choose all missed occurrences or skip missed occurrences.")
    if not chore.catchup_pending or chore.status != "completed":
        raise ValidationError("There is no catch-up decision awaiting action.")
    result = advance(chore, actor, choice)
    record(actor, chore, "recurrence_catchup", choice)
    return result


@transaction.atomic
def bulk_create(*, actor, assignees, frequency, due_date, **details):
    require_admin(actor)
    if frequency not in {"daily", "weekly"} or not assignees:
        raise ValidationError("Bulk assignment requires members and daily or weekly recurrence.")
    return [create_chore(actor=actor, assignee=member, due_date=due_date, frequency=frequency, **details) for member in set(assignees)]


def schedule_preview(*, actor):
    today = timezone.localdate()
    month = today.month % 12 + 1
    year = today.year + (today.month == 12)
    end = today.replace(year=year, month=month, day=min(today.day, calendar.monthrange(year, month)[1]))
    series_ids = visible_chores(actor=actor).exclude(series=None).values_list("series_id", flat=True)
    result = []
    for series in RecurringSeries.objects.filter(pk__in=series_ids, ended_at__isnull=True):
        last = series.occurrences.order_by("-scheduled_date").first()
        if last.deleted_at or last.catchup_pending:
            continue
        scheduled = last.scheduled_date + interval(series)
        while scheduled < today:
            scheduled += interval(series)
        while scheduled <= end:
            result.append({"title": last.title, "date": scheduled, "assignee": last.assignee.username, "series_id": series.pk})
            scheduled += interval(series)
    return sorted(result, key=lambda row: (row["date"], row["title"]))
