"""Smoke test for the running Docker stack: the whole bank, through nginx, like a customer would use it.

    python3 e2e/smoke.py                      # against http://localhost:8080 and Mailpit on :8025
    BASE_URL=... MAILPIT_URL=... python3 e2e/smoke.py

Standard library only, so it runs on any machine or CI runner without installing anything.
Safe to run repeatedly: every run adds its own uniquely named beneficiary and moves AED 1.00.
Exit code 0 = every check passed, 1 = at least one failed.
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass, field
from decimal import Decimal
from xml.etree import ElementTree

BASE = os.getenv("BASE_URL", "http://localhost:8080").rstrip("/")
MAILPIT = os.getenv("MAILPIT_URL", "http://localhost:8025").rstrip("/")
PASSWORD = "NovaBank-Demo-2026"  # noqa: S105 - published password of the fictional demo customers
PACS008 = "{urn:iso:std:iso:20022:tech:xsd:pacs.008.001.08}"

for _url in (BASE, MAILPIT):  # urllib also opens file:// URLs; only ever talk HTTP(S)
    if not _url.startswith(("http://", "https://")):
        raise SystemExit(f"Only http(s) URLs are allowed: {_url}")


@dataclass
class Response:
    status: int
    headers: dict[str, str]
    body: bytes

    def json(self):
        return json.loads(self.body)

    @property
    def text(self) -> str:
        return self.body.decode("utf-8", "replace")


def request(method: str, url: str, *, token: str = "", body=None, headers=None) -> Response:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)  # noqa: S310 - schemes checked above
    if data is not None:
        req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    for name, value in (headers or {}).items():
        req.add_header(name, value)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:  # noqa: S310 - schemes checked above
            return Response(resp.status, {k.lower(): v for k, v in resp.headers.items()}, resp.read())
    except urllib.error.HTTPError as err:  # 4xx/5xx still have a body worth reading
        return Response(err.code, {k.lower(): v for k, v in err.headers.items()}, err.read())


@dataclass
class Report:
    results: list[tuple[bool, str, str]] = field(default_factory=list)

    def check(self, ok: bool, name: str, detail: str = "") -> bool:
        self.results.append((ok, name, detail))
        print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"  ({detail})" if detail and not ok else ""))
        return ok


def uae_iban(bank_code: str, account_number: str) -> str:
    """A valid UAE IBAN: ISO 13616 mod-97 check digits (A=10, E=14)."""
    bban = bank_code + account_number
    check = 98 - int(bban + "101400") % 97
    return f"AE{check:02d}{bban}"


def login(email: str) -> str:
    response = request("POST", f"{BASE}/api/auth/login/", body={"email": email, "password": PASSWORD})
    if response.status != 200:
        raise SystemExit(f"Cannot log in as {email}: HTTP {response.status} {response.text[:200]}")
    return response.json()["access"]


def otp_from_mailpit(to: str, beneficiary_name: str, timeout_s: float = 10) -> str | None:
    """Poll Mailpit's API for the code email (sending is synchronous, but don't depend on that)."""
    deadline = time.monotonic() + timeout_s
    pattern = re.compile(rf"Your code to add {re.escape(beneficiary_name)} is (\d{{6}})")
    while time.monotonic() < deadline:
        search = request("GET", f"{MAILPIT}/api/v1/search?query=to:{to}").json()
        for message in search.get("messages", []):
            full = request("GET", f"{MAILPIT}/api/v1/message/{message['ID']}").json()
            match = pattern.search(full.get("Text", ""))
            if match:
                return match.group(1)
        time.sleep(0.5)
    return None


def main() -> int:
    report = Report()
    check = report.check
    run_id = str(int(time.time() * 1000))[-12:]

    print(f"Smoke test against {BASE} (mail: {MAILPIT})\n\nThe web server")
    home = request("GET", f"{BASE}/")
    check(home.status == 200 and "text/html" in home.headers.get("content-type", ""), "serves the app")
    csp = home.headers.get("content-security-policy", "")
    check("script-src 'self'" in csp and "frame-ancestors 'none'" in csp, "sends a strict CSP", csp)
    for header, value in [
        ("x-content-type-options", "nosniff"),
        ("x-frame-options", "DENY"),
        ("referrer-policy", "same-origin"),
    ]:
        check(
            home.headers.get(header) == value, f"sends {header}: {value}", home.headers.get(header, "missing")
        )
    # The CSP blocks inline scripts and handlers, so the page must not contain any (day 17's styles bug).
    inline = re.findall(r"<script(?![^>]*\bsrc=)[^>]*>|\son[a-z]+\s*=", home.text, re.IGNORECASE)
    check(not inline, "page has no inline scripts or event handlers", ", ".join(inline))
    check(
        home.headers.get("server", "") == "nginx",
        "doesn't reveal the nginx version",
        home.headers.get("server", ""),
    )
    deep = request("GET", f"{BASE}/accounts/1?direction=DEBIT")
    check(deep.status == 200 and "<lb-root" in deep.text, "deep links load the app (no 404 on refresh)")
    asset = re.search(r'src="(main-[A-Z0-9]+\.js)"', home.text)
    if check(bool(asset), "app bundle has a hashed name"):
        cache = request("GET", f"{BASE}/{asset.group(1)}").headers.get("cache-control", "")
        check("immutable" in cache, "hashed files are cached for a long time", cache)
    check("no-cache" in home.headers.get("cache-control", ""), "index.html is always revalidated")

    print("\nThe API, through nginx")
    health = request("GET", f"{BASE}/api/health/")
    check(
        health.status == 200 and health.json() == {"status": "ok", "database": "ok"},
        "health: API and Postgres up",
    )
    check(request("GET", f"{BASE}/api/accounts/").status == 401, "data needs a login")
    wrong = request(
        "POST", f"{BASE}/api/auth/login/", body={"email": "sara@example.com", "password": "wrong"}
    )
    check(wrong.status == 401, "a wrong password is refused")
    check(request("GET", f"{BASE}/static/admin/css/base.css").status == 200, "Django static files are served")

    sara, omar = login("sara@example.com"), login("omar@example.com")
    accounts = request("GET", f"{BASE}/api/accounts/", token=sara).json()["results"]
    check(len(accounts) == 2, "Sara sees her 2 accounts", str(len(accounts)))
    omar_account = request("GET", f"{BASE}/api/accounts/", token=omar).json()["results"][0]["id"]
    check(
        request("GET", f"{BASE}/api/accounts/{omar_account}/", token=sara).status == 404,
        "Sara can't open Omar's account (404, not 403)",
    )

    print("\nAdd a beneficiary with the emailed code (SMTP -> Mailpit)")
    name = f"Smoke Test {run_id}"
    iban = uae_iban("033", run_id.rjust(16, "0"))  # bank 033: another bank, so a pacs.008 is made
    created = request("POST", f"{BASE}/api/beneficiaries/", token=sara, body={"name": name, "iban": iban})
    if not check(
        created.status == 201 and created.json()["status"] == "PENDING",
        "beneficiary created, pending",
        created.text[:200],
    ):
        return finish(report)
    beneficiary = created.json()["id"]
    code = otp_from_mailpit("sara@example.com", name)
    if not check(code is not None, "the code email arrived in Mailpit"):
        return finish(report)
    wrong_code = "000000" if code != "000000" else "111111"
    bad = request(
        "POST", f"{BASE}/api/beneficiaries/{beneficiary}/confirm/", token=sara, body={"otp": wrong_code}
    )
    check(bad.status == 400 and bad.json().get("code") == "otp_invalid", "a wrong code is refused")
    ok = request("POST", f"{BASE}/api/beneficiaries/{beneficiary}/confirm/", token=sara, body={"otp": code})
    check(ok.status == 200 and ok.json()["status"] == "ACTIVE", "the right code confirms it")

    print("\nSend money: limits, idempotency, ISO 20022")
    # The richest active account, and say so if even that can't cover the test: with too little money
    # the bank answers insufficient_funds first, and the limit check below would fail for the wrong reason.
    source = max((a for a in accounts if a["status"] == "ACTIVE"), key=lambda a: Decimal(a["balance"]))
    if not check(
        Decimal(source["balance"]) > Decimal("10000.01"),
        "precondition: an account with more than AED 10,000.01",
        f"richest has {source['balance']}; reseed the demo data",
    ):
        return finish(report)
    too_much = request(
        "POST", f"{BASE}/api/transfers/", token=sara, headers={"Idempotency-Key": str(uuid.uuid4())},
        body={"from_account": source["id"], "beneficiary": beneficiary, "amount": "10000.01"},
    )  # fmt: skip
    check(
        too_much.json().get("code") == "new_beneficiary_limit",
        "AED 10,000.01 to a new beneficiary is refused",
    )

    key = str(uuid.uuid4())
    body = {"from_account": source["id"], "beneficiary": beneficiary, "amount": "1.00", "remarks": "smoke"}
    first = request("POST", f"{BASE}/api/transfers/", token=sara, body=body, headers={"Idempotency-Key": key})
    if not check(first.status == 201, "AED 1.00 sent", first.text[:200]):
        return finish(report)
    transfer = first.json()
    again = request("POST", f"{BASE}/api/transfers/", token=sara, body=body, headers={"Idempotency-Key": key})
    check(
        again.status == 201
        and again.headers.get("idempotent-replayed") == "true"
        and again.json()["id"] == transfer["id"],
        "the same Idempotency-Key replays it instead of paying twice",
    )
    after = request("GET", f"{BASE}/api/accounts/{source['id']}/", token=sara).json()
    expected = str(Decimal(source["balance"]) - Decimal("1.00"))  # money is never a float, here either
    check(
        after["balance"] == expected,
        "the balance went down by exactly AED 1.00 (once)",
        f"{after['balance']} != {expected}",
    )
    statement = request(
        "GET", f"{BASE}/api/accounts/{source['id']}/transactions/?search={run_id}", token=sara
    )
    rows = statement.json()["results"] if statement.status == 200 else []
    check(
        len(rows) == 1 and rows[0]["direction"] == "DEBIT" and rows[0]["amount"] == "1.00",
        "the statement shows exactly one AED 1.00 debit for it",
        f"{len(rows)} rows",
    )

    xml = request("GET", f"{BASE}/api/transfers/{transfer['id']}/pacs008/", token=sara)
    check(xml.status == 200 and "xml" in xml.headers.get("content-type", ""), "pacs.008 XML is returned")
    try:
        # Our own API's response; Python's expat doesn't resolve external entities (no XXE).
        root = ElementTree.fromstring(xml.body)  # noqa: S314
        uetr = root.findtext(f".//{PACS008}UETR")
        amount = root.find(f".//{PACS008}IntrBkSttlmAmt")
        check(uetr == transfer["uetr"], "its UETR matches the transfer", f"{uetr} != {transfer['uetr']}")
        check(
            amount is not None and amount.text == "1.00" and amount.get("Ccy") == "AED",
            "its settlement amount is AED 1.00",
        )
    except ElementTree.ParseError as err:
        check(False, "pacs.008 is well-formed XML", str(err))

    return finish(report)


def finish(report: Report) -> int:
    failed = [name for ok, name, _ in report.results if not ok]
    print(f"\n{len(report.results) - len(failed)} passed, {len(failed)} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
