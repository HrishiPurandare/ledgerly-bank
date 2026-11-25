import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone

from banking.models import Account, Transaction


class Beneficiary(models.Model):
    """Someone the customer can send money to. Usable only after OTP confirmation."""

    class Status(models.TextChoices):
        PENDING = "PENDING"  # waiting for the OTP
        ACTIVE = "ACTIVE"
        LOCKED = "LOCKED"  # too many wrong OTPs: delete and add again

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="beneficiaries"
    )
    name = models.CharField(max_length=140)
    iban = models.CharField(max_length=23)
    nickname = models.CharField(max_length=40, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(default=timezone.now)
    activated_at = models.DateTimeField(
        null=True, blank=True
    )  # the 24-hour new-beneficiary limit starts here
    otp_hash = models.CharField(max_length=64, blank=True)
    otp_expires_at = models.DateTimeField(null=True, blank=True)
    otp_attempts = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["name", "id"]
        constraints = [
            models.UniqueConstraint(fields=["owner", "iban"], name="unique_beneficiary_per_customer")
        ]

    def __str__(self) -> str:
        return f"{self.name} {self.iban}"


class Transfer(models.Model):
    class Kind(models.TextChoices):
        OWN = "OWN"  # between the customer's own accounts
        INTERNAL = "INTERNAL"  # to another NovaBank customer: instant
        LOCAL = "LOCAL"  # to another UAE bank: sent as an ISO 20022 pacs.008 message

    class Status(models.TextChoices):
        COMPLETED = "COMPLETED"
        PENDING = "PENDING"  # handed to the payment network, not yet settled

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="transfers")
    reference = models.CharField(max_length=20, unique=True)
    # Unique end-to-end transaction reference: follows the payment through every bank (pacs.008 <UETR>).
    uetr = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    kind = models.CharField(max_length=10, choices=Kind.choices)
    status = models.CharField(max_length=10, choices=Status.choices)
    from_account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name="outgoing_transfers")
    to_account = models.ForeignKey(
        Account, on_delete=models.PROTECT, null=True, blank=True, related_name="incoming_transfers"
    )
    beneficiary = models.ForeignKey(Beneficiary, on_delete=models.SET_NULL, null=True, blank=True)
    creditor_name = models.CharField(max_length=140)
    creditor_iban = models.CharField(max_length=23)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    currency = models.CharField(max_length=3, default="AED")
    remarks = models.CharField(max_length=140, blank=True)
    idempotency_key = models.CharField(max_length=64)
    request_fingerprint = models.CharField(max_length=64)  # hash of the request body, to spot key reuse
    debit = models.OneToOneField(Transaction, on_delete=models.PROTECT, related_name="+")
    credit = models.OneToOneField(
        Transaction, on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["owner", "idempotency_key"], name="unique_idempotency_key_per_customer"
            ),
            models.CheckConstraint(condition=models.Q(amount__gt=0), name="transfer_amount_positive"),
        ]

    def __str__(self) -> str:
        return f"{self.reference} {self.amount} {self.currency}"
