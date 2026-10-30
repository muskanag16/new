# SOP - After the discovery call

**What it does:** turns a call transcript into (1) a call summary, (2) a client Google Doc in Drive → `Clients`,
(3) a Gmail **draft** follow-up, and (4) a WhatsApp reminder text. **It never sends anything.** You do.

## How to run it (2 minutes)
1. Save the Fathom transcript as a text file in `E:\intern_task\transcripts\`, named
   `YYYY-MM-DD_firstname-lastname.txt` (e.g. `2026-10-26_riya-mehta.txt`).
2. Open the `intern_task` folder in VS Code → open the Claude panel → type:
   `/discovery-followup transcripts/2026-10-26_riya-mehta.txt`
3. Wait 1-2 minutes. Claude shows the summary, the Doc link, "Gmail: create DRAFT - OK", the WhatsApp
   text and a list of things to confirm. Every step is marked **OK**, **SKIPPED**, **MANUAL** or **FAILED**.

Running it twice is safe: it will not create a second doc or a second draft.

## Before you send the email - check all 7
1. **Recipient** - it is blank on purpose. Add the client's email yourself.
2. **Delete the review block** at the top of the email (`[REVIEW BEFORE SENDING ...]` to `[END OF REVIEW BLOCK]`).
3. **Replace placeholders** - `[CAL.COM BOOKING LINK]` and `[YOUR NAME]`. Search the email for `[` to be sure none are left.
4. **Facts** - is everything something the client actually said? Nothing added, nothing exaggerated.
5. **Dates and promises** - "by Monday", "Thursday afternoon": can you really deliver that?
6. **Nothing private** - no phone numbers, no other customers' names or amounts owed, no budget figure,
   no family members, nothing the client said "don't put in writing".
7. **Automation promises** - it should say *you* approve customer messages first, never "fully automatic".

Then also: open the **Client Doc**, check section **8. Pending Confirmations**, and fill in answers as you get them.
**WhatsApp:** read it, then paste it into AiSensy yourself.

## When something goes wrong
| You see | What it means / what to do |
|---|---|
| `Validation FAILED` | The agent caught a problem (e.g. private detail, missing link) and **stopped before touching Google**. Tell Claude: *"fix the validation failures and run again"*. |
| Browser opens asking you to sign in | Normal about once a week. Sign in, tick both boxes, Continue. |
| `Google sign-in FAILED` | Delete `token.json` in the folder and run again. If it says `credentials.json not found`, see `SETUP_GOOGLE.md`. |
| `API is not enabled` | Follow step 2 of `SETUP_GOOGLE.md`. |
| `Google is busy` / any one step FAILED | Wait a minute and run again - steps that worked are skipped, not repeated. |
| `SKIPPED - already recorded` | Not an error. That call was already processed. |
| `MANUAL - several docs start with...` | Two docs exist for one client. Merge them in Drive, delete the extra. |
| Nothing works | All four outputs are also saved in `output\<call name>\` (`email_draft.txt`, `client_doc.html`, `whatsapp.txt`, `summary.md`). Copy them in by hand. |

## Why it cannot send by accident
- The program only knows how to *create* drafts - there is no send command in it (checked by an automatic test).
- The draft has no recipient, so Gmail cannot send it until you add one.
- WhatsApp text is only shown on screen - nothing is connected to AiSensy.
- **Only you press Send, in Gmail.**
