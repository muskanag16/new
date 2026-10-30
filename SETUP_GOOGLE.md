# One-time Google setup (about 10 minutes, free)

You do this once. It lets the agent create Docs in *your* Drive and drafts in *your* Gmail.
Nothing is shared with anyone else, and the agent can only see files it created itself.

## 1. Create a project
1. Go to https://console.cloud.google.com/ and sign in with the Google account you use for clients.
2. Top bar → project picker → **New project** → name it `discovery-agent` → **Create**. Make sure it is selected.

## 2. Turn on the three APIs
Go to **APIs & Services → Library**, search for and click **Enable** on each:
- **Google Drive API**
- **Google Docs API**
- **Gmail API**

## 3. Consent screen
**APIs & Services → OAuth consent screen** (may be called **Google Auth Platform → Branding**):
1. App name `Discovery agent`, your email as support + developer contact. User type **External**.
2. **Audience / Test users → Add users** → add your own Gmail address. Save.
   (Leave the app in *Testing*. See "Known limits" below.)

## 4. Download the key file
**APIs & Services → Credentials → Create credentials → OAuth client ID**
- Application type: **Desktop app**, name `discovery-agent` → **Create** → **Download JSON**.
- Rename the file to `credentials.json` and put it in the project folder (`E:\intern_task\credentials.json`).
- Never email or upload this file. It is already excluded from git.

## 5. First sign-in
Run the agent once (see SOP). A browser tab opens:
- "Google hasn't verified this app" → **Continue** (it is your own app).
- Tick both permissions (Drive files it creates, Gmail compose) → **Continue**.
A `token.json` file appears in the folder - that is your saved sign-in.

## Known limits
- While the app is in *Testing*, Google expires the sign-in after **7 days**. When that happens the
  run shows `Google sign-in FAILED` and opens the browser again - just sign in. To avoid it, press
  **Publish app** on the consent screen (fine for personal use; you will see the "unverified" warning once).
- To revoke access at any time: https://myaccount.google.com/permissions → Discovery agent → Remove.
