"""Exercise the HTTP client against a real local aiohttp server."""

import asyncio
import importlib.util
from pathlib import Path
from unittest.mock import patch

import aiohttp
import pytest
from aiohttp import web

spec = importlib.util.spec_from_file_location(
    "travellog_api", Path(__file__).parents[1] / "custom_components/travellog/api.py"
)
api = importlib.util.module_from_spec(spec)
spec.loader.exec_module(api)


@pytest.fixture
async def server():
    responses, requests = [], []

    async def handle(request):
        requests.append(
            {
                "method": request.method,
                "path": request.path_qs,
                "headers": dict(request.headers),
                "body": await request.json() if request.method == "POST" else None,
            }
        )
        return responses.pop(0)

    app = web.Application()
    app.router.add_route("*", "/{path:.*}", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    port = runner.addresses[0][1]
    async with aiohttp.ClientSession() as session:
        yield (
            api.TravelLogClient(session, f"http://127.0.0.1:{port}/sub", "secret"),
            responses,
            requests,
        )
    await runner.cleanup()


@pytest.mark.parametrize(
    "url", ["https://travel.example/sub/", "https://travel.example/sub/api/v1/"]
)
def test_normalize_url(url):
    assert api.normalize_url(url) == "https://travel.example/sub"


@pytest.mark.parametrize(
    "url",
    [
        "ftp://host",
        "https://user:secret@host",
        "https://host/?token=secret",
        "https://host/#fragment",
        "http://host:invalid",
        "host",
    ],
)
def test_reject_invalid_url(url):
    with pytest.raises(ValueError):
        api.normalize_url(url)


async def test_fetch_actual_contract(server):
    client, responses, requests = server
    responses.extend(
        [
            web.json_response(
                {
                    "odometer_km": "102607.0",
                    "tasks": [
                        {"id": "1", "name": "Oil", "state": {"key": "soon", "label": "Bald fällig"}}
                    ],
                }
            ),
            web.json_response({"entries": []}),
        ]
    )
    result = await client.fetch()
    assert result["odometer_km"] == "102607.0"
    assert result["tasks"][0]["state"]["key"] == "soon"
    assert result["entries"] == []
    assert [r["path"] for r in requests] == [
        "/sub/api/v1/maintenance",
        "/sub/api/v1/logbook?limit=25",
    ]


async def test_post_preserves_payload_and_credentials_header(server):
    client, responses, requests = server
    payload = {"log_type": "fuel", "odometer_km": 102607, "is_full_tank": False}
    responses.append(web.json_response({"id": 3, "needs_review": True}, status=201))
    result = await client.request("POST", "logbook", payload)
    assert requests[0]["body"] == payload
    assert requests[0]["headers"]["X-API-Key"] == "secret"
    assert "Authorization" not in requests[0]["headers"]
    assert result == {"id": 3, "needs_review": True}


@pytest.mark.parametrize(
    "status,error",
    [
        (401, api.TravelLogAuthError),
        (403, api.TravelLogAuthError),
        (422, api.TravelLogError),
        (302, api.TravelLogError),
        (500, api.TravelLogWriteUncertain),
    ],
)
async def test_post_http_errors(server, status, error):
    client, responses, requests = server
    responses.append(web.Response(status=status, headers={"Location": "/redirect"}))
    with pytest.raises(error):
        await client.request("POST", "logbook", {})
    assert len(requests) == 1


@pytest.mark.parametrize(
    "body", ["<html>Error</html>", "[]", '{"id":3}', '{"id":3,"needs_review":"false"}']
)
async def test_bad_write_acknowledgement_is_uncertain(server, body):
    client, responses, requests = server
    responses.append(web.Response(status=201, text=body, content_type="application/json"))
    with pytest.raises(api.TravelLogWriteUncertain):
        await client.request("POST", "logbook", {})
    assert len(requests) == 1


async def test_timeout_never_retries(server):
    client, _, _ = server
    with patch.object(client.session, "request", side_effect=asyncio.TimeoutError()) as request:
        with pytest.raises(api.TravelLogWriteUncertain):
            await client.request("POST", "logbook", {})
        request.assert_called_once()


async def test_invalid_collection_rejected(server):
    client, responses, _ = server
    responses.extend([web.json_response({"tasks": {}}), web.json_response({"entries": []})])
    with pytest.raises(api.TravelLogError):
        await client.fetch()
