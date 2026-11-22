"""ISO 20022 pacs.008: schema-valid, correct content, correct settlement date, safe XML, stable output."""

import uuid
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from lxml import etree

from banking.models import Transaction
from payments.iso20022 import NAMESPACE, build_pacs008, settlement_date, validate
from payments.models import Beneficiary, Transfer

DUBAI = ZoneInfo("Asia/Dubai")
GOLDEN = Path(__file__).parent / "golden" / "pacs008_local.xml"
NS = {"p": NAMESPACE}
CREDITOR_IBAN = "AE070331234567890123456"


@pytest.fixture
def make_transfer(user, make_account):
    account = make_account(user, balance="0.00")
    beneficiary = Beneficiary.objects.create(
        owner=user, name="Fatima Noor", iban=CREDITOR_IBAN, status="ACTIVE"
    )
    counter = iter(range(1, 1000))

    def make(
        kind="LOCAL", amount="1250.75", remarks="Invoice 2026-114", name="Fatima Noor", when=None, uetr=None
    ):
        n = next(counter)
        when = when or datetime(2026, 11, 23, 10, 15, 0, tzinfo=DUBAI)  # a Monday morning
        debit = Transaction.objects.create(
            account=account,
            direction="DEBIT",
            category="TRANSFER_OUT",
            amount=Decimal(amount),
            balance_after=Decimal("0"),
            description="Transfer",
            reference=f"TRF-TEST-{n}D",
            created_at=when,
        )
        return Transfer.objects.create(
            owner=user,
            reference=f"TRF261123TEST{n:04d}",
            uetr=uetr or uuid.uuid4(),
            kind=kind,
            status="PENDING",
            from_account=account,
            beneficiary=beneficiary,
            creditor_name=name,
            creditor_iban=CREDITOR_IBAN,
            amount=Decimal(amount),
            remarks=remarks,
            idempotency_key=f"k{n}",
            request_fingerprint="x",
            debit=debit,
            created_at=when,
        )

    return make


def text(xml: bytes, path: str) -> str:
    return etree.fromstring(xml).findtext(path, namespaces=NS)


def test_the_message_is_valid_against_the_schema(make_transfer):
    assert validate(build_pacs008(make_transfer())) == []


def test_the_message_carries_the_right_payment(make_transfer, user):
    transfer = make_transfer()
    xml = build_pacs008(transfer)
    tx = "p:FIToFICstmrCdtTrf/p:CdtTrfTxInf"
    amount = etree.fromstring(xml).find(f"{tx}/p:IntrBkSttlmAmt", NS)
    assert (amount.text, amount.get("Ccy")) == ("1250.75", "AED")
    assert text(xml, f"{tx}/p:PmtId/p:EndToEndId") == transfer.reference
    assert text(xml, f"{tx}/p:PmtId/p:UETR") == str(transfer.uetr)
    assert text(xml, f"{tx}/p:Dbtr/p:Nm") == user.full_name
    assert text(xml, f"{tx}/p:DbtrAcct/p:Id/p:IBAN") == transfer.from_account.iban
    assert text(xml, f"{tx}/p:Cdtr/p:Nm") == "Fatima Noor"
    assert text(xml, f"{tx}/p:CdtrAcct/p:Id/p:IBAN") == CREDITOR_IBAN
    assert text(xml, f"{tx}/p:CdtrAgt/p:FinInstnId/p:Othr/p:Id") == "AE-BANK-033"  # bank code from the IBAN
    assert text(xml, "p:FIToFICstmrCdtTrf/p:GrpHdr/p:NbOfTxs") == "1"


def test_whole_dirhams_keep_two_decimals(make_transfer):
    xml = build_pacs008(make_transfer(amount="500"))
    assert text(xml, "p:FIToFICstmrCdtTrf/p:CdtTrfTxInf/p:IntrBkSttlmAmt") == "500.00"


def test_remittance_info_is_left_out_when_there_are_no_remarks(make_transfer):
    xml = build_pacs008(make_transfer(remarks=""))
    assert b"RmtInf" not in xml and validate(xml) == []  # an empty <Ustrd/> would break Max140Text


def test_special_characters_in_names_are_escaped_not_injected(make_transfer):
    nasty = 'Tom & Jerry <Trading> "LLC"</Nm><Nm>Evil'
    xml = build_pacs008(make_transfer(name=nasty))
    assert validate(xml) == []
    assert text(xml, "p:FIToFICstmrCdtTrf/p:CdtTrfTxInf/p:Cdtr/p:Nm") == nasty  # round-trips intact


def test_only_transfers_to_other_banks_get_a_message(make_transfer):
    with pytest.raises(ValueError):
        build_pacs008(make_transfer(kind="INTERNAL"))


# ---------- settlement date: before 14:00 on a business day = same day (UAE weekend: Sat-Sun) ----------


@pytest.mark.parametrize(
    ("created", "expected"),
    [
        ("2026-11-23 13:59", "2026-11-23"),  # Monday before the cut-off
        ("2026-11-23 14:00", "2026-11-24"),  # exactly 14:00 is too late
        ("2026-11-27 15:30", "2026-11-30"),  # Friday afternoon -> Monday
        ("2026-11-28 09:00", "2026-11-30"),  # Saturday -> Monday
        ("2026-11-29 09:00", "2026-11-30"),  # Sunday -> Monday
        ("2026-11-27 09:00", "2026-11-27"),  # Friday is a working day in the UAE
    ],
)
def test_settlement_date_follows_the_2pm_cut_off(created, expected):
    when = datetime.strptime(created, "%Y-%m-%d %H:%M").replace(tzinfo=DUBAI)
    assert settlement_date(when).isoformat() == expected


def test_the_cut_off_is_dubai_time_not_utc():
    # 10:30 UTC is 14:30 in Dubai: already past the cut-off.
    when = datetime(2026, 11, 23, 10, 30, tzinfo=ZoneInfo("UTC"))
    assert settlement_date(when).isoformat() == "2026-11-24"


# ---------- the validator itself must catch bad messages (test the test) ----------


@pytest.mark.parametrize(
    ("find", "replace"),
    [
        ("<ChrgBr>SLEV</ChrgBr>", "<ChrgBr>FREE</ChrgBr>"),  # not in the code list
        ('Ccy="AED"', 'Ccy="aed"'),  # currency must be 3 capitals
        ("<IBAN>AE07", "<IBAN>ae07"),  # IBAN country in capitals
        ("<NbOfTxs>1</NbOfTxs>", "<NbOfTxs>one</NbOfTxs>"),
        ("-41d3-", "-11d3-"),  # UETR must be a version-4 UUID (the 4 starts the third group)
    ],
    ids=["charge-bearer", "currency", "iban", "count", "uetr-version"],
)
def test_the_schema_rejects_broken_messages(make_transfer, find, replace):
    xml = build_pacs008(make_transfer(uetr=uuid.UUID("3f2504e0-4f89-41d3-9a0c-0305e82c3301")))
    broken = xml.decode().replace(find, replace, 1).encode()
    assert broken != xml and validate(broken)


def test_parsing_ignores_external_entities():
    """XXE: a message that tries to read a local file must not get its contents."""
    evil = (
        b'<?xml version="1.0"?><!DOCTYPE d [<!ENTITY x SYSTEM "file:///etc/passwd">]>'
        b'<Document xmlns="urn:iso:std:iso:20022:tech:xsd:pacs.008.001.08">&x;</Document>'
    )
    errors = validate(evil)
    assert errors == ["DOCTYPE is not allowed in payment messages"]


# ---------- golden file: the exact bytes for a fixed transfer ----------


def test_output_matches_the_reviewed_golden_file(make_transfer):
    transfer = make_transfer(uetr=uuid.UUID("3f2504e0-4f89-41d3-9a0c-0305e82c3301"))
    transfer.reference = "TRF261123GOLDEN01"
    xml = build_pacs008(transfer)
    if not GOLDEN.exists():  # first run writes it; a human reviews and commits it
        GOLDEN.write_bytes(xml)
    assert xml == GOLDEN.read_bytes(), "pacs.008 output changed: review the diff, then update the golden file"


# ---------- the endpoint ----------


def test_the_endpoint_returns_xml_for_the_owner(auth_api, make_transfer):
    transfer = make_transfer()
    response = auth_api.get(f"/api/transfers/{transfer.id}/pacs008/")
    assert response.status_code == 200
    assert response["Content-Type"].startswith("application/xml")
    assert validate(response.content) == []


def test_an_instant_transfer_has_no_message(auth_api, make_transfer):
    transfer = make_transfer(kind="INTERNAL")
    response = auth_api.get(f"/api/transfers/{transfer.id}/pacs008/")
    assert response.status_code == 409 and response.json()["code"] == "not_a_network_payment"


def test_someone_elses_message_is_404(api, make_transfer, make_user):
    transfer = make_transfer()
    make_user(email="other@example.com")
    token = api.post(
        "/api/auth/login/", {"email": "other@example.com", "password": "Corr3ct-Horse-Battery"}, format="json"
    ).json()["access"]
    api.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    assert api.get(f"/api/transfers/{transfer.id}/pacs008/").status_code == 404
