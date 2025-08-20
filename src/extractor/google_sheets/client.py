import os
from dataclasses import dataclass
from typing import Optional

# Lazy imports so make check works without deps installed
try:  # pragma: no cover - import-time optional
    from google.oauth2.credentials import Credentials  # type: ignore
    from google_auth_oauthlib.flow import InstalledAppFlow  # type: ignore
    from google.auth.transport.requests import Request  # type: ignore
    from googleapiclient.discovery import build  # type: ignore
except Exception:  # pragma: no cover - degrade gracefully
    Credentials = object  # type: ignore
    InstalledAppFlow = object  # type: ignore
    Request = object  # type: ignore
    build = None  # type: ignore

SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]


@dataclass
class GoogleAuthConfig:
    # Paths relative to repo root or absolute
    credentials_file: str = os.environ.get("GOOGLE_OAUTH_CLIENT_JSON", "./.secrets/google_client.json")
    token_file: str = os.environ.get("GOOGLE_OAUTH_TOKEN_JSON", "./.secrets/google_token.json")


def ensure_credentials(config: Optional[GoogleAuthConfig] = None):
    """Ensure OAuth credentials exist; perform local auth flow if needed.

    Returns a google.oauth2.credentials.Credentials instance when deps are available,
    otherwise raises a helpful error.
    """
    config = config or GoogleAuthConfig()

    if build is None:
        raise RuntimeError(
            "Google API client libraries not installed. Install with: pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib"
        )

    creds = None
    if os.path.exists(config.token_file):
        creds = Credentials.from_authorized_user_file(config.token_file, SCOPES)  # type: ignore
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not getattr(creds, "valid", False):
        if creds and getattr(creds, "expired", False) and getattr(creds, "refresh_token", None):
            creds.refresh(Request())  # type: ignore
        else:
            if not os.path.exists(config.credentials_file):
                raise FileNotFoundError(
                    f"Google OAuth client credentials not found at {config.credentials_file}. Download the OAuth client JSON and set GOOGLE_OAUTH_CLIENT_JSON."
                )
            flow = InstalledAppFlow.from_client_secrets_file(config.credentials_file, SCOPES)  # type: ignore
            creds = flow.run_local_server(port=0)  # type: ignore
        # Save the credentials for the next run
        os.makedirs(os.path.dirname(config.token_file), exist_ok=True)
        with open(config.token_file, "w") as token:
            token.write(creds.to_json())  # type: ignore
    return creds


def get_sheets_service(credentials=None):
    if build is None:
        raise RuntimeError(
            "Google API client libraries not installed. Install with: pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib"
        )
    if credentials is None:
        credentials = ensure_credentials()
    service = build("sheets", "v4", credentials=credentials)  # type: ignore
    return service.spreadsheets()
