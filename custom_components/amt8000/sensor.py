"""Sensors for AMT-8000."""

from __future__ import annotations

import logging

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_HOST,
    CONF_PORT,
    DEFAULT_PORT,
    DOMAIN,
)
from .coordinator import AMTCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors."""
    data = hass.data[DOMAIN][config_entry.entry_id]
    coordinator: AMTCoordinator = data["coordinator"]
    config = data["config"]

    entities: list[SensorEntity] = [
        AMTBatteryLevelSensor(coordinator=coordinator, config=config),
        AMTBatteryStatusSensor(coordinator=coordinator, config=config),
        AMTModelSensor(coordinator=coordinator, config=config),
        AMTVersionSensor(coordinator=coordinator, config=config),
    ]

    async_add_entities(entities)


class AMTBatteryLevelSensor(CoordinatorEntity[AMTCoordinator], SensorEntity):
    """Sensor for alarm battery level."""

    _attr_has_entity_name = True
    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: AMTCoordinator, config: dict) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._config = config

        host = config.get(CONF_HOST, "unknown")
        port = config.get(CONF_PORT, DEFAULT_PORT)
        self._attr_unique_id = f"amt8000_{host}_{port}_battery_level"
        self._attr_name = "Battery Level"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        host = self._config.get(CONF_HOST, "unknown")
        port = self._config.get(CONF_PORT, DEFAULT_PORT)
        return DeviceInfo(identifiers={(DOMAIN, f"{host}:{port}")})

    @property
    def native_value(self) -> int | None:
        """Return the battery level as a percentage."""
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.battery.level


class AMTBatteryStatusSensor(CoordinatorEntity[AMTCoordinator], SensorEntity):
    """Sensor for alarm battery status text."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: AMTCoordinator, config: dict) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._config = config

        host = config.get(CONF_HOST, "unknown")
        port = config.get(CONF_PORT, DEFAULT_PORT)
        self._attr_unique_id = f"amt8000_{host}_{port}_battery_status"
        self._attr_name = "Battery Status"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        host = self._config.get(CONF_HOST, "unknown")
        port = self._config.get(CONF_PORT, DEFAULT_PORT)
        return DeviceInfo(identifiers={(DOMAIN, f"{host}:{port}")})

    @property
    def native_value(self) -> str | None:
        """Return the battery status."""
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.battery.name.lower()

    @property
    def icon(self) -> str:
        """Return the icon based on battery status."""
        if self.coordinator.data is None:
            return "mdi:battery-unknown"
        level = self.coordinator.data.battery.level
        if level <= 0:
            return "mdi:battery-alert"
        if level <= 25:
            return "mdi:battery-low"
        if level <= 50:
            return "mdi:battery-medium"
        return "mdi:battery-high"


class AMTModelSensor(CoordinatorEntity[AMTCoordinator], SensorEntity):
    """Sensor showing the alarm model."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: AMTCoordinator, config: dict) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._config = config

        host = config.get(CONF_HOST, "unknown")
        port = config.get(CONF_PORT, DEFAULT_PORT)
        self._attr_unique_id = f"amt8000_{host}_{port}_model"
        self._attr_name = "Model"
        self._attr_icon = "mdi:alarm-panel"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        host = self._config.get(CONF_HOST, "unknown")
        port = self._config.get(CONF_PORT, DEFAULT_PORT)
        return DeviceInfo(identifiers={(DOMAIN, f"{host}:{port}")})

    @property
    def native_value(self) -> str | None:
        """Return the model name."""
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.model


class AMTVersionSensor(CoordinatorEntity[AMTCoordinator], SensorEntity):
    """Sensor showing the firmware version."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: AMTCoordinator, config: dict) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._config = config

        host = config.get(CONF_HOST, "unknown")
        port = config.get(CONF_PORT, DEFAULT_PORT)
        self._attr_unique_id = f"amt8000_{host}_{port}_version"
        self._attr_name = "Firmware Version"
        self._attr_icon = "mdi:information-outline"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        host = self._config.get(CONF_HOST, "unknown")
        port = self._config.get(CONF_PORT, DEFAULT_PORT)
        return DeviceInfo(identifiers={(DOMAIN, f"{host}:{port}")})

    @property
    def native_value(self) -> str | None:
        """Return the firmware version."""
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.version
