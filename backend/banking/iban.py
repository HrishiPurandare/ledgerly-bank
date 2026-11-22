"""UAE IBANs: "AE" + 2 check digits + 3-digit bank code + 16-digit account number = 23 characters.

The check digits use the ISO 13616 mod-97 rule, the same one every real bank uses to catch typos.
"""

import re

LEDGERLY_BANK_CODE = "999"  # fictional: no real UAE bank uses it
UAE_IBAN = re.compile(r"^AE\d{21}$")


def _to_digits(text: str) -> int:
    """Letters become numbers (A=10 ... Z=35), as the IBAN standard requires."""
    return int("".join(str(int(ch, 36)) for ch in text))


def check_digits(country: str, bban: str) -> str:
    return f"{98 - _to_digits(bban + country + '00') % 97:02d}"


def make_uae_iban(account_number: str, bank_code: str = LEDGERLY_BANK_CODE) -> str:
    if not (account_number.isdigit() and len(account_number) == 16):
        raise ValueError("account number must be 16 digits")
    bban = bank_code + account_number
    return f"AE{check_digits('AE', bban)}{bban}"


def normalise(iban: str) -> str:
    return re.sub(r"\s+", "", iban).upper()


def is_valid_uae_iban(iban: str) -> bool:
    iban = normalise(iban)
    if not UAE_IBAN.match(iban):
        return False
    rearranged = iban[4:] + iban[:4]
    return _to_digits(rearranged) % 97 == 1


def format_iban(iban: str) -> str:
    """Groups of four for display: AE07 9991 2345 ..."""
    iban = normalise(iban)
    return " ".join(iban[i : i + 4] for i in range(0, len(iban), 4))
