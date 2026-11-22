"""Moving money. Every rule that can say "no" lives here, inside one database transaction."""

import hashlib
import json
import secrets
from datetime import datetime, timedelta
from decimal import Decimal

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from rest_framework.exceptions import NotFound

from banking.iban import is_valid_uae_iban, normalise
from banking.models import Account, Transaction
from payments import otp, rules
from payments.errors import TransferRejected
from payments.models import Beneficiary, Transfer

# ---------- beneficiaries ----------


def add_beneficiary(user, *, name: str, iban: str, nickname: str, now: datetime) -> Beneficiary:
    iban = normalise(iban)
    if not is_valid_uae_iban(iban):
        raise TransferRejected("invalid_iban", "Enter a valid UAE IBAN: AE followed by 21 digits.")
    if Account.objects.filter(owner=user, iban=iban).exists():
        raise TransferRejected(
            "own_account", "This is your own account. Use a transfer between your accounts."
        )
    if Beneficiary.objects.filter(owner=user, iban=iban).exists():
        raise TransferRejected("duplicate_beneficiary", "You already have a beneficiary with this IBAN.")
    if Beneficiary.objects.filter(owner=user).count() >= settings.LEDGERLY["MAX_BENEFICIARIES"]:
        raise TransferRejected("too_many_beneficiaries", "You can have up to 100 beneficiaries.")

    beneficiary = Beneficiary.objects.create(
        owner=user, name=name, iban=iban, nickname=nickname, created_at=now
    )
    code = otp.new_code()
    beneficiary.otp_hash = otp.hash_code(beneficiary.id, code)
    beneficiary.otp_expires_at = now + timedelta(minutes=settings.LEDGERLY["OTP_MINUTES"])
    beneficiary.save(update_fields=["otp_hash", "otp_expires_at"])
    otp.send(user.email, name, code)
    return beneficiary


def confirm_beneficiary(beneficiary: Beneficiary, code: str, now: datetime) -> Beneficiary:
    """No transaction on purpose: a wrong attempt must be saved even though we return an error."""
    if beneficiary.status == Beneficiary.Status.ACTIVE:
        raise TransferRejected("already_active", "This beneficiary is already confirmed.")
    if beneficiary.status == Beneficiary.Status.LOCKED:
        raise TransferRejected(
            "otp_locked", "Too many wrong codes. Delete this beneficiary and add it again."
        )
    if now > beneficiary.otp_expires_at:
        raise TransferRejected(
            "otp_expired", "This code has expired. Delete the beneficiary and add it again."
        )
    if not otp.matches(beneficiary.id, code, beneficiary.otp_hash):
        beneficiary.otp_attempts += 1
        if beneficiary.otp_attempts >= settings.LEDGERLY["OTP_MAX_ATTEMPTS"]:
            beneficiary.status = Beneficiary.Status.LOCKED
        beneficiary.save(update_fields=["otp_attempts", "status"])
        if beneficiary.status == Beneficiary.Status.LOCKED:
            raise TransferRejected(
                "otp_locked", "Too many wrong codes. Delete this beneficiary and add it again."
            )
        left = settings.LEDGERLY["OTP_MAX_ATTEMPTS"] - beneficiary.otp_attempts
        raise TransferRejected("otp_invalid", f"That code is wrong. {left} attempt(s) left.")
    beneficiary.status = Beneficiary.Status.ACTIVE
    beneficiary.activated_at = now
    beneficiary.otp_hash = ""
    beneficiary.save(update_fields=["status", "activated_at", "otp_hash"])
    return beneficiary


# ---------- transfers ----------


def fingerprint(data: dict) -> str:
    return hashlib.sha256(json.dumps(data, sort_keys=True, default=str).encode()).hexdigest()


def _replay_or_conflict(user, key: str, request_hash: str) -> Transfer | None:
    existing = Transfer.objects.filter(owner=user, idempotency_key=key).first()
    if existing and existing.request_fingerprint != request_hash:
        raise TransferRejected(
            "idempotency_key_reused", "This Idempotency-Key was already used for a different transfer.", 409
        )
    return existing


def create_transfer(user, data: dict, *, idempotency_key: str, now: datetime) -> tuple[Transfer, bool]:
    """Returns (transfer, replayed). Replaying the same request with the same key never moves money twice."""
    request_hash = fingerprint(data)
    if existing := _replay_or_conflict(user, idempotency_key, request_hash):
        return existing, True
    try:
        return _execute(user, data, idempotency_key, request_hash, now), False
    except IntegrityError:
        # Two identical requests raced; the other one won. Answer like a replay.
        if existing := _replay_or_conflict(user, idempotency_key, request_hash):
            return existing, True
        raise


@transaction.atomic
def _execute(user, data: dict, key: str, request_hash: str, now: datetime) -> Transfer:
    amount: Decimal = data["amount"]
    # Lock the customer first: two transfers from DIFFERENT accounts must not both pass the daily limit.
    get_user_model().objects.select_for_update().get(pk=user.pk)

    from_account = Account.objects.filter(owner=user, pk=data["from_account"]).first()
    if from_account is None:
        raise NotFound("Account not found.")

    beneficiary = None
    if data.get("to_account"):
        to_account = Account.objects.filter(owner=user, pk=data["to_account"]).first()
        if to_account is None:
            raise NotFound("Account not found.")
        kind, creditor_name, creditor_iban = Transfer.Kind.OWN, user.full_name, to_account.iban
    else:
        beneficiary = Beneficiary.objects.filter(owner=user, pk=data["beneficiary"]).first()
        if beneficiary is None:
            raise NotFound("Beneficiary not found.")
        if beneficiary.status != Beneficiary.Status.ACTIVE:
            raise TransferRejected("beneficiary_not_active", "Confirm this beneficiary with the OTP first.")
        to_account = Account.objects.filter(iban=beneficiary.iban).first()  # a Ledgerly customer?
        kind = Transfer.Kind.INTERNAL if to_account else Transfer.Kind.LOCAL
        creditor_name, creditor_iban = beneficiary.name, beneficiary.iban

    # Lock both accounts in id order (a fixed order prevents deadlocks), then re-read their balances.
    ids = sorted({from_account.pk, *([to_account.pk] if to_account else [])})
    locked = {a.pk: a for a in Account.objects.select_for_update().filter(pk__in=ids).order_by("pk")}
    from_account = locked[from_account.pk]
    to_account = locked.get(to_account.pk) if to_account else None

    if to_account and to_account.pk == from_account.pk:
        raise TransferRejected("same_account", "Choose two different accounts.")
    if from_account.status != Account.Status.ACTIVE:
        raise TransferRejected("account_frozen", "This account is frozen. Please contact the bank.")
    if to_account and to_account.status != Account.Status.ACTIVE:
        raise TransferRejected("destination_unavailable", "The destination account can't receive payments.")
    if from_account.balance < amount:
        raise TransferRejected("insufficient_funds", "Not enough money in this account.")
    if kind != Transfer.Kind.OWN:
        remaining = rules.daily_limit() - rules.sent_today(user, now)
        if amount > remaining:
            raise TransferRejected(
                "daily_limit_exceeded",
                f"This would exceed your daily limit. You can send AED {remaining} more today.",
            )
    if beneficiary and rules.in_cooling_off(beneficiary, now):
        remaining = rules.new_beneficiary_limit() - rules.sent_to_new_beneficiary(beneficiary)
        if amount > remaining:
            raise TransferRejected(
                "new_beneficiary_limit",
                f"New beneficiaries are limited to AED {rules.new_beneficiary_limit()} for 24 hours. "
                f"You can send AED {max(remaining, Decimal('0'))} more until then.",
            )

    reference = f"TRF{now:%y%m%d}{secrets.token_hex(4).upper()}"
    remarks = data.get("remarks", "")
    from_account.balance -= amount
    from_account.save(update_fields=["balance"])
    debit = Transaction.objects.create(
        account=from_account,
        direction=Transaction.Direction.DEBIT,
        category=Transaction.Category.TRANSFER_OUT,
        amount=amount,
        balance_after=from_account.balance,
        description=f"Transfer to {creditor_name}" + (f": {remarks}" if remarks else ""),
        counterparty=creditor_name,
        reference=f"{reference}D",
        created_at=now,
    )
    credit = None
    if to_account:
        to_account.balance += amount
        to_account.save(update_fields=["balance"])
        credit = Transaction.objects.create(
            account=to_account,
            direction=Transaction.Direction.CREDIT,
            category=Transaction.Category.TRANSFER_IN,
            amount=amount,
            balance_after=to_account.balance,
            description=f"Transfer from {user.full_name}" + (f": {remarks}" if remarks else ""),
            counterparty=user.full_name,
            reference=f"{reference}C",
            created_at=now,
        )
    return Transfer.objects.create(
        owner=user,
        reference=reference,
        kind=kind,
        status=Transfer.Status.PENDING if kind == Transfer.Kind.LOCAL else Transfer.Status.COMPLETED,
        from_account=from_account,
        to_account=to_account,
        beneficiary=beneficiary,
        creditor_name=creditor_name,
        creditor_iban=creditor_iban,
        amount=amount,
        remarks=remarks,
        idempotency_key=key,
        request_fingerprint=request_hash,
        debit=debit,
        credit=credit,
        created_at=now,
    )
