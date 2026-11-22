from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone


class Account(models.Model):
    class Type(models.TextChoices):
        CURRENT = "CURRENT", "Everyday Current Account"
        SAVINGS = "SAVINGS", "Smart Savings Account"
        PREMIER = "PREMIER", "Premier Account"

    class Status(models.TextChoices):
        ACTIVE = "ACTIVE"
        FROZEN = "FROZEN"

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="accounts")
    iban = models.CharField(max_length=23, unique=True)
    type = models.CharField(max_length=10, choices=Type.choices)
    nickname = models.CharField(max_length=40, blank=True)
    currency = models.CharField(max_length=3, default="AED")
    # Money is Decimal, never float: 0.1 + 0.2 != 0.3 in floating point.
    balance = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ACTIVE)
    opened_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["opened_at", "id"]

    def __str__(self) -> str:
        return f"{self.get_type_display()} {self.iban}"


class Transaction(models.Model):
    """One line on a statement. Immutable: corrections are new transactions, never edits."""

    class Direction(models.TextChoices):
        CREDIT = "CREDIT"  # money in
        DEBIT = "DEBIT"  # money out

    class Category(models.TextChoices):
        SALARY = "SALARY"
        TRANSFER_IN = "TRANSFER_IN"
        TRANSFER_OUT = "TRANSFER_OUT"
        CARD = "CARD"
        BILL = "BILL"
        ATM = "ATM"
        FEE = "FEE"
        INTEREST = "INTEREST"

    account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name="transactions")
    direction = models.CharField(max_length=6, choices=Direction.choices)
    category = models.CharField(max_length=12, choices=Category.choices)
    amount = models.DecimalField(
        max_digits=14, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))]
    )
    balance_after = models.DecimalField(max_digits=14, decimal_places=2)
    description = models.CharField(max_length=140)
    counterparty = models.CharField(max_length=140, blank=True)
    reference = models.CharField(max_length=32, unique=True)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [
            models.CheckConstraint(condition=models.Q(amount__gt=0), name="transaction_amount_positive"),
        ]

    def __str__(self) -> str:
        return f"{self.reference} {self.direction} {self.amount}"

    @property
    def signed_amount(self) -> Decimal:
        return self.amount if self.direction == self.Direction.CREDIT else -self.amount
