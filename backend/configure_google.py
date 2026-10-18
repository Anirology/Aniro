"""Import a downloaded Google OAuth web client without printing credentials."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "google_oauth_client.json"
TARGET = ROOT / ".env"
REDIRECT = "http://127.0.0.1:8000/api/integrations/google/callback"

def main():
    if not SOURCE.exists():
        raise SystemExit("Place the downloaded Web application OAuth JSON at backend/google_oauth_client.json first.")
    payload = json.loads(SOURCE.read_text(encoding="utf-8-sig"))
    web = payload.get("web")
    if not isinstance(web, dict):
        raise SystemExit("This is not a Web application OAuth client JSON. Create a Web application client in Google Auth Platform.")
    if REDIRECT not in web.get("redirect_uris", []):
        raise SystemExit("Add this exact Authorized redirect URI in Google Cloud, then download the client JSON again: " + REDIRECT)
    client_id, client_secret = web.get("client_id"), web.get("client_secret")
    if not client_id or not client_secret:
        raise SystemExit("The downloaded JSON is missing a client ID or client secret.")
    values = {}
    if TARGET.exists():
        for line in TARGET.read_text(encoding="utf-8-sig").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                name, value = line.split("=", 1)
                values[name] = value
    values.update({"ANIRO_GOOGLE_CLIENT_ID": client_id,
                   "ANIRO_GOOGLE_CLIENT_SECRET": client_secret,
                   "ANIRO_GOOGLE_ALLOWED_EMAIL": "aniruththens@gmail.com",
                   "ANIRO_GOOGLE_REDIRECT_URI": REDIRECT})
    TARGET.write_text("\n".join(f"{name}={value}" for name, value in values.items()) + "\n", encoding="utf-8")
    print("Google OAuth web client imported into backend/.env. Credentials were not printed.")

if __name__ == "__main__": main()
