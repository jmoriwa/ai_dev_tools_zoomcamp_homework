from django.core.management.base import BaseCommand
from chores.reminders import send_reminders


class Command(BaseCommand):
    help = "Deliver due and rejected-overdue reminders, safely repeatable."

    def handle(self, *args, **options):
        self.stdout.write(f"Delivered {send_reminders()} reminders.")
