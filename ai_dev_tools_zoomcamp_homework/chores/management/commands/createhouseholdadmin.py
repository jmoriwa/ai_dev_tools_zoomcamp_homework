from getpass import getpass

from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import IntegrityError, transaction

from chores.accounts import validate_pin
from chores.models import User


class Command(BaseCommand):
    help = "Create the first household primary admin with a privately prompted PIN."

    def add_arguments(self, parser):
        parser.add_argument("username")

    def handle(self, *args, **options):
        if User.objects.filter(role=User.Role.PRIMARY_ADMIN).exists():
            raise CommandError("A primary admin already exists. Use member management for additional admins.")
        pin = getpass("PIN (six digits, no leading zero): ")
        try:
            validate_pin(pin)
            if pin != getpass("Confirm PIN: "):
                raise CommandError("PINs do not match.")
            with transaction.atomic():
                user = User(username=options["username"], role=User.Role.PRIMARY_ADMIN)
                user.set_password(pin)
                user.full_clean()
                user.save()
        except ValidationError as error:
            raise CommandError(" ".join(error.messages)) from error
        except IntegrityError as error:
            raise CommandError("Username or primary admin already exists.") from error
        self.stdout.write(self.style.SUCCESS("Primary admin created. Log in at /login/."))
