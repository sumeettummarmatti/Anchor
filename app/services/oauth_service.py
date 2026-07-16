from __future__ import annotations

from authlib.integrations.starlette_client import OAuth
from fastapi import Request

from app.core.config import Settings
from app.core.exceptions import ConfigurationError

SUPPORTED_OAUTH_PROVIDERS = {"google", "github"}


class OAuthService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def _client_settings(self, provider: str) -> dict[str, str]:
        if provider not in SUPPORTED_OAUTH_PROVIDERS:
            raise ConfigurationError("OAuth provider must be google or github.")

        if provider == "google":
            if not all(
                [
                    self.settings.google_client_id,
                    self.settings.google_client_secret,
                    self.settings.google_redirect_uri,
                ]
            ):
                raise ConfigurationError("Google OAuth is not configured.")
            return {
                "client_id": self.settings.google_client_id,
                "client_secret": self.settings.google_client_secret,
                "redirect_uri": self.settings.google_redirect_uri,
                "server_metadata_url": "https://accounts.google.com/.well-known/openid-configuration",
                "scope": "openid email profile",
            }

        if not all(
            [
                self.settings.github_client_id,
                self.settings.github_client_secret,
                self.settings.github_redirect_uri,
            ]
        ):
            raise ConfigurationError("GitHub OAuth is not configured.")
        return {
            "client_id": self.settings.github_client_id,
            "client_secret": self.settings.github_client_secret,
            "redirect_uri": self.settings.github_redirect_uri,
            "authorize_url": "https://github.com/login/oauth/authorize",
            "access_token_url": "https://github.com/login/oauth/access_token",
            "api_base_url": "https://api.github.com/",
            "scope": "read:user user:email",
        }

    def _client(self, provider: str):  # type: ignore[no-untyped-def]
        values = self._client_settings(provider)
        oauth = OAuth()
        common = {
            "client_id": values["client_id"],
            "client_secret": values["client_secret"],
            "client_kwargs": {"scope": values["scope"]},
        }
        if provider == "google":
            oauth.register(
                name=provider,
                server_metadata_url=values["server_metadata_url"],
                **common,
            )
        else:
            oauth.register(
                name=provider,
                authorize_url=values["authorize_url"],
                access_token_url=values["access_token_url"],
                api_base_url=values["api_base_url"],
                **common,
            )
        return oauth.create_client(provider), values["redirect_uri"]

    async def authorize_redirect(self, provider: str, request: Request):  # type: ignore[no-untyped-def]
        client, redirect_uri = self._client(provider)
        return await client.authorize_redirect(request, redirect_uri)

    async def fetch_identity(self, provider: str, request: Request) -> tuple[str, str, str | None]:
        client, _ = self._client(provider)
        token = await client.authorize_access_token(request)
        if provider == "google":
            profile = await client.parse_id_token(request, token)
            return str(profile["sub"]), str(profile["email"]), profile.get("name")

        profile_response = await client.get("user", token=token)
        profile = profile_response.json()
        email = profile.get("email")
        if not email:
            emails_response = await client.get("user/emails", token=token)
            emails = emails_response.json()
            email = next((item["email"] for item in emails if item.get("primary")), None)
        if not email:
            raise ConfigurationError("GitHub account has no accessible email address.")
        return str(profile["id"]), str(email), profile.get("name") or profile.get("login")
