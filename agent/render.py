"""Turn extraction.json into the client doc (HTML), a dated update block (plain text) and the email.

The doc layout is fixed here, not by the model, so every client file has the same structure.
"""
import datetime
import html
import re

STATUS_LABEL = {
    "confirmed": "",
    "preference": "Client preference",
    "tentative": "Tentative",
    "unconfirmed": "Not yet confirmed",
}

APPEND_MARKER = "Later calls are appended below as dated updates. Earlier entries are never overwritten."


def doc_title(data):
    return f"Client - {data['client']['name']} - {data['meta']['call_date']}"


def nice_date(iso):
    d = datetime.date.fromisoformat(iso)
    return f"{d.day} {d.strftime('%b %Y')} ({d.strftime('%A')})"


def _e(s):
    return html.escape(str(s))


def _items_html(items):
    out = []
    for it in items:
        label = STATUS_LABEL.get(it.get("status", "confirmed"), it.get("status", ""))
        tag = f" <i>({_e(label)})</i>" if label else ""
        out.append(f"<li>{_e(it['text'])}{tag}</li>")
    return "<ul>" + "".join(out) + "</ul>"


def render_doc_html(data):
    c, m, b = data["client"], data["meta"], data["budget"]
    team = ", ".join(c["team"])
    steps = "".join(
        f"<tr><td>{_e(s['action'])}</td><td>{_e(s['owner'])}</td>"
        f"<td>{_e(s['deadline'])}</td><td>{_e(s['status'])}</td></tr>"
        for s in data["next_steps"]
    )
    return f"""<html><head><meta charset="utf-8"></head><body>
<h1>{_e(doc_title(data))}</h1>
<p><i>Generated from the call transcript for review. Items marked [CONFIRM] need checking.
Labels: <b>Tentative</b> = depends on something else; <b>Not yet confirmed</b> = proposed, not agreed;
<b>Client preference</b> = a wish, not a commitment. Unlabelled items were stated by the client.</i></p>

<h1>Client Profile</h1>
<ul>
<li><b>Client name:</b> {_e(c['name'])}</li>
<li><b>Business name:</b> {_e(c['business'])}</li>
<li><b>Call date:</b> {_e(nice_date(m['call_date']))} - {_e(m['call_title'])}, {_e(m['duration_min'])} min</li>
<li><b>Business overview:</b> {_e(c['business_type'])}; {_e(c['scale'])}</li>
<li><b>Team structure:</b> {_e(team)}</li>
<li><b>Location:</b> {_e(c['location'])}</li>
<li><b>Email:</b> {_e(c['email'] or '[CONFIRM CLIENT EMAIL ADDRESS]')}</li>
<li><b>Private contact:</b> {_e(c['private_contact'])}</li>
</ul>

<h1>1. Executive Summary</h1>
<p>{_e(data['executive_summary'])}</p>

<h1>2. Business Goals</h1>
{_items_html(data['goals'])}

<h1>3. Current Challenges and Pain Points</h1>
{_items_html(data['pain_points'])}

<h1>4. Business Context</h1>
{_items_html(data['business_context'])}

<h1>5. Budget and Commercial Context</h1>
<ul>
<li><b>Indicated budget:</b> {_e(b['range'])}</li>
<li><b>Status:</b> {_e(b['status'])}</li>
<li><b>Financial decision-maker:</b> {_e(b['decision_maker'])}</li>
<li><b>Notes:</b> {_e(b['notes'])}</li>
</ul>

<h1>6. Objections and Concerns</h1>
{_items_html(data['objections'])}

<h1>7. Agreed Next Steps</h1>
<table border="1" cellpadding="6" style="border-collapse:collapse">
<tr><th>Action</th><th>Responsible</th><th>Deadline</th><th>Status</th></tr>
{steps}
</table>

<h1>8. Pending Confirmations</h1>
<ul>{''.join(f'<li>{_e(p)}</li>' for p in data['pending_confirmations'])}</ul>

<h1>9. Privacy Notes</h1>
<ul>{''.join(f'<li>{_e(p)}</li>' for p in data['privacy_notes'])}</ul>

<h1>Call History</h1>
<p>{_e(nice_date(m['call_date']))}: {_e(m['call_title'])} - initial record created.</p>
<p>{APPEND_MARKER}</p>
</body></html>"""


def render_update_text(data):
    """Plain-text block appended to an existing client doc for a later call.

    Returns (heading, body) so the caller can style the heading line.
    """
    m, b = data["meta"], data["budget"]

    def bullets(items):
        return "\n".join(f"  - {it['text']}" + (f" ({STATUS_LABEL[it['status']]})" if STATUS_LABEL.get(it['status']) else "") for it in items)

    heading = f"Update - {nice_date(m['call_date'])} - {m['call_title']}"
    body = "\n".join([
        f"Summary: {data['executive_summary']}",
        "Goals:", bullets(data["goals"]),
        "Pain points:", bullets(data["pain_points"]),
        "Business context:", bullets(data["business_context"]),
        f"Budget: {b['range']} - {b['status']}. Decision-maker: {b['decision_maker']}.",
        "Concerns:", bullets(data["objections"]),
        "Next steps:",
        "\n".join(f"  - {s['action']} | {s['owner']} | {s['deadline']} | {s['status']}" for s in data["next_steps"]),
        "Pending confirmations:",
        "\n".join(f"  - {p}" for p in data["pending_confirmations"]),
    ])
    return heading, body


def render_email_text(data):
    e = data["email"]
    return f"To: {e['to'] or '(blank - [CONFIRM CLIENT EMAIL ADDRESS])'}\nSubject: {e['subject']}\n\n{e['body']}\n"


def render_summary_md(data):
    """Human-readable call summary for the console / Claude report."""
    def lst(items):
        return "\n".join(f"- {it['text']}" + (f" _({STATUS_LABEL[it['status']]})_" if STATUS_LABEL.get(it['status']) else "") for it in items)
    b = data["budget"]
    steps = "\n".join(f"| {s['action']} | {s['owner']} | {s['deadline']} | {s['status']} |" for s in data["next_steps"])
    return f"""# Call summary - {data['client']['name']}, {data['client']['business']} ({data['meta']['call_date']})

{data['executive_summary']}

## Client goals
{lst(data['goals'])}

## Pain points
{lst(data['pain_points'])}

## Budget / timeline
- Budget: {b['range']} - **{b['status']}** (decision-maker: {b['decision_maker']})
{chr(10).join('- ' + d['value'] for d in data['derived_dates'])}

## Objections
{lst(data['objections'])}

## Agreed next steps
| Action | Owner | Deadline | Status |
|---|---|---|---|
{steps}

## Pending confirmations
{chr(10).join('- ' + p for p in data['pending_confirmations'])}
"""


def html_to_text(s):
    s = re.sub(r"<[^>]+>", " ", s)
    return html.unescape(re.sub(r"\s+", " ", s))
