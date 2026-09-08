"""Small asynchronous client for the TravelLog REST API."""

import asyncio
from urllib.parse import urlsplit, urlunsplit

import aiohttp


class TravelLogError(Exception):
    """API request failed."""


class TravelLogAuthError(TravelLogError):
    """API key was rejected."""


class TravelLogWriteUncertain(TravelLogError):
    """A write may have reached the server. Never retry automatically."""


def normalize_url(value: str) -> str:
    """Preserve deployment subpaths, but reject credentials/query/fragment."""
    parts = urlsplit(value.strip())
    if (
        parts.scheme not in ("http", "https")
        or not parts.hostname
        or parts.username is not None
        or parts.password is not None
        or parts.query
        or parts.fragment
    ):
        raise ValueError("Enter the application URL without credentials or query")
    _ = parts.port  # Validate the port as well.
    path = parts.path.rstrip("/")
    if path.endswith("/api/v1"):
        path = path[:-7]
    return urlunsplit((parts.scheme, parts.netloc.lower(), path, "", ""))


class TravelLogClient:
    """Use Home Assistant's shared session and verified TLS."""

    def __init__(self, session, url: str, api_key: str):
        self.session = session
        self.url = normalize_url(url)
        self._api_key = api_key

    async def request(self, method: str, path: str, payload=None) -> dict:
        """Do not log credentials/bodies or follow redirects with API keys."""
        try:
            async with self.session.request(
                method,
                f"{self.url}/api/v1/{path}",
                headers={"X-API-Key": self._api_key},
                json=payload,
                timeout=aiohttp.ClientTimeout(total=30),
                allow_redirects=False,
            ) as response:
                if response.status in (401, 403):
                    raise TravelLogAuthError("TravelLog API key rejected")
                expected = 201 if method == "POST" else 200
                if response.status != expected:
                    if method == "POST" and response.status >= 500:
                        raise TravelLogWriteUncertain(
                            "Server error; check TravelLog before retrying"
                        )
                    raise TravelLogError(f"TravelLog returned HTTP {response.status}")
                data = await response.json()
                if not isinstance(data, dict):
                    raise ValueError("Expected a JSON object")
                if method == "POST" and (
                    not isinstance(data.get("id"), int)
                    or not isinstance(data.get("needs_review"), bool)
                ):
                    raise ValueError("Invalid write acknowledgement")
                return data
        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as err:
            if method == "POST":
                raise TravelLogWriteUncertain(
                    "No valid confirmation; check TravelLog before retrying"
                ) from err
            raise TravelLogError("Cannot read TravelLog API response") from err

    async def fetch(self) -> dict:
        """Read a consistent snapshot, validating collections before use."""
        maintenance = await self.request("GET", "maintenance")
        logbook = await self.request("GET", "logbook?limit=25")
        tasks = maintenance.get("tasks")
        entries = logbook.get("entries")
        if not isinstance(tasks, list) or not isinstance(entries, list):
            raise TravelLogError("Invalid maintenance or logbook response")
        for task in tasks:
            if (
                not isinstance(task, dict)
                or "id" not in task
                or not isinstance(task.get("state"), dict)
                or task["state"].get("key") not in ("never", "neutral", "overdue", "soon", "ok")
            ):
                raise TravelLogError("Invalid maintenance task")
        if any(not isinstance(entry, dict) for entry in entries):
            raise TravelLogError("Invalid logbook entry")
        return {"odometer_km": maintenance.get("odometer_km"), "tasks": tasks, "entries": entries}
