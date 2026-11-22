import os
from datetime import date

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from banking.seed import CUSTOMERS, DEMO_PASSWORD, reset, seed


class Command(BaseCommand):
    help = "Create demo customers, accounts and 90 days of transactions (deterministic)."

    def add_arguments(self, parser):
        parser.add_argument("--seed", type=int, default=42, help="same seed, same data")
        parser.add_argument(
            "--today", type=date.fromisoformat, help="anchor date YYYY-MM-DD (default: today)"
        )
        parser.add_argument("--reset", action="store_true", help="delete the demo customers first")

    def handle(self, *args, **options):
        # Known passwords must never reach a real environment.
        if not settings.DEBUG and os.getenv("LEDGERLY_ALLOW_SEED") != "true":
            raise CommandError(
                "Refusing to seed demo users with DEBUG off. Set LEDGERLY_ALLOW_SEED=true to override."
            )
        if options["reset"]:
            reset()
        elif get_user_model().objects.filter(email__in=[c.email for c in CUSTOMERS]).exists():
            raise CommandError("Demo customers already exist. Use --reset to recreate them.")
        summary = seed(seed_value=options["seed"], today=options["today"])
        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded {summary['customers']} customers, {summary['accounts']} accounts, "
                f"{summary['transactions']} transactions. Password for all: {DEMO_PASSWORD}"
            )
        )
