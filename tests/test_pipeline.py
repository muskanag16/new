"""Proves the safety gate catches the mistakes it exists to catch.

Run: python -m pytest -q
"""
import copy
import json
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "agent"))
import validate  # noqa: E402
from render import doc_title, html_to_text, render_doc_html  # noqa: E402

EXTRACTION = ROOT / "output" / "2026-10-26_riya-mehta" / "extraction.json"
DATA, TRANSCRIPT = validate.load(EXTRACTION)


def failures(data):
    return [n for n, ok, _ in validate.run_checks(data, TRANSCRIPT) if not ok]


def mutate(fn):
    d = copy.deepcopy(DATA)
    fn(d)
    return failures(d)


# --- the real extraction passes -------------------------------------------------------------

def test_reference_extraction_passes_all_checks():
    assert failures(DATA) == []


def test_doc_title_uses_call_date():
    assert doc_title(DATA) == "Client - Riya Mehta - 2026-10-26"


def test_whatsapp_under_300():
    assert len(DATA["whatsapp"]) < 300


# --- sensitive information ------------------------------------------------------------------

def test_no_sensitive_content_anywhere_in_outputs():
    texts = [html_to_text(render_doc_html(DATA)), DATA["email"]["body"], DATA["whatsapp"]]
    for t in texts:
        assert "98XXX" not in t and "12345" not in t
        assert "financial trouble" not in t.lower()
    for t in texts[1:]:  # client-facing
        assert "Green Basket" not in t and "lakh" not in t and "husband" not in t


def test_catches_phone_number_in_email():
    assert any("privacy" in f for f in mutate(lambda d: d["email"].update(body=d["email"]["body"] + "\nCall me on 98XXX 12345")))


def test_catches_unmasked_phone_number_in_doc():
    assert any("privacy" in f for f in mutate(lambda d: d["privacy_notes"].append("Urgent: 9812312345")))


def test_catches_speculation_in_doc():
    assert any("privacy" in f for f in mutate(lambda d: d["business_context"].append(
        {"text": "Green Basket may be in financial trouble", "status": "unconfirmed",
         "evidence": "Green Basket in Pune, is 60 days overdue"})))


def test_catches_reworded_speculation():
    assert any("privacy" in f for f in mutate(lambda d: d.update(executive_summary=d["executive_summary"] + " One buyer might be going under.")))


def test_catches_debtor_name_in_email():
    assert any("client-facing" in f for f in mutate(lambda d: d["email"].update(body=d["email"]["body"] + " Green Basket")))


def test_catches_budget_in_whatsapp():
    assert any("client-facing" in f for f in mutate(lambda d: d.update(whatsapp="Hi Riya, re the 25-30k budget...")))


def test_catches_missing_redaction_entry():
    assert any("cues" in f for f in mutate(lambda d: d["redactions"].pop()))


# --- invented facts -------------------------------------------------------------------------

def test_catches_fact_without_transcript_quote():
    assert any("grounding" in f for f in mutate(lambda d: d["goals"].append(
        {"text": "Expand to Bangalore", "status": "confirmed", "evidence": "we want to expand to Bangalore"})))


def test_catches_invented_number():
    assert any("numbers" in f for f in mutate(lambda d: d.update(executive_summary=d["executive_summary"] + " She has 12 retail partners.")))


def test_catches_invented_email_address():
    assert any("recipient" in f for f in mutate(lambda d: d["email"].update(to="riya@mehtaorganics.com")))


def test_catches_budget_marked_approved():
    assert any("budget" in f for f in mutate(lambda d: d["budget"].update(status="Approved")))


def test_catches_full_automation_promise():
    assert any("automatic customer" in f for f in mutate(lambda d: d["email"].update(
        body=d["email"]["body"] + " We'll make your customer replies fully automated.")))


def test_catches_whatsapp_too_long():
    assert any("whatsapp" in f for f in mutate(lambda d: d.update(whatsapp="x" * 300)))


def test_catches_missing_booking_placeholder():
    assert any("CAL.COM" in f for f in mutate(lambda d: d["email"].update(body=d["email"]["body"].replace("[CAL.COM BOOKING LINK]", ""))))


# --- draft-only behaviour -------------------------------------------------------------------

def test_code_never_calls_a_send_method():
    src = (ROOT / "agent" / "publish.py").read_text(encoding="utf-8")
    assert not re.search(r"\.send\s*\(", src), "publish.py must never call send()"
    assert "drafts().create" in src


def test_dry_run_writes_local_files_and_touches_nothing_remote():
    r = subprocess.run([sys.executable, str(ROOT / "agent" / "publish.py"), str(EXTRACTION), "--dry-run"],
                       capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stdout + r.stderr
    out = EXTRACTION.parent
    for f in ("summary.md", "client_doc.html", "email_draft.txt", "whatsapp.txt", "run_log.json"):
        assert (out / f).exists()
    steps = {s["step"]: s["status"] for s in json.loads((out / "run_log.json").read_text(encoding="utf-8"))["steps"]}
    assert steps["Google Drive + Gmail"] == "SKIPPED"


def test_publish_refuses_when_validation_fails(tmp_path):
    bad = copy.deepcopy(DATA)
    bad["whatsapp"] += " My number is 98XXX 12345"
    p = tmp_path / "extraction.json"
    p.write_text(json.dumps(bad), encoding="utf-8")
    r = subprocess.run([sys.executable, str(ROOT / "agent" / "publish.py"), str(p)],
                       capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 1 and "Stopped before touching Google" in r.stdout
