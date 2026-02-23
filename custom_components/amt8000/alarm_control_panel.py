"""Alarm control panel for AMT-8000."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.alarm_control_panel import (
    AlarmControlPanelEntity,
    AlarmControlPanelEntityFeature,
    AlarmControlPanelState,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_AWAY_PARTITIONS,
    CONF_HOST,
    CONF_NIGHT_PARTITIONS,
    CONF_NUM_PARTITIONS,
    CONF_PORT,
    CONF_STAY_PARTITIONS,
    DEFAULT_NUM_PARTITIONS,
    DEFAULT_PORT,
    DOMAIN,
)
from .coordinator import AMTCoordinator
from .isec2 import AlarmState

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the alarm control panel."""
    data = hass.data[DOMAIN][config_entry.entry_id]
    coordinator: AMTCoordinator = data["coordinator"]
    config = data["config"]

    away_partitions = config.get(CONF_AWAY_PARTITIONS, [0])
    stay_partitions = config.get(CONF_STAY_PARTITIONS, [])
    night_partitions = config.get(CONF_NIGHT_PARTITIONS, [])
    num_partitions = config.get(CONF_NUM_PARTITIONS, DEFAULT_NUM_PARTITIONS)

    entities: list[AlarmControlPanelEntity] = []

    # Main alarm panel
    entities.append(
        AMTAlarmPanel(
            coordinator=coordinator,
            config=config,
            away_partitions=away_partitions,
            stay_partitions=stay_partitions,
            night_partitions=night_partitions,
        )
    )

    # Individual partition panels
    if coordinator.data and coordinator.data.partitions:
        for partition in coordinator.data.partitions[:num_partitions]:
            if partition.enabled:
                entities.append(
                    AMTPartitionPanel(
                        coordinator=coordinator,
                        config=config,
                        partition_number=partition.number,
                    )
                )

    async_add_entities(entities)


class AMTAlarmPanel(CoordinatorEntity[AMTCoordinator], AlarmControlPanelEntity):
    """Main AMT-8000 alarm control panel."""

    _attr_has_entity_name = True
    _attr_code_arm_required = False

    def __init__(
        self,
        coordinator: AMTCoordinator,
        config: dict,
        away_partitions: list[int],
        stay_partitions: list[int],
        night_partitions: list[int],
    ) -> None:
        """Initialize the alarm panel."""
        super().__init__(coordinator)
        self._config = config
        self._away_partitions = away_partitions or [0]
        self._stay_partitions = stay_partitions
        self._night_partitions = night_partitions

        host = config.get(CONF_HOST, "unknown")
        port = config.get(CONF_PORT, DEFAULT_PORT)
        self._attr_unique_id = f"amt8000_{host}_{port}_alarm"
        self._attr_name = "Alarm"

        # Build supported features based on configured partitions
        features = AlarmControlPanelEntityFeature.ARM_AWAY | AlarmControlPanelEntityFeature.TRIGGER
        if self._stay_partitions:
            features |= AlarmControlPanelEntityFeature.ARM_HOME
        if self._night_partitions:
            features |= AlarmControlPanelEntityFeature.ARM_NIGHT
        self._attr_supported_features = features

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        host = self._config.get(CONF_HOST, "unknown")
        port = self._config.get(CONF_PORT, DEFAULT_PORT)
        model = "AMT-8000"
        version = ""
        if self.coordinator.data:
            model = self.coordinator.data.model or "AMT-8000"
            version = self.coordinator.data.version or ""

        return DeviceInfo(
            identifiers={(DOMAIN, f"{host}:{port}")},
            name="Intelbras AMT-8000",
            manufacturer="Intelbras",
            model=model,
            sw_version=version,
        )

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.last_update_success and self.coordinator.data is not None

    @property
    def alarm_state(self) -> AlarmControlPanelState | None:
        """Return the state of the alarm."""
        if self.coordinator.data is None:
            return None

        status = self.coordinator.data

        if status.siren:
            return AlarmControlPanelState.TRIGGERED

        if status.state == AlarmState.DISARMED:
            return AlarmControlPanelState.DISARMED

        if status.state == AlarmState.PARTIAL:
            # Determine which partial state we're in
            armed_parts = [
                p.number for p in status.partitions if p.armed
            ]

            if self._night_partitions and set(self._night_partitions) == set(armed_parts):
                return AlarmControlPanelState.ARMED_NIGHT
            if self._stay_partitions and set(self._stay_partitions) == set(armed_parts):
                return AlarmControlPanelState.ARMED_HOME
            if self._away_partitions and set(self._away_partitions) == set(armed_parts):
                return AlarmControlPanelState.ARMED_AWAY

            # Default: if some partitions are armed, call it partial/home
            return AlarmControlPanelState.ARMED_HOME

        if status.state == AlarmState.ARMED:
            return AlarmControlPanelState.ARMED_AWAY

        return AlarmControlPanelState.DISARMED

    async def async_alarm_disarm(self, code: str | None = None) -> None:
        """Send disarm command."""
        _LOGGER.info("Disarming AMT-8000")
        result = await self.coordinator.async_disarm_all()
        if result:
            await self.coordinator.async_request_refresh()

    async def async_alarm_arm_away(self, code: str | None = None) -> None:
        """Send arm away command."""
        _LOGGER.info("Arming AMT-8000 away: partitions %s", self._away_partitions)
        # Disarm first to handle transitions between armed states
        await self.coordinator.async_disarm_all()
        result = await self.coordinator.async_arm_partitions(self._away_partitions)
        if result:
            await self.coordinator.async_request_refresh()

    async def async_alarm_arm_home(self, code: str | None = None) -> None:
        """Send arm home/stay command."""
        if not self._stay_partitions:
            _LOGGER.warning("No stay partitions configured")
            return
        _LOGGER.info("Arming AMT-8000 stay: partitions %s", self._stay_partitions)
        await self.coordinator.async_disarm_all()
        result = await self.coordinator.async_arm_partitions(self._stay_partitions)
        if result:
            await self.coordinator.async_request_refresh()

    async def async_alarm_arm_night(self, code: str | None = None) -> None:
        """Send arm night command."""
        if not self._night_partitions:
            _LOGGER.warning("No night partitions configured")
            return
        _LOGGER.info("Arming AMT-8000 night: partitions %s", self._night_partitions)
        await self.coordinator.async_disarm_all()
        result = await self.coordinator.async_arm_partitions(self._night_partitions)
        if result:
            await self.coordinator.async_request_refresh()

    async def async_alarm_trigger(self, code: str | None = None) -> None:
        """Send alarm trigger (panic) command."""
        _LOGGER.warning("Triggering AMT-8000 panic alarm!")
        result = await self.coordinator.async_trigger_panic()
        if result:
            await self.coordinator.async_request_refresh()


class AMTPartitionPanel(CoordinatorEntity[AMTCoordinator], AlarmControlPanelEntity):
    """Individual partition alarm control panel."""

    _attr_has_entity_name = True
    _attr_code_arm_required = False

    def __init__(
        self,
        coordinator: AMTCoordinator,
        config: dict,
        partition_number: int,
    ) -> None:
        """Initialize the partition panel."""
        super().__init__(coordinator)
        self._config = config
        self._partition_number = partition_number

        host = config.get(CONF_HOST, "unknown")
        port = config.get(CONF_PORT, DEFAULT_PORT)
        self._attr_unique_id = f"amt8000_{host}_{port}_partition_{partition_number}"
        self._attr_name = f"Partition {partition_number}"
        self._attr_supported_features = (
            AlarmControlPanelEntityFeature.ARM_AWAY
            | AlarmControlPanelEntityFeature.ARM_HOME
        )

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
    def _partition(self):
        """Get the partition data."""
        if self.coordinator.data and self.coordinator.data.partitions:
            for p in self.coordinator.data.partitions:
                if p.number == self._partition_number:
                    return p
        return None

    @property
    def alarm_state(self) -> AlarmControlPanelState | None:
        """Return the state of this partition."""
        partition = self._partition
        if partition is None:
            return None

        if partition.firing:
            return AlarmControlPanelState.TRIGGERED

        if partition.armed:
            if partition.stay:
                return AlarmControlPanelState.ARMED_HOME
            return AlarmControlPanelState.ARMED_AWAY

        return AlarmControlPanelState.DISARMED

    async def async_alarm_disarm(self, code: str | None = None) -> None:
        """Disarm this partition."""
        _LOGGER.info("Disarming partition %d", self._partition_number)
        client = self.coordinator
        result = await client.async_disarm_all()
        if result:
            await client.async_request_refresh()

    async def async_alarm_arm_away(self, code: str | None = None) -> None:
        """Arm this partition in away mode."""
        _LOGGER.info("Arming partition %d away", self._partition_number)
        result = await self.coordinator.async_arm_partitions([self._partition_number])
        if result:
            await self.coordinator.async_request_refresh()

    async def async_alarm_arm_home(self, code: str | None = None) -> None:
        """Arm this partition in stay mode."""
        _LOGGER.info("Arming partition %d stay", self._partition_number)
        result = await self.coordinator.async_arm_stay_partitions([self._partition_number])
        if result:
            await self.coordinator.async_request_refresh()
