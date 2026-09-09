"""Exercise Home Assistant services, entities, flows and coordinator."""

import asyncio
import shutil
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest
import yaml

pytest.importorskip("homeassistant")

import voluptuous as vol
from homeassistant import config_entries, loader
from homeassistant.bootstrap import async_load_base_functionality
from homeassistant.core import HomeAssistant, SupportsResponse
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
    loader.async_setup(hass)
    hass.config_entries = config_entries.ConfigEntries(hass, {})
    await async_load_base_functionality(hass)
    # HTTP behavior is covered separately against a real server. Use a plain
    # session here so flow tests do not require HA's unrelated mDNS discovery.
    async with aiohttp.ClientSession() as session:
        with (
            patch("custom_components.travellog.async_get_clientsession", return_value=session),
            patch(
                "custom_components.travellog.config_flow.async_get_clientsession",
                return_value=session,
            ),
        ):
            yield hass
    await hass.async_stop(force=True)


@pytest.fixture
def coordinator(hass):
    client = SimpleNamespace(
        fetch=AsyncMock(return_value=deepcopy(SNAPSHOT)),
        request=AsyncMock(return_value={"id": 8, "needs_review": False}),
    )
    entry = SimpleNamespace(entry_id="test", options={}, async_start_reauth=MagicMock())
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


async def test_reauthentication_updates_key(hass):
    with patch(
        "custom_components.travellog.api.TravelLogClient.fetch",
        AsyncMock(return_value=deepcopy(SNAPSHOT)),
    ):
        result = await hass.config_entries.flow.async_init(
            "travellog",
            context={"source": "user"},
            data={"url": "https://travel.example", "api_key": "old"},
        )
        await hass.async_block_till_done()
        entry = result["result"]
        reauth = await hass.config_entries.flow.async_init(
            "travellog",
            context={"source": "reauth", "entry_id": entry.entry_id},
            data=entry.data,
        )
        assert reauth["step_id"] == "reauth_confirm"
        reauth = await hass.config_entries.flow.async_configure(
            reauth["flow_id"], {"api_key": "new"}
        )
        assert reauth["reason"] == "reauth_successful"
        assert entry.data["api_key"] == "new"
        await hass.async_block_till_done()


async def test_day_end_uses_location_and_ignores_fuel(coordinator, hass):
    hass.states.async_set("sensor.nx_01_position_gps_location", "Kempten, Deutschland")
    coordinator.set_odometer(123456.7)
    coordinator.set_fuel_input("liters", 120)
    await coordinator.async_quick_entry("day_end")
    coordinator.client.request.assert_awaited_once_with(
        "POST",
        "logbook",
        {"log_type": "day_end", "odometer_km": 123456.7, "vendor": "Kempten, Deutschland"},
    )
    assert coordinator.fuel_inputs["liters"] == 120


@pytest.mark.parametrize("location", [None, "unknown", "unavailable", "   ", "x" * 181])
async def test_invalid_location_does_not_write(coordinator, hass, location):
    coordinator.set_odometer(100)
    if location is not None:
        hass.states.async_set("sensor.nx_01_position_gps_location", location)
    with pytest.raises(HomeAssistantError):
        await coordinator.async_quick_entry("day_end")
    coordinator.client.request.assert_not_called()


async def test_cleared_location_option_uses_server_lookup(coordinator):
    coordinator.entry.options = {"location_entity": ""}
    coordinator.set_odometer(100)
    await coordinator.async_quick_entry("day_end")
    assert coordinator.client.request.call_args.args[2] == {
        "log_type": "day_end",
        "odometer_km": 100,
    }


async def test_fuel_omits_unset_values_and_clears_confirmed_draft(coordinator):
    coordinator.set_odometer(100)
    coordinator.set_fuel_input("liters", 123.45)
    coordinator.set_fuel_input("amount", 0)
    coordinator.set_full_tank(True)
    coordinator.client.request.return_value = {"id": 8, "needs_review": True}
    await coordinator.async_quick_entry("fuel")
    assert coordinator.client.request.call_args.args[2] == {
        "log_type": "fuel",
        "odometer_km": 100,
        "liters": 123.45,
        "amount": 0,
        "is_full_tank": True,
    }
    assert all(v is None for v in coordinator.fuel_inputs.values())
    assert coordinator.full_tank is False
    assert coordinator.odometer_input == 100
    with pytest.raises(HomeAssistantError, match="Repeated"):
        await coordinator.async_quick_entry("fuel")
    coordinator.client.request.assert_awaited_once()


async def test_fuel_failure_preserves_draft(coordinator):
    coordinator.set_odometer(100)
    coordinator.set_fuel_input("liters", 20)
    coordinator.set_fuel_input("price_per_liter", 1.789)
    coordinator.set_full_tank(True)
    coordinator.client.request.side_effect = TravelLogWriteUncertain("Check logbook")
    with pytest.raises(HomeAssistantError):
        await coordinator.async_quick_entry("fuel")
    assert coordinator.fuel_inputs["liters"] == 20
    assert coordinator.fuel_inputs["price_per_liter"] == 1.789
    assert coordinator.full_tank is True
    coordinator.reset_fuel()
    assert all(v is None for v in coordinator.fuel_inputs.values())
    assert coordinator.full_tank is False


async def test_buttons_and_options_through_home_assistant(hass):
    with (
        patch(
            "custom_components.travellog.api.TravelLogClient.fetch",
            AsyncMock(return_value=deepcopy(SNAPSHOT)),
        ),
        patch(
            "custom_components.travellog.api.TravelLogClient.request",
            AsyncMock(return_value={"id": 9, "needs_review": False}),
        ) as request,
    ):
        result = await hass.config_entries.flow.async_init(
            "travellog",
            context={"source": "user"},
            data={"url": "https://travel.example", "api_key": "test"},
        )
        await hass.async_block_till_done()
        entry = result["result"]
        registry = er.async_get(hass)

        async def call(domain, service, key, **data):
            entity_id = registry.async_get_entity_id(domain, "travellog", f"{entry.entry_id}_{key}")
            assert entity_id is not None
            await hass.services.async_call(
                domain, service, {"entity_id": entity_id, **data}, blocking=True
            )

        options = await hass.config_entries.options.async_init(entry.entry_id)
        assert options["type"] is FlowResultType.FORM
        await hass.config_entries.options.async_configure(
            options["flow_id"], {"location_entity": "sensor.destination"}
        )
        hass.states.async_set("sensor.destination", "Bozen")
        await call("number", "set_value", "odometer_input", value=123456)
        await call("button", "press", "day_end")
        assert request.call_args.args[2]["vendor"] == "Bozen"
        await call("number", "set_value", "fuel_liters", value=100)
        await call("number", "set_value", "fuel_price_per_liter", value=1.789)
        await call("number", "set_value", "fuel_amount", value=178.9)
        await call("switch", "turn_on", "fuel_full_tank")
        await call("button", "press", "fuel")
        assert request.call_args.args[2] == {
            "log_type": "fuel",
            "odometer_km": 123456,
            "liters": 100,
            "price_per_liter": 1.789,
            "amount": 178.9,
            "is_full_tank": True,
        }
        assert entry.runtime_data.full_tank is False
        assert all(v is None for v in entry.runtime_data.fuel_inputs.values())
        await call("number", "set_value", "fuel_liters", value=50)
        await call("switch", "turn_on", "fuel_full_tank")
        await call("button", "press", "reset_fuel_inputs")
        assert entry.runtime_data.fuel_inputs["liters"] is None
        assert entry.runtime_data.full_tank is False
        assert request.await_count == 2


async def setup_display_package(hass, fail=False):
    """Run the actual supplied YAML with HA helpers and mocked external services."""
    package = yaml.safe_load(
        (Path(__file__).parents[1] / "examples/openhasp/480x480/package.yaml").read_text()
    )
    posts, pages = [], []

    async def change_page(call):
        pages.append(call.data["page"])

    async def write(call):
        posts.append(dict(call.data))
        if fail:
            raise HomeAssistantError("Uncertain write")
        return {"id": 123, "needs_review": call.data["log_type"] == "fuel"}

    hass.services.async_register("openhasp", "change_page", change_page)
    hass.services.async_register(
        "travellog", "add_logbook_entry", write, supports_response=SupportsResponse.OPTIONAL
    )
    for domain in ("input_text", "input_select", "input_boolean", "script"):
        assert await async_setup_component(hass, domain, {domain: package[domain]})
    await hass.async_block_till_done()

    async def operate(operation, **kwargs):
        await hass.services.async_call(
            "script", "travellog_480_action", {"operation": operation, **kwargs}, blocking=True
        )

    async def enter(field, value):
        await operate("edit_" + field)
        await operate("key", key="C")
        for digit in value:
            await operate("key", key=digit)
        await operate("accept")

    return posts, pages, operate, enter


async def test_display_decimal_fuel_and_double_tap(hass):
    posts, pages, operate, enter = await setup_display_package(hass)
    await enter("km_fuel", "102607")
    await enter("liters", "123.40")
    assert hass.states.get("input_text.travellog_480_liters").state == "|123.40"
    await enter("price", "1.789")
    await operate("full", checked=1)
    await operate("fuel")
    assert posts == [
        {
            "log_type": "fuel",
            "odometer_km": 102607,
            "liters": 123.4,
            "price_per_liter": 1.789,
            "is_full_tank": True,
        }
    ]
    assert hass.states.get("input_text.travellog_480_km").state == "|"
    assert hass.states.get("input_text.travellog_480_liters").state == "|"
    assert hass.states.get("input_boolean.travellog_480_full").state == "off"
    assert "WebApp ergaenzen" in hass.states.get("input_text.travellog_480_feedback").state
    assert pages[-1] == 6
    await operate("fuel")
    assert len(posts) == 1


async def test_display_day_end_location_and_cancel(hass):
    posts, pages, operate, enter = await setup_display_package(hass)
    await enter("km_day", "100.5")
    await operate("edit_km_day")
    await operate("key", key="C")
    await operate("key", key="9")
    await operate("cancel")
    assert hass.states.get("input_text.travellog_480_km").state == "|100.5"
    assert pages[-1] == 6
    await operate("day_end")
    assert posts == []
    hass.states.async_set("sensor.nx_01_position_gps_location", "Bozen")
    await operate("day_end")
    assert posts == [{"log_type": "day_end", "odometer_km": 100.5, "vendor": "Bozen"}]


async def test_display_rejects_invalid_precision_and_preserves_zero(hass):
    posts, _, operate, enter = await setup_display_package(hass)
    await enter("km_fuel", "100")
    await enter("price", "1.2345")
    assert hass.states.get("input_text.travellog_480_price").state == "|"
    assert "Ungueltig" in hass.states.get("input_text.travellog_480_feedback").state
    await enter("amount", "0")
    await operate("fuel")
    assert posts == [{"log_type": "fuel", "odometer_km": 100, "amount": 0, "is_full_tank": False}]


async def test_display_uncertain_write_cannot_be_retried_by_queued_tap(hass):
    posts, _, operate, enter = await setup_display_package(hass, fail=True)
    await enter("km_fuel", "100")
    await enter("liters", "25.50")
    await operate("fuel")
    assert len(posts) == 1
    assert hass.states.get("input_text.travellog_480_km").state == "|100"
    assert hass.states.get("input_text.travellog_480_liters").state == "|25.50"
    assert "WebApp pruefen" in hass.states.get("input_text.travellog_480_feedback").state
    await operate("fuel")
    assert len(posts) == 1
    # Explicit KM confirmation is needed to arm a new attempt after checking the web app.
    await operate("edit_km_fuel")
    await operate("accept")
    await operate("fuel")
    assert len(posts) == 2
