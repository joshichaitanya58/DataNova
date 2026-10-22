"""
Google Drive OAuth Refresh Token Generator for DataNova Platform
================================================================
Generates a persistent 15GB Personal Google Drive OAuth Refresh Token
for use in local .env or Render Cloud Environment Variables.

How to run:
    python generate_gdrive_refresh_token.py

Important for Long-term Production on Render:
1. In Google Cloud Console (https://console.cloud.google.com/):
   - Go to "APIs & Services" -> "OAuth consent screen".
   - If Publishing Status is "Testing", tokens EXPIRE AFTER 7 DAYS.
   - Click "PUBLISH APP" to switch to "In Production" so tokens NEVER expire!
2. Ensure "Google Drive API" is enabled in "Enabled APIs & Services".
"""

import os
import sys

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

try:
    from google_auth_oauthlib.flow import InstalledAppFlow
except ImportError:
    print("\n[ERROR] Missing required library: google-auth-oauthlib")
    print("Please run: pip install google-auth-oauthlib\n")
    sys.exit(1)

SCOPES = [
    'https://www.googleapis.com/auth/drive.file',
    'https://www.googleapis.com/auth/drive'
]


def main():
    print("=" * 65)
    print("      DataNova Google Drive OAuth Refresh Token Generator")
    print("=" * 65)

    client_id = (os.getenv('GDRIVE_CLIENT_ID') or os.getenv('GOOGLE_CLIENT_ID') or '').strip()
    client_secret = (os.getenv('GDRIVE_CLIENT_SECRET') or os.getenv('GOOGLE_CLIENT_SECRET') or '').strip()

    if client_id and 'your_' not in client_id:
        print(f"Found Google Client ID in .env: {client_id[:16]}...")
        use_env = input("Use this Client ID & Secret from .env? (Y/n): ").strip().lower()
        if use_env in ('n', 'no'):
            client_id = ""
            client_secret = ""

    if not client_id or not client_secret or 'your_' in client_secret:
        print("\nEnter your OAuth 2.0 Client credentials from Google Cloud Console:")
        client_id = input("Client ID: ").strip()
        client_secret = input("Client Secret: ").strip()

    if not client_id or not client_secret:
        print("[ERROR] Client ID and Secret are required to generate a token.")
        sys.exit(1)

    client_config = {
        "installed": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["http://localhost:8080/"]
        }
    }

    print("\nStarting local authentication server...")
    print("A browser window will open shortly. Please log in with your Google account and grant Drive permissions.")
    print("=" * 65)

    try:
        flow = InstalledAppFlow.from_client_config(
            client_config,
            scopes=SCOPES,
            redirect_uri="http://localhost:8080/"
        )
        creds = flow.run_local_server(
            port=8080,
            prompt='consent',
            access_type='offline'
        )

        refresh_token = creds.refresh_token
        if not refresh_token:
            print("\n[WARNING] No refresh token returned. (Google only returns it when prompt='consent' is used).")
            print("Please run this script again with prompt='consent'.")
            return

        print("\n" + "=" * 65)
        print("🎉 SUCCESS! Here is your new Google Drive Refresh Token:")
        print("=" * 65)
        print(f"\nGDRIVE_REFRESH_TOKEN={refresh_token}\n")
        print("=" * 65)
        print("\nNext Steps:")
        print("1. In Render Dashboard -> Environment Variables:")
        print(f"   Set GDRIVE_REFRESH_TOKEN = {refresh_token}")
        print("   Set STORAGE_MODE = drive")
        print(f"   Ensure GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET match this app.")
        print("\n2. To prevent token expiration after 7 days:")
        print("   Go to https://console.cloud.google.com/apis/credentials/consent")
        print("   Under 'Publishing status', click 'PUBLISH APP' -> Switch to Production.")
        print("=" * 65 + "\n")

    except Exception as e:
        print(f"\n[ERROR] Authentication failed: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
