# "After the discovery call" agent

Transcript in → client Google Doc + Gmail **draft** + WhatsApp text out. Drafts only; a person approves everything.

- **Run it:** see [SOP.md](SOP.md). **First-time Google setup:** [SETUP_GOOGLE.md](SETUP_GOOGLE.md).
- **Prompt / skill file:** [.claude/skills/discovery-followup/SKILL.md](.claude/skills/discovery-followup/SKILL.md)

## How it works

```
transcript.txt
  → Claude (skill file)     reads the call, writes extraction.json: facts + verbatim quote for each,
                             statuses (confirmed / tentative / unconfirmed), [CONFIRM] list,
                             redactions, email, WhatsApp
  → agent/validate.py       17 safety checks. Any failure = stop, nothing leaves the machine
  → agent/publish.py        Drive: find-or-create Clients/"Client - <Name> - <Date>", append dated
                             updates for later calls. Gmail: drafts.create only, then re-reads the
                             draft to confirm label = DRAFT. Writes run_log.json.
```

**Why Claude + a short Python script (not n8n/Make/Zapier):**
- Most of the work is judgement (what is sensitive, what is only tentative). Claude does that well,
  and the skill file reads as plain English the owner can edit.
- The risky part (what reaches Google) should be predictable, not left to a model. A ~200-line
  script does exactly two things, checks for duplicates, and can be unit-tested. The tests prove it
  never calls send, which you can't easily prove inside a no-code tool.
- Everything is free: Claude in VS Code, free Google APIs. No paid API keys, no hosting, and
  credentials stay on one laptop.
- Least privilege: `drive.file` (the app only sees files it created) + `gmail.compose`.

## Sensitive details: what was kept out of the email, and why

| In the transcript | Decision |
|---|---|
| "I think they're in financial trouble, don't put that in writing" | **Dropped everywhere**, including the Doc. It's speculation about a third party, and she asked explicitly. Only the fact (60 days overdue) is kept, in the internal Doc. |
| Personal number, "don't share it with Arjun" | Never stored. The Doc shows `[PRIVATE CONTACT DETAIL WITHHELD]`, because a client file is exactly what an assistant like Arjun may later see. |
| Debtor names, ₹1.8 lakh, 60 days | Internal Doc only. Naming her customers in an email adds risk and no value. |
| ₹25-30k budget, husband decides | Doc: **tentative**, with the dependency noted. Email: "discuss it internally first". No figure, no husband, no pressure. |
| Chatbot sent wrong prices | Put **in** the email on purpose. It's her main objection, so the email answers it: nothing reaches a customer until she approves it. |

## Results on the sample transcript
- Doc: `Clients/Client - Riya Mehta - 2026-10-26`, created in Drive (verified by re-reading it through the API).
- Gmail draft created. Its only label is `DRAFT`, and the recipient is blank (`[CONFIRM CLIENT EMAIL ADDRESS]`).
- WhatsApp: **228 / 300 characters**.
- Second run: both steps `SKIPPED`, still one Doc and one draft.
- Outputs: `output/2026-10-26_riya-mehta/` (summary.md, client_doc.html, email_draft.txt, whatsapp.txt, run_log.json).

## Testing: `python -m pytest -q` → 21 passed

| Claim | How it is checked |
|---|---|
| Correct extraction, no hallucination | Every fact must carry a quote found **verbatim** in the transcript. Every number in the Doc, email and WhatsApp must appear in the transcript or in a declared derived date. Tests inject "Expand to Bangalore" and "12 retail partners": both are caught. |
| Sensitive info protected | Each "don't share / don't put in writing" phrase in the transcript must have a redaction entry. Phone patterns (masked or plain), speculation words ("financial trouble", "going under", "insolvent"), and debtor/budget/family words in client-facing text are all blocked. 7 tests inject each kind of leak; all are caught. |
| Document created correctly | Live run, then Drive export re-read: one doc, correct name, all sections, no leaked terms. |
| Draft-only | Test: `publish.py` contains no `.send(` call. Live: Gmail returns label `DRAFT` only. Invalid input → the publisher exits before any Google call (tested). |
| WhatsApp under 300 | Checked in the validator and in a test (300 chars → fail). |

## What would break first in real use

- **Google sign-in expires every 7 days.** The Google app is in "Testing" mode, so a week after setup
  the run fails at sign-in, probably the morning after an important call. *Fix:* press "Publish app"
  (fine for one user), or move to a Workspace "internal" app. The script already catches the expiry
  and reopens the sign-in instead of crashing.
- **Real Fathom transcripts are messier than this one.** Names come through misspelt ("Ria Mehta"),
  calls mix Hindi and English, and off-the-record remarks don't match the cue list ("isko likhna
  mat", "between ourselves"). That means a duplicate client file, an update added to the wrong
  client's file, or a private remark slipping past the pattern check. *Fix:* match clients on email
  or a client ID kept in a small index sheet, not on name. Have Claude show "I'll add this to
  <doc>, correct?" before appending. Add a Hinglish cue list, and add a test for every slip found.
- **AiSensy won't send free text.** Messages a business starts outside WhatsApp's 24-hour reply
  window must use a template approved in advance, so the 228-character text can't be pasted and
  sent as it is. *Fix:* register one "session reminder" template in AiSensy with variables
  ({{name}}, {{day}}, {{link}}), and have the agent output those values instead of free text.

## 5-minute recording plan
1. **0:00-0:30** The brief, and the transcript file. Point out the 2 sensitive lines.
2. **0:30-1:00** Show the skill file: grounding, `[CONFIRM]` and redaction rules.
3. **1:00-2:15** In VS Code, type `/discovery-followup transcripts/2026-10-26_riya-mehta.txt`.
   Show the 17/17 checks, then OK for Drive and Gmail. Before recording, reset so it creates
   everything fresh: move the Doc to Drive trash, delete the Gmail draft, and delete `output/state.json`.
4. **2:15-3:00** Open the Drive Doc: profile, tentative budget, next-steps table,
   Pending Confirmations, Privacy Notes. Search the doc for "98" and "trouble": nothing.
5. **3:00-3:50** Open Gmail Drafts: blank recipient, review block, chatbot concern answered,
   `[CAL.COM BOOKING LINK]`. Show that the Sent folder is empty.
6. **3:50-4:20** WhatsApp text plus 228 characters. Run again and show that both steps are SKIPPED.
7. **4:20-5:00** Safety demo: add "call me on 98XXX 12345" to the WhatsApp text in extraction.json, run, and show
   it stops with "Stopped before touching Google". Undo the change.
