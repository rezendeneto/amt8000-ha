"""Binary sensors for AMT-8000 zones."""

from __future__ import annotations

import logging

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_HOST,
    CONF_NUM_ZONES,
    CONF_PORT,
    DEFAULT_NUM_ZONES,
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
    """Set up binary sensors for zones."""
    data = hass.data[DOMAIN][config_entry.entry_id]
    coordinator: AMTCoordinator = data["coordinator"]
    config = data["config"]

    num_zones = config.get(CONF_NUM_ZONES, DEFAULT_NUM_ZONES)

    entities: list[BinarySensorEntity] = []

    if coordinator.data and coordinator.data.zones:
        for zone in coordinator.data.zones[:num_zones]:
            if zone.enabled:
                # Zone sensor (open/violated)
                entities.append(
                    AMTZoneSensor(
                        coordinator=coordinator,
                        config=config,
                        zone_number=zone.number,
                    )
                )
                # Zone tamper sensor
                entities.append(
                    AMTZoneTamperSensor(
                        coordinator=coordinator,
                        config=config,
                        zone_number=zone.number,
                    )
                )
                # Zone low battery sensor
                entities.append(
                    AMTZoneBatterySensor(
                        coordinator=coordinator,
                        config=config,
                        zone_number=zone.number,
                    )
                )

    # System-level sensors
    entities.append(
        AMTSirenSensor(coordinator=coordinator, config=config)
    )
    entities.append(
        AMTTamperSensor(coordinator=coordinator, config=config)
    )
    entities.append(
        AMTZonesFiringSensor(coordinator=coordinator, config=config)
    )

    async_add_entities(entities)


class AMTZoneSensor(CoordinatorEntity[AMTCoordinator], BinarySensorEntity):
    """Binary sensor for an alarm zone (open/violated)."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: AMTCoordinator,
        config: dict,
        zone_number: int,
    ) -> None:
        """Initialize the zone sensor."""
        super().__init__(coordinator)
        self._config = config
        self._zone_number = zone_number

        host = config.get(CONF_HOST, "unknown")
        port = config.get(CONF_PORT, DEFAULT_PORT)
        self._attr_unique_id = f"amt8000_{host}_{port}_zone_{zone_number}"
        self._attr_name = f"Zone {zone_number}"
        # Default to motion, can be overridden in HA customization
        self._attr_device_class = BinarySensorDeviceClass.MOTION

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        host = self._config.get(CONF_HOST, "unknown")
        port = self._config.get(CONF_PORT, DEFAULT_PORT)
        return DeviceInfo(
            identifiers={(DOMAIN, f"{host}:{port}")},
        )

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.last_update_success and self.coordinator.data is not None

    @property
    def is_on(self) -> bool | None:
        """Return true if the zone is open/violated."""
        if self.coordinator.data is None:
            return None
        for zone in self.coordinator.data.zones:
            if zone.number == self._zone_number:
                return zone.is_open
        return None

    @property
    def extra_state_attributes(self) -> dict:
        """Return extra attributes."""
        if self.coordinator.data is None:
            return {}
        for zone in self.coordinator.data.zones:
            if zone.number == self._zone_number:
                return {
                    "open": zone.open,
                    "violated": zone.violated,
                    "bypassed": zone.bypassed,
                    "tamper": zone.tamper,
                    "low_battery": zone.low_battery,
                    "enabled": zone.enabled,
                }
        return {}


class AMTZoneTamperSensor(CoordinatorEntity[AMTCoordinator], BinarySensorEntity):
    """Binary sensor for zone tamper status."""

    _attr_has_entity_name = True
    _attr_device_class = BinarySensorDeviceClass.TAMPER
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        coordinator: AMTCoordinator,
        config: dict,
        zone_number: int,
    ) -> None:
        """Initialize the zone tamper sensor."""
        super().__init__(coordinator)
        self._config = config
        self._zone_number = zone_number

        host = config.get(CONF_HOST, "unknown")
        port = config.get(CONF_PORT, DEFAULT_PORT)
        self._attr_unique_id = f"amt8000_{host}_{port}_zone_{zone_number}_tamper"
        self._attr_name = f"Zone {zone_number} Tamper"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        host = self._config.get(CONF_HOST, "unknown")
        port = self._config.get(CONF_PORT, DEFAULT_PORT)
        return DeviceInfo(identifiers={(DOMAIN, f"{host}:{port}")})

    @property
    def is_on(self) -> bool | None:
        """Return true if tampered."""
        if self.coordinator.data is None:
            return None
        for zone in self.coordinator.data.zones:
            if zone.number == self._zone_number:
                return zone.tamper
        return None


class AMTZoneBatterySensor(CoordinatorEntity[AMTCoordinator], BinarySensorEntity):
    """Binary sensor for zone low battery status."""

    _attr_has_entity_name = True
    _attr_device_class = BinarySensorDeviceClass.BATTERY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        coordinator: AMTCoordinator,
        config: dict,
        zone_number: int,
    ) -> None:
        """Initialize the zone battery sensor."""
        super().__init__(coordinator)
        self._config = config
        self._zone_number = zone_number

        host = config.get(CONF_HOST, "unknown")
        port = config.get(CONF_PORT, DEFAULT_PORT)
        self._attr_unique_id = f"amt8000_{host}_{port}_zone_{zone_number}_battery"
        self._attr_name = f"Zone {zone_number} Battery"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        host = self._config.get(CONF_HOST, "unknown")
        port = self._config.get(CONF_PORT, DEFAULT_PORT)
        return DeviceInfo(identifiers={(DOMAIN, f"{host}:{port}")})

    @property
    def is_on(self) -> bool | None:
        """Return true if battery is OK (False = low)."""
        if self.coordinator.data is None:
            return None
        for zone in self.coordinator.data.zones:
            if zone.number == self._zone_number:
                # BinarySensorDeviceClass.BATTERY: on = normal, off = low
                return not zone.low_battery
        return None


class AMTSirenSensor(CoordinatorEntity[AMTCoordinator], BinarySensorEntity):
    """Binary sensor for the siren status."""

    _attr_has_entity_name = True
    _attr_device_class = BinarySensorDeviceClass.SOUND

    def __init__(
        self,
        coordinator: AMTCoordinator,
        config: dict,
    ) -> None:
        """Initialize the siren sensor."""
        super().__init__(coordinator)
        self._config = config

        host = config.get(CONF_HOST, "unknown")
        port = config.get(CONF_PORT, DEFAULT_PORT)
        self._attr_unique_id = f"amt8000_{host}_{port}_siren"
        self._attr_name = "Siren"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        host = self._config.get(CONF_HOST, "unknown")
        port = self._config.get(CONF_PORT, DEFAULT_PORT)
        return DeviceInfo(identifiers={(DOMAIN, f"{host}:{port}")})

    @property
    def is_on(self) -> bool | None:
        """Return true if siren is active."""
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.siren


class AMTTamperSensor(CoordinatorEntity[AMTCoordinator], BinarySensorEntity):
    """Binary sensor for the system tamper status."""

    _attr_has_entity_name = True
    _attr_device_class = BinarySensorDeviceClass.TAMPER
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        coordinator: AMTCoordinator,
        config: dict,
    ) -> None:
        """Initialize the tamper sensor."""
        super().__init__(coordinator)
        self._config = config

        host = config.get(CONF_HOST, "unknown")
        port = config.get(CONF_PORT, DEFAULT_PORT)
        self._attr_unique_id = f"amt8000_{host}_{port}_tamper"
        self._attr_name = "System Tamper"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        host = self._config.get(CONF_HOST, "unknown")
        port = self._config.get(CONF_PORT, DEFAULT_PORT)
        return DeviceInfo(identifiers={(DOMAIN, f"{host}:{port}")})

    @property
    def is_on(self) -> bool | None:
        """Return true if system is tampered."""
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.tamper


class AMTZonesFiringSensor(CoordinatorEntity[AMTCoordinator], BinarySensorEntity):
    """Binary sensor for zones firing status."""

    _attr_has_entity_name = True
    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(
        self,
        coordinator: AMTCoordinator,
        config: dict,
    ) -> None:
        """Initialize the zones firing sensor."""
        super().__init__(coordinator)
        self._config = config

        host = config.get(CONF_HOST, "unknown")
        port = config.get(CONF_PORT, DEFAULT_PORT)
        self._attr_unique_id = f"amt8000_{host}_{port}_zones_firing"
        self._attr_name = "Zones Firing"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        host = self._config.get(CONF_HOST, "unknown")
        port = self._config.get(CONF_PORT, DEFAULT_PORT)
        return DeviceInfo(identifiers={(DOMAIN, f"{host}:{port}")})

    @property
    def is_on(self) -> bool | None:
        """Return true if zones are firing."""
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.zones_firing
