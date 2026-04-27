# Google OAuth setup for Hearth

Hearth needs to push events into your family Google Calendar. To do that, you authorize Hearth via OAuth using credentials you create in Google Cloud Console.

This is a one-time setup, ~5–10 minutes.

## 1. Create a Google Cloud project

1. Go to https://console.cloud.google.com
2. Create a new project (or pick an existing one)
3. Note the project name — anything is fine

## 2. Enable the Google Calendar API

1. In the project, go to **APIs & Services → Library**
2. Search for "Google Calendar API"
3. Click **Enable**

## 3. Configure the OAuth consent screen

1. Go to **APIs & Services → OAuth consent screen**
2. User type: **External** (this is for personal use, but External is required for the OAuth flow to work outside Google Workspace)
3. App name: anything (e.g., "Hearth (home)")
4. User support email + Developer contact: your email
5. Scopes: add `.../auth/calendar` (calendar full read/write)
6. Test users: add your Google account email — only test users can authorize an unverified app, which is what we want here. Don't submit for verification — that's for public apps.

## 4. Create OAuth 2.0 Client ID credentials

1. Go to **APIs & Services → Credentials → Create Credentials → OAuth client ID**
2. Application type: **Web application**
3. Authorized redirect URI: `http://hearth.local/api/google/oauth/callback` (or `http://localhost:8080/api/google/oauth/callback` for local dev). The redirect URI shown in Hearth's `/setup/google` page is the authoritative version — copy from there.
4. Save. Google shows you a Client ID + Client Secret. Copy both.

## 5. Paste into Hearth

1. Visit Hearth's `/setup/google` page (you'll be on it automatically during first-run wizard)
2. Paste the Client ID and Client Secret
3. Click **Continue with Google**
4. Google asks you to authorize Hearth → click **Allow**
5. You'll be returned to Hearth with "Connected ✓"

## Troubleshooting

- **"App is in testing"** warning during consent: expected. Click "Continue" past it. Only test users (you) can authorize.
- **Redirect URI mismatch error**: the URI in the GCP OAuth client config must match EXACTLY what Hearth shows. No trailing slash. Match scheme (http/https), host, port, path. Update GCP if needed.
- **Refresh token expired** after 90 days: Google's inactivity rule for unverified apps. Visit `/admin/google` (Phase 8) and reconnect.

## What scopes does Hearth use?

Just `https://www.googleapis.com/auth/calendar` — full read/write of your Google Calendar(s). Nothing else.

## Privacy

The Client ID, Client Secret, and OAuth tokens are stored locally in your Hearth SQLite database (in the volume mounted at `/data`). They never leave your home server.
