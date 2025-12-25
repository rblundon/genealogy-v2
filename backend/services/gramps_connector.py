"""Gramps Web API connector service."""

import os
import logging
import time
from typing import Optional
from dataclasses import dataclass, field

import httpx

logger = logging.getLogger(__name__)


@dataclass
class GrampsConnectionStatus:
    """Status of Gramps Web connection."""

    connected: bool
    url: str
    error: Optional[str] = None
    api_version: Optional[str] = None
    tree_name: Optional[str] = None
    database_id: Optional[str] = None
    locale: Optional[dict] = None


@dataclass
class TokenInfo:
    """Cached token information."""

    access_token: str
    refresh_token: Optional[str] = None
    expires_at: float = 0  # Unix timestamp when token expires


class GrampsConnector:
    """Connector for Gramps Web API with dynamic token generation."""

    # Token expires after 15 minutes by default, refresh 1 minute early
    TOKEN_REFRESH_BUFFER = 60

    def __init__(
        self,
        base_url: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        timeout: float = 10.0,
    ):
        """
        Initialize Gramps Web connector.

        Args:
            base_url: Gramps Web base URL (defaults to GRAMPS_WEB_URL env var)
            username: Gramps Web username (defaults to GRAMPS_USERNAME env var)
            password: Gramps Web password (defaults to GRAMPS_PASSWORD env var)
            timeout: Request timeout in seconds
        """
        self.base_url = (base_url or os.getenv("GRAMPS_WEB_URL", "")).rstrip("/")
        self.username = username or os.getenv("GRAMPS_USERNAME", "")
        self.password = password or os.getenv("GRAMPS_PASSWORD", "")
        self.timeout = timeout

        # Ensure URL has protocol
        if self.base_url and not self.base_url.startswith(("http://", "https://")):
            self.base_url = f"https://{self.base_url}"

        # Token cache
        self._token: Optional[TokenInfo] = None

    def _is_token_valid(self) -> bool:
        """Check if cached token is still valid."""
        if not self._token:
            return False
        # Check if token expires within the buffer period
        return time.time() < (self._token.expires_at - self.TOKEN_REFRESH_BUFFER)

    async def _get_token(self) -> Optional[str]:
        """
        Get a valid access token, fetching a new one if needed.

        Returns:
            Access token string or None if authentication fails
        """
        if self._is_token_valid():
            return self._token.access_token

        # Need to fetch a new token
        if not self.username or not self.password:
            logger.error("Gramps credentials not configured")
            return None

        try:
            async with httpx.AsyncClient(
                timeout=self.timeout,
                follow_redirects=True,
            ) as client:
                response = await client.post(
                    f"{self.base_url}/api/token/",
                    json={
                        "username": self.username,
                        "password": self.password,
                    },
                )

                if response.status_code == 200:
                    data = response.json()
                    access_token = data.get("access_token")
                    refresh_token = data.get("refresh_token")

                    if access_token:
                        # Token expires in 15 minutes (900 seconds) by default
                        expires_at = time.time() + 900
                        self._token = TokenInfo(
                            access_token=access_token,
                            refresh_token=refresh_token,
                            expires_at=expires_at,
                        )
                        logger.info("Successfully obtained Gramps Web API token")
                        return access_token

                elif response.status_code in (401, 403):
                    logger.error("Gramps Web authentication failed - invalid credentials")
                else:
                    try:
                        error_data = response.json()
                        error_msg = error_data.get("error", {}).get("message", "")
                        logger.error(f"Gramps Web token request failed: HTTP {response.status_code} - {error_msg}")
                    except Exception:
                        logger.error(f"Gramps Web token request failed: HTTP {response.status_code}")

        except Exception as e:
            logger.error(f"Error obtaining Gramps Web token: {e}")

        return None

    def _get_headers(self, token: Optional[str] = None) -> dict:
        """Get headers for API requests."""
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return headers

    async def check_connection(self) -> GrampsConnectionStatus:
        """
        Check connection to Gramps Web API.

        Returns:
            GrampsConnectionStatus with connection details
        """
        if not self.base_url:
            return GrampsConnectionStatus(
                connected=False,
                url="",
                error="GRAMPS_WEB_URL not configured",
            )

        if not self.username or not self.password:
            return GrampsConnectionStatus(
                connected=False,
                url=self.base_url,
                error="GRAMPS_USERNAME and GRAMPS_PASSWORD not configured",
            )

        # Get token first
        token = await self._get_token()
        if not token:
            return GrampsConnectionStatus(
                connected=False,
                url=self.base_url,
                error="Authentication failed - check GRAMPS_USERNAME and GRAMPS_PASSWORD",
            )

        try:
            async with httpx.AsyncClient(
                timeout=self.timeout,
                follow_redirects=True,
            ) as client:
                response = await client.get(
                    f"{self.base_url}/api/metadata/",
                    headers=self._get_headers(token),
                )

                if response.status_code == 200:
                    data = response.json()
                    return GrampsConnectionStatus(
                        connected=True,
                        url=self.base_url,
                        api_version=data.get("gramps_webapi", {}).get("version"),
                        tree_name=data.get("database", {}).get("name"),
                        database_id=data.get("database", {}).get("id"),
                        locale=data.get("locale"),
                    )
                elif response.status_code == 401:
                    # Token might be invalid, clear cache
                    self._token = None
                    return GrampsConnectionStatus(
                        connected=False,
                        url=self.base_url,
                        error="Authentication failed - token rejected",
                    )
                elif response.status_code == 403:
                    return GrampsConnectionStatus(
                        connected=False,
                        url=self.base_url,
                        error="Access forbidden - check user permissions",
                    )
                else:
                    return GrampsConnectionStatus(
                        connected=False,
                        url=self.base_url,
                        error=f"Unexpected response: HTTP {response.status_code}",
                    )

        except httpx.ConnectError as e:
            logger.error(f"Failed to connect to Gramps Web: {e}")
            return GrampsConnectionStatus(
                connected=False,
                url=self.base_url,
                error=f"Connection failed - is Gramps Web running at {self.base_url}?",
            )
        except httpx.TimeoutException:
            logger.error(f"Timeout connecting to Gramps Web at {self.base_url}")
            return GrampsConnectionStatus(
                connected=False,
                url=self.base_url,
                error=f"Connection timeout after {self.timeout}s",
            )
        except Exception as e:
            logger.error(f"Error checking Gramps Web connection: {e}")
            return GrampsConnectionStatus(
                connected=False,
                url=self.base_url,
                error=str(e),
            )

    async def get_people_count(self) -> Optional[int]:
        """
        Get count of people in the Gramps database.

        Returns:
            Number of people or None if request fails
        """
        if not self.base_url:
            return None

        token = await self._get_token()
        if not token:
            return None

        try:
            async with httpx.AsyncClient(
                timeout=self.timeout,
                follow_redirects=True,
            ) as client:
                response = await client.get(
                    f"{self.base_url}/api/people/?keys=handle&pagesize=1",
                    headers=self._get_headers(token),
                )
                if response.status_code == 200:
                    # Total count is usually in headers
                    total = response.headers.get("X-Total-Count")
                    if total:
                        return int(total)
                    # Fallback: count from response
                    data = response.json()
                    if isinstance(data, list):
                        return len(data)
        except Exception as e:
            logger.error(f"Error getting people count: {e}")

        return None


# Singleton instance for dependency injection
_connector: Optional[GrampsConnector] = None


def get_gramps_connector() -> GrampsConnector:
    """Get or create Gramps connector singleton."""
    global _connector
    if _connector is None:
        _connector = GrampsConnector()
    return _connector


def reset_gramps_connector() -> None:
    """Reset the connector singleton (useful for testing)."""
    global _connector
    _connector = None
