"""Safety gate: checks extraction.json against the transcript before anything leaves this machine.

Usage: python agent/validate.py output/<call-id>/extraction.json
Exit code 0 = all checks passed, 1 = at least one failed.
"""
import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from render import html_to_text, render_doc_html, render_update_text  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
WHATSAPP_LIMIT = 300

# Phrases in a transcript that signal "keep this out of writing". Each one found must be
# matched by an entry in extraction["redactions"].
SENSITIVE_CUES = [
    r"don'?t put (that|this|it) in writing",
    r"don'?t (share|tell|mention)",
    r"off the record",
    r"between (us|you and me)",
    r"keep (this|that|it) (private|confidential|to yourself)",
    r"\bconfidential\b",
]

# Never allowed anywhere in generated output, whatever the model decided.
ALWAYS_FORBIDDEN = [
    r"financial (trouble|difficult|distress|problems?)",
    r"\binsolven", r"\bbankrupt", r"going under", r"can'?t pay",
]
PHONE_PATTERNS = [
    r"\b\d{2}[X\d]{3}[\s-]?\d{5}\b",        # Indian mobile, incl. masked forms like 98XXX 12345
    r"(?:\d[\s-]?){10,}",                    # any run of 10+ digits (dates have only 8)
]

# Not allowed in client-facing text (email + WhatsApp).
CLIENT_FACING_FORBIDDEN = [
    r"green basket", r"\blakh\b", r"\b1\.8\b", r"husband", r"\bpune\b",
    r"₹", r"\b25\b", r"\b30\b", r"thousand", r"overdue",
    r"\bapproved budget\b", r"budget (is|has been) (approved|confirmed)",
]

REQUIRED_KEYS = ["meta", "client", "executive_summary", "goals", "pain_points", "business_context",
                 "budget", "objections", "next_steps", "derived_dates", "pending_confirmations",
                 "privacy_notes", "redactions", "email", "whatsapp"]
STATUSES = {"confirmed", "preference", "tentative", "unconfirmed"}


def norm(s):
    s = s.lower().replace("’", "'").replace("–", "-").replace("—", "-")
    return re.sub(r"\s+", " ", s).strip()


def outputs(data):
    """Every piece of text that will be written to Drive or Gmail or shown as WhatsApp."""
    heading, body = render_update_text(data)
    return {
        "doc": html_to_text(render_doc_html(data)) + " " + heading + " " + body,
        "email": data["email"]["subject"] + " " + data["email"]["body"] + " " + data["email"]["to"],
        "whatsapp": data["whatsapp"],
    }


def run_checks(data, transcript):
    t = norm(transcript)
    out = outputs(data)
    results = []

    def check(name, ok, detail=""):
        results.append((name, bool(ok), detail))

    missing = [k for k in REQUIRED_KEYS if k not in data]
    check("schema: all sections present", not missing, f"missing: {missing}" if missing else "")
    if missing:
        return results

    # 1. Grounding: every fact carries a verbatim quote from the transcript.
    labelled = data["goals"] + data["pain_points"] + data["business_context"] + data["objections"]
    ungrounded = []
    for it in labelled + data["next_steps"] + [data["budget"]]:
        ev = it.get("evidence", "")
        if not ev or norm(ev) not in t:
            ungrounded.append(it.get("text") or it.get("action") or it.get("range"))
    bad_status = [it["text"] for it in labelled if it.get("status") not in STATUSES]
    check("grounding: every fact has a verbatim transcript quote", not ungrounded, f"{ungrounded}")
    check("labels: every item has a valid status", not bad_status, f"{bad_status}")

    # 2. Numbers in outputs must come from the transcript or a declared derived date.
    allowed = set(re.findall(r"\d+(?:\.\d+)?", transcript))
    for d in data["derived_dates"]:
        allowed |= set(re.findall(r"\d+(?:\.\d+)?", d["value"]))
    allowed |= set(re.findall(r"\d+", data["meta"]["call_date"]))  # ISO date in the doc title
    allowed |= {str(i) for i in range(1, 10)}  # doc section numbers
    stray = set()
    for name, text in out.items():
        stray |= set(re.findall(r"\d+(?:\.\d+)?", text)) - allowed
    check("no invented numbers (all figures appear in transcript)", not stray, f"unexpected: {sorted(stray)}")

    # 3. Every sensitive cue in the transcript is acknowledged by a redaction entry.
    cues = [m.group(0) for p in SENSITIVE_CUES for m in re.finditer(p, t)]
    covered = [norm(r["cue_quote"]) for r in data["redactions"]]
    uncovered = [c for c in cues if not any(c in cq or cq in c for cq in covered)]
    check(f"privacy: all {len(cues)} sensitive cues in transcript handled", not uncovered, f"unhandled: {uncovered}")
    bad_quotes = [r["cue_quote"] for r in data["redactions"] if norm(r["cue_quote"]) not in t]
    check("privacy: redaction cue quotes are verbatim", not bad_quotes, f"{bad_quotes}")

    # 4. Nothing redacted leaks into any output.
    leaks = []
    for name, text in out.items():
        low = norm(text)
        for r in data["redactions"]:
            leaks += [f"{name}: '{w}'" for w in r["must_not_appear"] if norm(w) in low]
        leaks += [f"{name}: /{p}/" for p in ALWAYS_FORBIDDEN if re.search(p, low)]
        leaks += [f"{name}: phone number" for p in PHONE_PATTERNS if re.search(p, text)]
    check("privacy: no redacted content, speculation or phone numbers in doc/email/WhatsApp", not leaks, f"{leaks}")

    # 5. Client-facing text stays clean.
    cf = []
    for name in ("email", "whatsapp"):
        low = out[name].lower()
        cf += [f"{name}: /{p}/" for p in CLIENT_FACING_FORBIDDEN if re.search(p, low)]
    check("client-facing: no debtor names, amounts, budget or family details", not cf, f"{cf}")

    # 6. Budget never shown as approved.
    b = data["budget"]
    check("budget: marked tentative, not approved", "tentative" in b["status"].lower() and "approved" not in b["status"].lower().replace("not approved", ""), b["status"])

    # 7. Email rules.
    e = data["email"]
    to_ok = (e["to"] == "" and "[CONFIRM CLIENT EMAIL ADDRESS]" in e["body"]) or (e["to"] and norm(e["to"]) in t)
    check("email: recipient blank + flagged, or taken from transcript", to_ok, repr(e["to"]))
    check("email: no invented addresses in body", not re.search(r"[\w.+-]+@[\w-]+\.[\w.]+", e["body"]))
    check("email: contains [CAL.COM BOOKING LINK]", "[CAL.COM BOOKING LINK]" in e["body"])
    check("email: starts with consultant review block", e["body"].lstrip().startswith("[REVIEW BEFORE SENDING"))
    check("email: does not promise fully automatic customer messaging",
          not re.search(r"fully automat|completely automat|without (you|your) (needing|having) to (check|review)", e["body"].lower()))

    # 8. WhatsApp.
    n = len(data["whatsapp"])
    check(f"whatsapp: under {WHATSAPP_LIMIT} characters", n < WHATSAPP_LIMIT, f"{n} chars")
    check("whatsapp: no [CONFIRM] tags left in", "[CONFIRM" not in data["whatsapp"])

    # 9. Missing info is flagged rather than guessed.
    check("pending confirmations listed", len(data["pending_confirmations"]) > 0)
    return results


def load(extraction_path):
    data = json.loads(pathlib.Path(extraction_path).read_text(encoding="utf-8"))
    transcript = (ROOT / data["meta"]["transcript_file"]).read_text(encoding="utf-8")
    return data, transcript


def main(argv):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # Windows consoles choke on ₹
    if len(argv) != 2:
        print(__doc__)
        return 2
    data, transcript = load(argv[1])
    results = run_checks(data, transcript)
    for name, ok, detail in results:
        print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"  -> {detail}" if not ok and detail else ""))
    failed = sum(not ok for _, ok, _ in results)
    print(f"\n{len(results) - failed}/{len(results)} checks passed.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
