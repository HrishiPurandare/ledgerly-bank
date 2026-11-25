"""One-time passwords for adding a beneficiary (policy: "Adding a beneficiary requires OTP confirmation")."""

import hashlib
import hmac
import secrets

from django.conf import settings
from django.core.mail import send_mail


def new_code() -> str:
    return f"{secrets.randbelow(10**6):06d}"  # secrets, not random: an OTP must be unpredictable


def hash_code(beneficiary_id: int, code: str) -> str:
    """Stored instead of the code itself, so a database leak doesn't reveal live OTPs."""
    message = f"{beneficiary_id}:{code}".encode()
    return hmac.new(settings.SECRET_KEY.encode(), message, hashlib.sha256).hexdigest()


def matches(beneficiary_id: int, code: str, stored_hash: str) -> bool:
    return hmac.compare_digest(hash_code(beneficiary_id, code), stored_hash)  # constant time


def send(email: str, beneficiary_name: str, code: str) -> None:
    minutes = settings.NOVABANK["OTP_MINUTES"]
    send_mail(
        subject="NovaBank: confirm your new beneficiary",
        message=(
            f"Your code to add {beneficiary_name} is {code}. It expires in {minutes} minutes.\n"
            "NovaBank will never ask for this code by phone."
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[email],
    )
