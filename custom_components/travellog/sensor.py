"""Dashboard sensors and dynamically discovered maintenance tasks."""

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.const import UnitOfLength
from homeassistant.core import callback

from .entity import TravelLogEntity


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = entry.runtime_data
    async_add_entities(
        [
            TravelLogSensor(coordinator, key, name)
            for key, name in (
                ("odometer", "Odometer"),
                ("maintenance", "Maintenance"),
                ("overdue", "Maintenance overdue"),
                ("soon", "Maintenance soon"),
                ("never", "Maintenance never recorded"),
                ("logbook", "Logbook"),
                ("write_status", "Write status"),
            )
        ]
    )
    known = set()

    @callback
    def add_tasks():
        entities = []
        for task in coordinator.data["tasks"]:
            task_id = str(task["id"])
            if task_id not in known:
                known.add(task_id)
                entities.append(TravelLogTask(coordinator, task_id, task.get("name", task_id)))
        async_add_entities(entities)

    add_tasks()
    entry.async_on_unload(coordinator.async_add_listener(add_tasks))


class TravelLogSensor(TravelLogEntity, SensorEntity):
    def __init__(self, coordinator, key, name):
        super().__init__(coordinator, key)
        self.key = key
        self._attr_name = name
        if key == "odometer":
            self._attr_device_class = SensorDeviceClass.DISTANCE
            self._attr_native_unit_of_measurement = UnitOfLength.KILOMETERS

    @property
    def available(self):
        return self.key == "write_status" or super().available

    @property
    def native_value(self):
        data = self.coordinator.data
        if self.key == "odometer":
            return data["odometer_km"]
        if self.key == "write_status":
            return self.coordinator.write_status
        if self.key == "logbook":
            return len(data["entries"])
        if self.key == "maintenance":
            return len(data["tasks"])
        return sum(t["state"]["key"] == self.key for t in data["tasks"])

    @property
    def extra_state_attributes(self):
        if self.key == "write_status":
            return {"last_result": self.coordinator.last_result}
        if self.key == "logbook":
            return {"entries": self.coordinator.data["entries"], "limit": 25}
        if self.key == "maintenance":
            return {"tasks": self.coordinator.data["tasks"]}
        return None


class TravelLogTask(TravelLogEntity, SensorEntity):
    """Use stable task IDs; removed or inactive tasks become unavailable."""

    _attr_icon = "mdi:wrench-clock"

    def __init__(self, coordinator, task_id, name):
        super().__init__(coordinator, f"task_{task_id}")
        self.task_id = task_id
        self._attr_name = name

    @property
    def task(self):
        return next(
            (t for t in self.coordinator.data["tasks"] if str(t["id"]) == self.task_id), None
        )

    @property
    def available(self):
        return super().available and self.task is not None

    @property
    def native_value(self):
        return self.task["state"]["key"] if self.task else None

    @property
    def extra_state_attributes(self):
        return self.task
