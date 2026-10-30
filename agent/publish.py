"""Publish a validated extraction: Google Doc in Drive + Gmail DRAFT. Never sends anything.

Usage:
  python agent/publish.py output/<call-id>/extraction.json            # real run
  python agent/publish.py output/<call-id>/extraction.json --dry-run  # local files only

Safe to re-run: a transcript already processed is skipped in Drive, and its draft is not duplicated.
The only Gmail calls in this file are drafts.create and drafts.get.
"""
import argparse
import base64
import datetime
import hashlib
import json
import pathlib
import sys
from email.message import EmailMessage

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import validate  # noqa: E402
from render import (doc_title, render_doc_html, render_email_text, render_summary_md,  # noqa: E402
                    render_update_text)

ROOT = pathlib.Path(__file__).resolve().parent.parent
CREDENTIALS = ROOT / "credentials.json"
TOKEN = ROOT / "token.json"
STATE = ROOT / "output" / "state.json"
FOLDER_NAME = "Clients"
# drive.file = this app can only see files it created (least privilege).
# gmail.compose = create drafts. Google has no narrower "drafts only" scope, so this code
# simply never calls a send method (enforced by tests/test_pipeline.py).
SCOPES = ["https://www.googleapis.com/auth/drive.file",
          "https://www.googleapis.com/auth/gmail.compose"]


class StepError(Exception):
    pass


class RunLog:
    def __init__(self, path):
        self.path, self.steps = path, []

    def add(self, step, status, detail=""):
        self.steps.append({"step": step, "status": status, "detail": detail})
        print(f"  [{status:^7}] {step}" + (f" - {detail}" if detail else ""))

    def save(self):
        self.path.write_text(json.dumps({"run_at": datetime.datetime.now().isoformat(timespec="seconds"),
                                         "steps": self.steps}, indent=2), encoding="utf-8")


def explain(err):
    """Turn Google API errors into something the consultant can act on."""
    from googleapiclient.errors import HttpError
    if isinstance(err, HttpError):
        code, text = err.resp.status, str(err)
        if "accessNotConfigured" in text or "has not been used" in text:
            return f"{code}: the Google API is not enabled in your Cloud project - see SETUP_GOOGLE.md step 2"
        if code in (401, 403):
            return f"{code}: permission denied - delete token.json and run again to sign in"
        if code == 404:
            return f"{code}: not found (it may have been deleted)"
        if code >= 500 or code == 429:
            return f"{code}: Google is busy - wait a minute and run again"
        return f"{code}: {err.reason}"
    return f"{type(err).__name__}: {err}"


def get_credentials():
    from google.auth.exceptions import RefreshError
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow

    creds = Credentials.from_authorized_user_file(str(TOKEN), SCOPES) if TOKEN.exists() else None
    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
        except RefreshError:
            creds = None  # expired or revoked: sign in again below
    if not creds or not creds.valid:
        if not CREDENTIALS.exists():
            raise StepError("credentials.json not found in the project folder - see SETUP_GOOGLE.md")
        creds = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS), SCOPES).run_local_server(port=0)
        TOKEN.write_text(creds.to_json(), encoding="utf-8")
    return creds


def q(s):
    return s.replace("\\", "\\\\").replace("'", "\\'")


def utf16_len(s):
    return len(s.encode("utf-16-le")) // 2


def get_folder(drive):
    res = drive.files().list(q=f"name = '{FOLDER_NAME}' and mimeType = 'application/vnd.google-apps.folder' "
                               "and trashed = false", fields="files(id)").execute()
    if res["files"]:
        return res["files"][0]["id"]
    return drive.files().create(body={"name": FOLDER_NAME, "mimeType": "application/vnd.google-apps.folder"},
                                fields="id").execute()["id"]


def publish_doc(creds, data, run_key, log, reprocess=False):
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaInMemoryUpload

    drive = build("drive", "v3", credentials=creds, cache_discovery=False)
    folder = get_folder(drive)
    prefix = f"Client - {data['client']['name']} - "
    found = drive.files().list(
        q=f"name contains '{q(prefix)}' and '{folder}' in parents and "
          "mimeType = 'application/vnd.google-apps.document' and trashed = false",
        fields="files(id,name,webViewLink,appProperties,createdTime)", orderBy="createdTime").execute()["files"]
    found = [f for f in found if f["name"].startswith(prefix)]

    if not found:
        meta = {"name": doc_title(data), "mimeType": "application/vnd.google-apps.document",
                "parents": [folder], "appProperties": {run_key: "1"}}
        media = MediaInMemoryUpload(render_doc_html(data).encode("utf-8"), mimetype="text/html")
        f = drive.files().create(body=meta, media_body=media, fields="id,name,webViewLink").execute()
        log.add("Drive: create client doc", "OK", f"{f['name']} -> {f['webViewLink']}")
        return f["webViewLink"]

    f = found[0]
    if len(found) > 1:
        log.add("Drive: duplicate check", "MANUAL", f"{len(found)} docs start with '{prefix}' - using the oldest, please merge")
    if run_key in (f.get("appProperties") or {}) and not reprocess:
        log.add("Drive: client doc", "SKIPPED", f"this transcript was already recorded in '{f['name']}' -> {f['webViewLink']}")
        return f["webViewLink"]

    # Existing client: append a dated update, never overwrite.
    docs = build("docs", "v1", credentials=creds, cache_discovery=False)
    end = docs.documents().get(documentId=f["id"]).execute()["body"]["content"][-1]["endIndex"] - 1
    heading, body = render_update_text(data)
    if reprocess and run_key in (f.get("appProperties") or {}):
        heading += " (re-processed)"
    text = "\n" + heading + "\n" + body
    start, stop = end + 1, end + utf16_len(text)
    docs.documents().batchUpdate(documentId=f["id"], body={"requests": [
        {"insertText": {"location": {"index": end}, "text": text}},
        {"deleteParagraphBullets": {"range": {"startIndex": start, "endIndex": stop}}},
        {"updateParagraphStyle": {"range": {"startIndex": start, "endIndex": stop},
                                  "paragraphStyle": {"namedStyleType": "NORMAL_TEXT"}, "fields": "namedStyleType"}},
        {"updateParagraphStyle": {"range": {"startIndex": start, "endIndex": start + utf16_len(heading)},
                                  "paragraphStyle": {"namedStyleType": "HEADING_1"}, "fields": "namedStyleType"}},
    ]}).execute()
    drive.files().update(fileId=f["id"], body={"appProperties": {run_key: "1"}}).execute()
    log.add("Drive: append dated update to existing client doc", "OK", f"{f['name']} -> {f['webViewLink']}")
    return f["webViewLink"]


def publish_draft(creds, data, run_key, log, state):
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError

    gmail = build("gmail", "v1", credentials=creds, cache_discovery=False)
    previous = state.get(run_key, {}).get("draft_id")
    if previous:
        try:
            gmail.users().drafts().get(userId="me", id=previous, format="minimal").execute()
            log.add("Gmail: draft", "SKIPPED", f"draft already exists for this call (id {previous})")
            return previous
        except HttpError as err:
            if err.resp.status != 404:
                raise
            log.add("Gmail: draft", "MANUAL",
                    "the earlier draft is gone (sent or deleted) - not recreating it; delete output/state.json entry to force")
            return None

    e = data["email"]
    msg = EmailMessage()
    if e["to"]:
        msg["To"] = e["to"]
    msg["Subject"] = e["subject"]
    msg.set_content(e["body"])
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    draft = gmail.users().drafts().create(userId="me", body={"message": {"raw": raw}}).execute()

    # Verify with Gmail that it really is a draft and not sent.
    check = gmail.users().drafts().get(userId="me", id=draft["id"], format="metadata").execute()
    labels = check["message"].get("labelIds", [])
    if "DRAFT" not in labels or "SENT" in labels:
        raise StepError(f"Gmail returned unexpected labels {labels}")
    state.setdefault(run_key, {})["draft_id"] = draft["id"]
    log.add("Gmail: create DRAFT (not sent)", "OK",
            f"id {draft['id']}, labels {labels}, recipient {'blank - [CONFIRM CLIENT EMAIL ADDRESS]' if not e['to'] else e['to']}")
    return draft["id"]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("extraction")
    ap.add_argument("--dry-run", action="store_true", help="write local files only, do not touch Google")
    ap.add_argument("--reprocess", action="store_true", help="append to the doc even if this transcript was recorded")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # Windows consoles choke on ₹

    path = pathlib.Path(args.extraction).resolve()
    outdir = path.parent
    data, transcript = validate.load(path)
    log = RunLog(outdir / "run_log.json")
    print(f"\nProcessing: {data['meta']['call_title']}\n")

    # Gate: nothing goes to Google unless every safety check passes.
    results = validate.run_checks(data, transcript)
    failed = [n for n, ok, _ in results if not ok]
    if failed:
        log.add("Validation", "FAILED", "; ".join(failed))
        log.save()
        print("\nStopped before touching Google. Fix extraction.json and run again.")
        return 1
    log.add("Validation", "OK", f"{len(results)}/{len(results)} safety checks passed")

    # Local copies always - also the fallback if Google fails.
    (outdir / "summary.md").write_text(render_summary_md(data), encoding="utf-8")
    (outdir / "client_doc.html").write_text(render_doc_html(data), encoding="utf-8")
    (outdir / "email_draft.txt").write_text(render_email_text(data), encoding="utf-8")
    (outdir / "whatsapp.txt").write_text(data["whatsapp"], encoding="utf-8")
    n = len(data["whatsapp"])
    log.add("Local files: summary, doc, email, WhatsApp", "OK", f"{outdir.relative_to(ROOT)} (WhatsApp {n}/300 chars)")

    run_key = "tx_" + hashlib.sha256(transcript.encode("utf-8")).hexdigest()[:16]
    if args.dry_run:
        log.add("Google Drive + Gmail", "SKIPPED", "--dry-run")
        log.save()
        return 0

    state = json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else {}
    try:
        creds = get_credentials()
        log.add("Google sign-in", "OK")
    except Exception as err:  # noqa: BLE001 - report every auth failure plainly
        log.add("Google sign-in", "FAILED", explain(err))
        log.add("Next", "MANUAL", "local files are ready; copy them into Drive/Gmail by hand or fix sign-in and re-run")
        log.save()
        return 1

    ok = True
    for name, fn in (("Drive: client doc", lambda: publish_doc(creds, data, run_key, log, args.reprocess)),
                     ("Gmail: draft", lambda: publish_draft(creds, data, run_key, log, state))):
        try:
            fn()
        except Exception as err:  # noqa: BLE001 - one failed step must not hide the other
            ok = False
            log.add(name, "FAILED", explain(err))
    STATE.write_text(json.dumps(state, indent=2), encoding="utf-8")
    log.add("WhatsApp reminder", "MANUAL", f"text only, {n} chars - copy from whatsapp.txt into AiSensy after approval")
    log.save()
    print("\nNothing has been sent. Review the draft in Gmail before sending.")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
