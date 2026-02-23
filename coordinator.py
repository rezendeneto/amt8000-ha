"""Data coordinator for AMT-8000."""

from __future__ import annotations

import asyncio
import logging
from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .isec2 import AMTStatus, AsyncClient, CommunicationError

_LOGGER = logging.getLogger(__name__)

UPDATE_INTERVAL = timedelta(seconds=15)


class AMTCoordinator(DataUpdateCoordinator[AMTStatus]):
    """Coordinator to manage polling the AMT-8000 alarm system."""

    def __init__(
        self,
        hass: HomeAssistant,
        host: str,
        port: int,
        password: str,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="AMT-8000",
            update_interval=UPDATE_INTERVAL,
        )
        self.host = host
        self.port = port
        self.password = password
        self._consecutive_errors = 0

    async def _async_update_data(self) -> AMTStatus:
        """Fetch data from the alarm system."""
        client = AsyncClient(self.host, self.port)
        try:
            await client.connect()
            await client.auth(self.password)
            status = await client.status()
            self._consecutive_errors = 0
            _LOGGER.debug(
                "AMT-8000 status: state=%s, siren=%s, battery=%s",
                status.state.name,
                status.siren,
                status.battery.name,
            )
            return status
        except CommunicationError as err:
            self._consecutive_errors += 1
            _LOGGER.warning(
                "Communication error with AMT-8000 (attempt %d): %s",
                self._consecutive_errors,
                err,
            )
            raise UpdateFailed(f"Communication error: {err}") from err
        except Exception as err:
            self._consecutive_errors += 1
            _LOGGER.error(
                "Unexpected error communicating with AMT-8000: %s", err
            )
            raise UpdateFailed(f"Unexpected error: {err}") from err
        finally:
            try:
                await client.disconnect()
            except Exception:  # noqa: BLE001
                pass

    async def async_arm_partitions(self, partitions: list[int]) -> bool:
        """Arm specified partitions."""
        client = AsyncClient(self.host, self.port)
        try:
            await client.connect()
            await client.auth(self.password)
            for partition in partitions:
                result = await client.arm(partition)
                if not result:
                    _LOGGER.warning("Failed to arm partition %d", partition)
                    return False
            return True
        except Exception as err:
            _LOGGER.error("Error arming partitions: %s", err)
            return False
        finally:
            try:
                await client.disconnect()
            except Exception:  # noqa: BLE001
                pass

    async def async_arm_stay_partitions(self, partitions: list[int]) -> bool:
        """Arm specified partitions in stay mode."""
        client = AsyncClient(self.host, self.port)
        try:
            await client.connect()
            await client.auth(self.password)
            for partition in partitions:
                result = await client.arm_stay(partition)
                if not result:
                    _LOGGER.warning("Failed to arm stay partition %d", partition)
                    return False
            return True
        except Exception as err:
            _LOGGER.error("Error arming stay partitions: %s", err)
            return False
        finally:
            try:
                await client.disconnect()
            except Exception:  # noqa: BLE001
                pass

    async def async_disarm_all(self) -> bool:
        """Disarm all partitions."""
        client = AsyncClient(self.host, self.port)
        try:
            await client.connect()
            await client.auth(self.password)
            return await client.disarm(0)
        except Exception as err:
            _LOGGER.error("Error disarming: %s", err)
            return False
        finally:
            try:
                await client.disconnect()
            except Exception:  # noqa: BLE001
                pass

    async def async_trigger_panic(self) -> bool:
        """Trigger panic alarm."""
        client = AsyncClient(self.host, self.port)
        try:
            await client.connect()
            await client.auth(self.password)
            return await client.panic(1)
        except Exception as err:
            _LOGGER.error("Error triggering panic: %s", err)
            return False
        finally:
            try:
                await client.disconnect()
            except Exception:  # noqa: BLE001
                pass

    async def async_turn_off_siren(self) -> bool:
        """Turn off the siren."""
        client = AsyncClient(self.host, self.port)
        try:
            await client.connect()
            await client.auth(self.password)
            return await client.turn_off_siren()
        except Exception as err:
            _LOGGER.error("Error turning off siren: %s", err)
            return False
        finally:
            try:
                await client.disconnect()
            except Exception:  # noqa: BLE001
                pass

    async def async_clean_firings(self) -> bool:
        """Clean zone firings."""
        client = AsyncClient(self.host, self.port)
        try:
            await client.connect()
            await client.auth(self.password)
            return await client.clean_firings()
        except Exception as err:
            _LOGGER.error("Error cleaning firings: %s", err)
            return False
        finally:
            try:
                await client.disconnect()
            except Exception:  # noqa: BLE001
                pass

    async def async_bypass_zone(self, zone: int, bypass: bool = True) -> bool:
        """Bypass or un-bypass a zone."""
        client = AsyncClient(self.host, self.port)
        try:
            await client.connect()
            await client.auth(self.password)
            return await client.bypass_zone(zone, bypass)
        except Exception as err:
            _LOGGER.error("Error bypassing zone %d: %s", zone, err)
            return False
        finally:
            try:
                await client.disconnect()
            except Exception:  # noqa: BLE001
                pass
