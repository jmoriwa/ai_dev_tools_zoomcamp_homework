from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db import transaction
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from .models import Chore, Notification, User


def publish(user_ids, household_id, admins=True):
    groups = {f"user.{pk}" for pk in user_ids if pk}
    if admins:
        groups.add(f"admins.{household_id}")
    def send():
        layer = get_channel_layer()
        for group in groups:
            async_to_sync(layer.group_send)(group, {"type": "household.changed"})
    transaction.on_commit(send)


@receiver(pre_save, sender=Chore)
def remember_assignee(sender, instance, **kwargs):
    instance._old_assignee_id = Chore.objects.filter(pk=instance.pk).values_list("assignee_id", flat=True).first() if instance.pk else None


@receiver(post_save, sender=Chore)
def chore_changed(sender, instance, **kwargs):
    publish({instance.assignee_id, getattr(instance, "_old_assignee_id", None)}, instance.household_id)


@receiver(post_save, sender=Notification)
def notification_changed(sender, instance, **kwargs):
    publish({instance.recipient_id}, None, admins=False)


@receiver(post_save, sender=User)
def user_changed(sender, instance, **kwargs):
    publish({instance.pk}, instance.household_id)
