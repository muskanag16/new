---
name: discovery-followup
description: After a discovery call, turn the transcript into a client record (Google Doc), a Gmail DRAFT follow-up and a WhatsApp reminder text. Drafts only - never sends. Usage - /discovery-followup transcripts/<file>.txt
---

# After-the-discovery-call agent

You are preparing post-call paperwork for a one-person consulting practice. The consultant
approves everything. **You never send anything.** The publisher script can only create a
Google Doc and a Gmail *draft*.

Input: the transcript path given as the argument (e.g. `transcripts/2026-10-26_riya-mehta.txt`).
Output folder: `output/<transcript file name without .txt>/`.

## Step 1 - Read and analyse (no writing yet)

Read the whole transcript. Before writing anything, list for yourself:
- every fact the client stated (who, what, numbers, dates);
- every *tentative* item (budgets "I could do", "need to check with...");
- every *proposed but not confirmed* item (meeting days without a time, "next week");
- every **sensitive cue** - phrases like "don't put that in writing", "don't share", "off the record",
  "between us", "confidential", personal phone numbers, health/family/financial gossip about third parties.

## Step 2 - Write `extraction.json`

Write `output/<call-id>/extraction.json` following the schema below exactly.
Use `output/2026-10-26_riya-mehta/extraction.json` as the reference example.

Rules - these are not optional:

1. **No invented facts.** Every item in `goals`, `pain_points`, `business_context`, `objections`,
   `budget` and `next_steps` carries an `evidence` field: a short quote copied *verbatim* from the
   transcript. If you cannot quote it, you cannot state it.
2. Anything missing or ambiguous is written as `[CONFIRM]` (or `[CONFIRM: <what>]`) and listed in
   `pending_confirmations`. Never guess an email address, surname spelling, time, location or price.
3. Every item has a `status`: `confirmed` (client stated it as fact), `preference` (client wish),
   `tentative` (depends on something else) or `unconfirmed` (proposed, not agreed).
4. Dates you *derive* (e.g. "Monday" -> 2 Nov 2026) go in `derived_dates` with the reasoning, and are
   shown with `[CONFIRM]` until the consultant checks them.
5. **Sensitive cues.** For every sensitive cue, add an entry to `redactions` with:
   - `cue_quote`: the verbatim instruction phrase only (e.g. "don't put that in writing anywhere") -
     never the sensitive content itself;
   - `handling`: what you did;
   - `must_not_appear`: words/numbers that must not appear in any output (the validator checks).
   Then leave the sensitive content out of the doc, email and WhatsApp entirely. Personal phone
   numbers are replaced by `[PRIVATE CONTACT DETAIL WITHHELD]`. Speculation about third parties is
   dropped, not softened. `privacy_notes` (shown in the doc) contains handling instructions only and
   must not hint at what was withheld.
6. **Client-facing text (email, WhatsApp)** must not mention: other customers or debtors by name,
   amounts owed, family members, the budget figure, or anything from `redactions`. Acknowledge the
   commercial side only as "once you've had a chance to discuss it internally".
7. If the client expressed worry about automation, the email acknowledges it and proposes a
   human-approved-first approach. Never promise fully automatic customer messaging.
8. Email `to` is `""` unless an address appears in the transcript. The body starts with a
   `[REVIEW BEFORE SENDING - delete this block]` checklist for the consultant. Include the
   placeholder `[CAL.COM BOOKING LINK]` and sign off with `[YOUR NAME]`.
9. WhatsApp text: under 300 characters, friendly, no private or payment details.

### Schema

```
meta:        {call_id, call_title, call_date (YYYY-MM-DD), duration_min, transcript_file}
client:      {name, business, business_type, scale, team[], location, email, private_contact}
executive_summary: string
goals[], pain_points[], business_context[], objections[]:  {text, status, evidence}
budget:      {range, status, decision_maker, notes, evidence}
next_steps[]: {action, owner, deadline, status, evidence}
derived_dates[]: {value, basis}
pending_confirmations[]: string
privacy_notes[]: string
redactions[]: {cue_quote, handling, must_not_appear[]}
email:       {to, subject, body}
whatsapp:    string
```

## Step 3 - Validate

Run:

```
python agent/validate.py output/<call-id>/extraction.json
```

If any check fails, fix `extraction.json` and re-run. Do not continue with failures.

## Step 4 - Publish (drafts only)

Run:

```
python agent/publish.py output/<call-id>/extraction.json
```

The script re-validates, then: finds or creates the `Clients` folder in Drive; finds an existing
`Client - <Name> - ...` doc (appends a dated update) or creates `Client - <Name> - <call date>`;
creates a Gmail draft; writes `output/<call-id>/run_log.json`. Re-running the same transcript is
safe - it skips work already done.

If Google is not set up or a step fails, run with `--dry-run` to still produce local files, and
tell the consultant exactly which step failed and the error message. Never say a doc or draft was
created unless the script printed `OK` for that step.

## Step 5 - Report to the consultant

Show: the call summary, the Doc link, the draft status, the WhatsApp text with its character count,
and the full `pending_confirmations` list. End with: "Nothing has been sent. Please review the
draft in Gmail before sending."
