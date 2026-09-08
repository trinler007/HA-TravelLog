"""Exercise Home Assistant services, entities, flows and coordinator."""

import asyncio
import shutil
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytest.importorskip("homeassistant")

import voluptuous as vol
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from custom_components.travellog import SERVICE_SCHEMA
from custom_components.travellog.api import (
    TravelLogAuthError,
    TravelLogError,
    TravelLogWriteUncertain,
)
from custom_components.travellog.coordinator import TravelLogCoordinator

SNAPSHOT = {
    "odometer_km": "102607.0",
    "entries": [],
    "tasks": [
        {
            "id": "1",
            "name": "Oil",
            "state": {"key": "soon", "label": "Bald fällig"},
            "last_performed_on": "2025-01-31",
            "last_odometer_km": "95000",
            "interval_km": "10000",
            "interval_months": "12",
        }
    ],
}


@pytest.fixture
async def hass(tmp_path):
    hass = HomeAssistant(str(tmp_path))
    shutil.copytree(Path(__file__).parents[1] / "custom_components", tmp_path / "custom_components")
    yield hass
    await hass.async_stop(force=True)


@pytest.fixture
def coordinator(hass):
    client = SimpleNamespace(
        fetch=AsyncMock(return_value=deepcopy(SNAPSHOT)),
        request=AsyncMock(return_value={"id": 8, "needs_review": False}),
    )
    entry = SimpleNamespace(entry_id="test", async_start_reauth=MagicMock())
    coordinator = TravelLogCoordinator(hass, entry, client)
    coordinator.async_set_updated_data(deepcopy(SNAPSHOT))
    coordinator.async_request_refresh = AsyncMock()
    return coordinator


async def test_draft_never_posts_and_buttons_require_input(coordinator):
    with pytest.raises(HomeAssistantError, match="odometer"):
        await coordinator.async_write({"log_type": "day_end"})
    coordinator.set_odometer(102608)
    coordinator.client.request.assert_not_called()
    await coordinator.async_write({"log_type": "day_end"})
    coordinator.client.request.assert_awaited_once_with(
        "POST", "logbook", {"log_type": "day_end", "odometer_km": 102608}
    )
    assert coordinator.write_status == "saved"
    with pytest.raises(HomeAssistantError, match="Repeated"):
        await coordinator.async_write({"log_type": "day_end"})


async def test_write_in_flight_blocks_second_call(coordinator):
    started, finish = asyncio.Event(), asyncio.Event()

    async def post(*args):
        started.set()
        await finish.wait()
        return {"id": 1, "needs_review": False}

    coordinator.client.request.side_effect = post
    first = asyncio.create_task(coordinator.async_write({"log_type": "fuel", "odometer_km": 1}))
    await started.wait()
    with pytest.raises(HomeAssistantError, match="already"):
        await coordinator.async_write({"log_type": "day_end", "odometer_km": 2})
    finish.set()
    await first


@pytest.mark.parametrize(
    "exception,status",
    [
        (TravelLogWriteUncertain("uncertain"), "uncertain"),
        (TravelLogError("error"), "error"),
        (TravelLogAuthError("auth"), "error"),
    ],
)
async def test_write_failure_status(coordinator, exception, status):
    coordinator.client.request.side_effect = exception
    with pytest.raises(HomeAssistantError):
        await coordinator.async_write({"log_type": "fuel", "odometer_km": 1})
    assert coordinator.write_status == status
    coordinator.async_request_refresh.assert_not_called()


async def test_partial_fuel_returns_review_flag(coordinator):
    coordinator.client.request.return_value = {"id": 8, "needs_review": True}
    result = await coordinator.async_write({"log_type": "fuel", "odometer_km": 1})
    assert result["needs_review"] is True
    assert coordinator.write_status == "needs_review"


@pytest.mark.parametrize("value", [-1, float("nan"), float("inf"), True, "invalid"])
def test_service_rejects_invalid_numbers(value):
    with pytest.raises(vol.Invalid):
        SERVICE_SCHEMA({"log_type": "fuel", "odometer_km": value})


def test_service_validates_optional_fields():
    data = SERVICE_SCHEMA(
        {
            "log_type": "fuel",
            "odometer_km": "123.4",
            "occurred_on": "2026-09-08",
            "country_code": "de",
            "currency": "eur",
            "is_full_tank": False,
        }
    )
    assert data["occurred_on"] == "2026-09-08"
    assert data["country_code"] == "DE"
    assert data["is_full_tank"] is False
    for extra in ({"occurred_on": "2026-02-30"}, {"liters": -1}, {"unexpected": 1}):
        with pytest.raises(vol.Invalid):
            SERVICE_SCHEMA({"log_type": "fuel", "odometer_km": 1, **extra})


async def test_real_config_flow_setup_service_and_unload(hass):
    assert await async_setup_component(hass, "persistent_notification", {})
    with (
        patch(
            "custom_components.travellog.api.TravelLogClient.fetch",
            AsyncMock(return_value=deepcopy(SNAPSHOT)),
        ),
        patch(
            "custom_components.travellog.api.TravelLogClient.request",
            AsyncMock(return_value={"id": 9, "needs_review": True}),
        ) as request,
    ):
        result = await hass.config_entries.flow.async_init("travellog", context={"source": "user"})
        assert result["type"] is FlowResultType.FORM
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"url": "https://travel.example/", "api_key": "test"}
        )
        assert result["type"] is FlowResultType.CREATE_ENTRY
        await hass.async_block_till_done()
        entry = result["result"]
        registry = er.async_get(hass)

        def entity_id(domain, key):
            return registry.async_get_entity_id(domain, "travellog", f"{entry.entry_id}_{key}")

        assert hass.states.get(entity_id("sensor", "odometer")).state == "102607.0"
        assert hass.states.get(entity_id("sensor", "task_1")).state == "soon"
        assert hass.states.get(entity_id("number", "odometer_input")).state == "unknown"
        response = await hass.services.async_call(
            "travellog",
            "add_logbook_entry",
            {"log_type": "fuel", "odometer_km": 102608},
            blocking=True,
            return_response=True,
        )
        assert response == {"id": 9, "needs_review": True}
        request.assert_awaited_once()
        duplicate = await hass.config_entries.flow.async_init(
            "travellog",
            context={"source": "user"},
            data={"url": "https://travel.example", "api_key": "test"},
        )
        assert duplicate["reason"] == "already_configured"
        data = deepcopy(SNAPSHOT)
        data["tasks"] = [{"id": 2, "name": "Tires", "state": {"key": "never"}}]
        entry.runtime_data.async_set_updated_data(data)
        await hass.async_block_till_done()
        assert hass.states.get(entity_id("sensor", "task_1")).state == "unavailable"
        assert hass.states.get(entity_id("sensor", "task_2")).state == "never"
        assert await hass.config_entries.async_unload(entry.entry_id)
        with pytest.raises(HomeAssistantError):
            await hass.services.async_call(
                "travellog",
                "add_logbook_entry",
                {"log_type": "fuel", "odometer_km": 1},
                blocking=True,
            )


@pytest.mark.parametrize(
    "error,reason", [(TravelLogAuthError(), "invalid_auth"), (TravelLogError(), "cannot_connect")]
)
async def test_config_flow_errors(hass, error, reason):
    with patch(
        "custom_components.travellog.api.TravelLogClient.fetch", AsyncMock(side_effect=error)
    ):
        result = await hass.config_entries.flow.async_init(
            "travellog",
            context={"source": "user"},
            data={"url": "https://travel.example", "api_key": "test"},
        )
    assert result["errors"] == {"base": reason}
