"""ISO 20022 pacs.008.001.08: the message a bank sends to move a customer's money to another bank.

NovaBank builds one for every LOCAL transfer (to another UAE bank). The XML is a pure function of the
transfer, so the same transfer always gives byte-identical XML (and golden-file tests can compare it).
"""

from datetime import date, datetime, time, timedelta
from functools import cache
from pathlib import Path
from zoneinfo import ZoneInfo

from lxml import etree

from payments.models import Transfer

NAMESPACE = "urn:iso:std:iso:20022:tech:xsd:pacs.008.001.08"
SCHEMA_PATH = Path(__file__).resolve().parent / "schemas" / "pacs.008.001.08.subset.xsd"
NOVABANK_BIC = "NOVAAEADXXX"  # fictional BIC for the fictional bank
DUBAI = ZoneInfo("Asia/Dubai")
CUT_OFF = time(14, 0)  # policy: "made before 2:00 PM on a business day are credited the same day"
WEEKEND = {5, 6}  # Saturday and Sunday, the UAE weekend since 2022


def settlement_date(created_at: datetime) -> date:
    """Same business day before 14:00 Dubai time; otherwise the next business day.

    Public holidays aren't modelled (a real bank would read them from a holiday calendar).
    """
    local = created_at.astimezone(DUBAI)
    day = local.date()
    if day.weekday() not in WEEKEND and local.time() < CUT_OFF:
        return day
    day += timedelta(days=1)
    while day.weekday() in WEEKEND:
        day += timedelta(days=1)
    return day


def _sub(parent, tag: str, text: str | None = None, **attrs):
    element = etree.SubElement(parent, f"{{{NAMESPACE}}}{tag}", **attrs)
    if text is not None:
        element.text = text  # lxml escapes &, < and > for us: names can't break or inject into the XML
    return element


def _iban_account(parent, tag: str, iban: str) -> None:
    _sub(_sub(_sub(parent, tag), "Id"), "IBAN", iban)


def build_pacs008(transfer: Transfer) -> bytes:
    if transfer.kind != Transfer.Kind.LOCAL:
        raise ValueError("Only transfers to other banks travel as pacs.008 messages.")
    document = etree.Element(f"{{{NAMESPACE}}}Document", nsmap={None: NAMESPACE})
    message = _sub(document, "FIToFICstmrCdtTrf")

    header = _sub(message, "GrpHdr")
    _sub(header, "MsgId", f"MSG-{transfer.reference}")
    _sub(header, "CreDtTm", transfer.created_at.astimezone(DUBAI).isoformat(timespec="seconds"))
    _sub(header, "NbOfTxs", "1")
    _sub(_sub(header, "SttlmInf"), "SttlmMtd", "CLRG")  # settled through the local clearing system

    tx = _sub(message, "CdtTrfTxInf")
    payment_id = _sub(tx, "PmtId")
    _sub(payment_id, "InstrId", transfer.reference)
    _sub(payment_id, "EndToEndId", transfer.reference)
    _sub(payment_id, "UETR", str(transfer.uetr))
    _sub(tx, "IntrBkSttlmAmt", f"{transfer.amount:.2f}", Ccy=transfer.currency)
    _sub(tx, "IntrBkSttlmDt", settlement_date(transfer.created_at).isoformat())
    _sub(tx, "ChrgBr", "SLEV")  # charges follow the clearing system's service level
    _sub(_sub(tx, "Dbtr"), "Nm", transfer.owner.full_name)
    _iban_account(tx, "DbtrAcct", transfer.from_account.iban)
    _sub(_sub(_sub(tx, "DbtrAgt"), "FinInstnId"), "BICFI", NOVABANK_BIC)
    # The creditor's bank is identified by the 3-digit UAE bank code inside its IBAN (characters 5-7).
    creditor_agent = _sub(_sub(tx, "CdtrAgt"), "FinInstnId")
    _sub(_sub(creditor_agent, "Othr"), "Id", f"AE-BANK-{transfer.creditor_iban[4:7]}")
    _sub(_sub(tx, "Cdtr"), "Nm", transfer.creditor_name)
    _iban_account(tx, "CdtrAcct", transfer.creditor_iban)
    if transfer.remarks:
        _sub(_sub(tx, "RmtInf"), "Ustrd", transfer.remarks)

    return etree.tostring(document, xml_declaration=True, encoding="UTF-8", pretty_print=True)


@cache
def _schema() -> etree.XMLSchema:
    return etree.XMLSchema(etree.parse(str(SCHEMA_PATH), _safe_parser()))


def _safe_parser() -> etree.XMLParser:
    """Never resolve entities or fetch from the network when parsing XML (XXE protection)."""
    return etree.XMLParser(resolve_entities=False, no_network=True, load_dtd=False)


def validate(xml: bytes) -> list[str]:
    """Schema errors as readable strings; an empty list means valid. Never raises on bad input."""
    try:
        document = etree.fromstring(xml, _safe_parser())
    except etree.XMLSyntaxError as exc:
        return [f"not well-formed XML: {exc}"]
    # Payment messages never need a DOCTYPE; refusing one blocks entity tricks (XXE, billion laughs).
    if document.getroottree().docinfo.doctype:
        return ["DOCTYPE is not allowed in payment messages"]
    schema = _schema()
    try:
        if schema.validate(document):
            return []
    except etree.XMLSchemaValidateError as exc:
        return [f"schema validation failed: {exc}"]
    return [f"line {e.line}: {e.message}" for e in schema.error_log]
