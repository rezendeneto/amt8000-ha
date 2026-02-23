"""Module for AMT-8000 iSec2 protocol communication."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from enum import IntEnum

_LOGGER = logging.getLogger(__name__)

# Protocol constants
DST_ID = 0x0000
SRC_ID = 0x8FE0
DEVICE_TYPE = 0x00
SOFTWARE_VERSION = 0x10

TIMEOUT = 5.0


class Command(IntEnum):
    """iSec2 protocol commands."""

    AUTH = 0xF0F0
    DISCONNECT = 0xF0F1
    STATUS = 0x0B4A
    PANIC = 0x401A
    ARM_DISARM = 0x401E
    TURN_OFF_SIREN = 0x4019
    CLEAN_FIRING = 0x4013
    BYPASS = 0x401F


class AlarmState(IntEnum):
    """Alarm global states."""

    DISARMED = 0x00
    PARTIAL = 0x01
    ARMED = 0x03


class BatteryStatus(IntEnum):
    """Battery status values."""

    UNKNOWN = 0x00
    DEAD = 0x01
    LOW = 0x02
    MIDDLE = 0x03
    FULL = 0x04

    @property
    def level(self) -> int:
        """Return a percentage level."""
        mapping = {0: 0, 1: 0, 2: 25, 3: 50, 4: 100}
        return mapping.get(self.value, 0)

    @property
    def is_low(self) -> bool:
        """Return True if battery is low or worse."""
        return self.value <= 2


@dataclass
class Zone:
    """Represents a zone (sensor) on the alarm."""

    number: int
    enabled: bool = False
    open: bool = False
    violated: bool = False
    bypassed: bool = False
    tamper: bool = False
    low_battery: bool = False

    @property
    def is_open(self) -> bool:
        """Return True if the zone is currently open or violated."""
        return self.open or self.violated


@dataclass
class Partition:
    """Represents a partition on the alarm."""

    number: int
    enabled: bool = False
    armed: bool = False
    firing: bool = False
    fired: bool = False
    stay: bool = False


@dataclass
class SirenInfo:
    """Represents a siren status."""

    number: int
    tamper: bool = False
    low_battery: bool = False


@dataclass
class RepeaterInfo:
    """Represents a repeater status."""

    number: int
    tamper: bool = False
    low_battery: bool = False


@dataclass
class AMTStatus:
    """Complete status of the AMT-8000 alarm system."""

    model: str = "Unknown"
    version: str = "0.0.0"
    state: AlarmState = AlarmState.DISARMED
    zones_firing: bool = False
    zones_closed: bool = False
    siren: bool = False
    tamper: bool = False
    battery: BatteryStatus = BatteryStatus.UNKNOWN
    partitions: list[Partition] = field(default_factory=list)
    zones: list[Zone] = field(default_factory=list)
    sirens: list[SirenInfo] = field(default_factory=list)
    repeaters: list[RepeaterInfo] = field(default_factory=list)


class CommunicationError(Exception):
    """Exception raised for communication errors."""


class AuthError(Exception):
    """Exception raised for authentication errors."""


def _split_into_octets(n: int) -> bytes:
    """Split an integer into two bytes (big-endian)."""
    return bytes([n >> 8 & 0xFF, n & 0xFF])


def _merge_octets(buf: bytes | bytearray) -> int:
    """Merge two bytes into an integer."""
    return buf[0] * 256 + buf[1]


def _checksum(buf: bytes | bytearray) -> int:
    """Calculate XOR checksum for the buffer."""
    check = 0
    for b in buf:
        check ^= b
    check ^= 0xFF
    check &= 0xFF
    return check


def _contact_id_encode(password: str) -> list[int]:
    """Encode the password using ContactID encoding."""
    buf = []
    for char in password:
        digit = int(char) % 10
        if digit == 0:
            digit = 0x0A
        buf.append(digit)

    # Pad 4-digit passwords to 6 digits
    if len(password) == 4:
        buf = [0x0A, 0x0A] + buf

    return buf


def _make_payload(cmd: int, data: bytes | list[int] | None = None) -> bytes:
    """Build a protocol payload."""
    if data is None:
        data = []
    if isinstance(data, bytes):
        data = list(data)

    dst_id = list(_split_into_octets(DST_ID))
    src_id = list(_split_into_octets(SRC_ID))
    length = list(_split_into_octets(len(data) + 2))
    cmd_bytes = list(_split_into_octets(cmd))

    payload = dst_id + src_id + length + cmd_bytes + data
    cs = _checksum(payload)
    return bytes(payload + [cs])


def _make_auth_payload(password: str) -> bytes:
    """Build an authentication payload."""
    contact_id = _contact_id_encode(password)
    data = [DEVICE_TYPE] + contact_id + [SOFTWARE_VERSION]
    return _make_payload(Command.AUTH, data)


def _parse_response(buf: bytearray) -> tuple[int, bytearray]:
    """Parse a protocol response into (command, payload)."""
    if len(buf) < 8:
        return 0, bytearray()

    len_payload = _merge_octets(buf[4:6]) - 2
    cmd = _merge_octets(buf[6:8])

    if len_payload < 0 or len(buf) < 8 + len_payload:
        return cmd, bytearray()

    payload = buf[8: 8 + len_payload]
    return cmd, payload


def _parse_status(payload: bytearray) -> AMTStatus:
    """Parse the status response payload into an AMTStatus object.

    Based on the Go implementation in caarlos0/homekit-amt8000.
    The payload is expected to be 143 bytes (the data after the 8-byte header).
    """
    if len(payload) < 135:
        _LOGGER.warning(
            "Status payload too short: %d bytes (expected >= 135)", len(payload)
        )
        return AMTStatus()

    # Model
    model = "AMT-8000" if payload[0] == 1 else "Unknown"
    version = f"{payload[1]}.{payload[2]}.{payload[3]}"

    # Global state flags from byte 20
    state_byte = payload[20]
    state_val = (state_byte >> 5) & 0x03
    try:
        state = AlarmState(state_val)
    except ValueError:
        state = AlarmState.DISARMED

    zones_firing = (state_byte & 0x08) > 0
    zones_closed = (state_byte & 0x04) > 0
    siren = (state_byte & 0x02) > 0

    # Partitions (16 partitions, bytes 21-36)
    partitions = []
    for i in range(16):
        if 21 + i < len(payload):
            octet = payload[21 + i]
            partitions.append(
                Partition(
                    number=i + 1,
                    enabled=(octet & 0x80) > 0,
                    armed=(octet & 0x01) > 0,
                    firing=(octet & 0x04) > 0,
                    fired=(octet & 0x08) > 0,
                    stay=(octet & 0x40) > 0,
                )
            )
        else:
            partitions.append(Partition(number=i + 1))

    # Zones (up to 64 zones)
    zones = [Zone(number=i + 1) for i in range(64)]

    # Zone enabled flags: bytes 12-18 (7 bytes, 56 bits)
    for i in range(min(7, len(payload) - 12)):
        octet = payload[12 + i]
        for j in range(8):
            idx = j + i * 8
            if idx < 64:
                zones[idx].enabled = (octet & (1 << j)) > 0

    # Zone open flags: bytes 38-44 (7 bytes)
    for i in range(min(7, max(0, len(payload) - 38))):
        octet = payload[38 + i]
        for j in range(8):
            idx = j + i * 8
            if idx < 64:
                zones[idx].open = (octet & (1 << j)) > 0

    # Zone violated flags: bytes 46-52 (7 bytes)
    for i in range(min(7, max(0, len(payload) - 46))):
        octet = payload[46 + i]
        for j in range(8):
            idx = j + i * 8
            if idx < 64:
                zones[idx].violated = (octet & (1 << j)) > 0

    # Zone bypassed (anulated) flags: bytes 54-61 (8 bytes)
    for i in range(min(8, max(0, len(payload) - 54))):
        octet = payload[54 + i]
        for j in range(8):
            idx = j + i * 8
            if idx < 64:
                zones[idx].bypassed = (octet & (1 << j)) > 0

    # Zone tamper flags: bytes 89-95 (7 bytes)
    for i in range(min(7, max(0, len(payload) - 89))):
        octet = payload[89 + i]
        for j in range(8):
            idx = j + i * 8
            if idx < 64:
                zones[idx].tamper = (octet & (1 << j)) > 0

    # Zone low battery flags: bytes 105-111 (7 bytes)
    for i in range(min(7, max(0, len(payload) - 105))):
        octet = payload[105 + i]
        for j in range(8):
            idx = j + i * 8
            if idx < 64:
                zones[idx].low_battery = (octet & (1 << j)) > 0

    # Sirens
    sirens = []
    for i in range(2):
        siren_info = SirenInfo(number=i + 1)
        if 99 + i < len(payload):
            siren_info.tamper = (payload[99 + i] & 0x01) > 0
        if 115 + i < len(payload):
            siren_info.low_battery = (payload[115 + i] & 0x01) > 0
        sirens.append(siren_info)

    # Repeaters
    repeaters = []
    for i in range(2):
        rep = RepeaterInfo(number=i + 1)
        if 101 + i < len(payload):
            rep.tamper = (payload[101 + i] & 0x01) > 0
        if 117 + i < len(payload):
            rep.low_battery = (payload[117 + i] & 0x01) > 0
        repeaters.append(rep)

    # Battery
    battery_val = payload[134] if len(payload) > 134 else 0
    try:
        battery = BatteryStatus(battery_val)
    except ValueError:
        battery = BatteryStatus.UNKNOWN

    # Tamper
    tamper = (payload[71] & (1 << 0x01)) > 0 if len(payload) > 71 else False

    return AMTStatus(
        model=model,
        version=version,
        state=state,
        zones_firing=zones_firing,
        zones_closed=zones_closed,
        siren=siren,
        tamper=tamper,
        battery=battery,
        partitions=partitions,
        zones=zones,
        sirens=sirens,
        repeaters=repeaters,
    )


class AsyncClient:
    """Async client to communicate with AMT-8000 via iSec2 protocol."""

    def __init__(self, host: str, port: int) -> None:
        """Initialize the client."""
        self.host = host
        self.port = port
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._lock = asyncio.Lock()

    async def connect(self) -> None:
        """Create a new TCP connection."""
        try:
            self._reader, self._writer = await asyncio.wait_for(
                asyncio.open_connection(self.host, self.port),
                timeout=TIMEOUT,
            )
        except (asyncio.TimeoutError, OSError) as err:
            raise CommunicationError(f"Cannot connect to {self.host}:{self.port}: {err}") from err

    async def close(self) -> None:
        """Close the connection."""
        if self._writer is not None:
            try:
                self._writer.close()
                await self._writer.wait_closed()
            except Exception:  # noqa: BLE001
                pass
            finally:
                self._writer = None
                self._reader = None

    async def _send_and_receive(self, payload: bytes, read_size: int = 1024) -> bytearray:
        """Send payload and read response."""
        if self._writer is None or self._reader is None:
            raise CommunicationError("Not connected")

        self._writer.write(payload)
        await self._writer.drain()

        try:
            data = await asyncio.wait_for(
                self._reader.read(read_size),
                timeout=TIMEOUT,
            )
        except asyncio.TimeoutError as err:
            raise CommunicationError("Response timeout") from err

        return bytearray(data)

    async def auth(self, password: str) -> bool:
        """Authenticate with the alarm panel."""
        if len(password) not in (4, 6) or not password.isdigit():
            raise CommunicationError("Password must be 4 or 6 digits")

        payload = _make_auth_payload(password)
        response = await self._send_and_receive(payload)

        if len(response) < 9:
            raise CommunicationError("Auth response too short")

        _, resp_payload = _parse_response(response)

        if len(resp_payload) == 0:
            raise CommunicationError("Empty auth response payload")

        result = resp_payload[0]

        if result == 0:
            return True
        if result == 1:
            raise AuthError("Invalid password")
        if result == 2:
            raise AuthError("Incorrect software version")
        if result == 3:
            raise AuthError("Alarm panel will call back")
        if result == 4:
            raise AuthError("Waiting for user permission")

        raise CommunicationError(f"Unknown auth response: {result}")

    async def status(self) -> AMTStatus:
        """Get the current status of the alarm system."""
        payload = _make_payload(Command.STATUS)
        self._writer.write(payload)
        await self._writer.drain()

        # Read the header first (variable response size)
        data = bytearray()
        try:
            # Read in chunks until we get enough data
            chunk = await asyncio.wait_for(
                self._reader.read(4096),
                timeout=TIMEOUT,
            )
            data.extend(chunk)

            # If we need more data (the Go implementation reads in two passes)
            if len(data) > 0 and len(data) < data[0] + 6:
                try:
                    chunk2 = await asyncio.wait_for(
                        self._reader.read(4096),
                        timeout=TIMEOUT,
                    )
                    data.extend(chunk2)
                except asyncio.TimeoutError:
                    pass  # Use what we have

        except asyncio.TimeoutError as err:
            raise CommunicationError("Status response timeout") from err

        if len(data) < 9:
            raise CommunicationError(f"Status response too short: {len(data)} bytes")

        _, resp_payload = _parse_response(data)
        return _parse_status(resp_payload)

    async def arm(self, partition: int) -> bool:
        """Arm a partition. Use 0 or 0xFF for all partitions."""
        if partition == 0:
            partition = 0xFF

        payload = _make_payload(Command.ARM_DISARM, [partition, 0x01])
        response = await self._send_and_receive(payload)

        if len(response) < 9:
            _LOGGER.warning("Arm response too short: %d", len(response))
            return False

        _, resp_payload = _parse_response(response)
        if len(resp_payload) > 0:
            if resp_payload[0] == 0xF0:
                _LOGGER.warning("Cannot arm: open zones detected")
                return False
            if resp_payload[0] == 0x40:
                return True

        # Also check byte 8 directly as the original code does
        if len(response) > 8 and response[8] == 0x91:
            return True

        return True  # Assume success if no error

    async def arm_stay(self, partition: int) -> bool:
        """Arm a partition in stay mode."""
        if partition == 0:
            partition = 0xFF

        payload = _make_payload(Command.ARM_DISARM, [partition, 0x02])
        response = await self._send_and_receive(payload)

        if len(response) > 8 and response[8] == 0x91:
            return True

        _, resp_payload = _parse_response(response)
        if len(resp_payload) > 0 and resp_payload[0] == 0xF0:
            _LOGGER.warning("Cannot arm stay: open zones detected")
            return False

        return True

    async def disarm(self, partition: int) -> bool:
        """Disarm a partition. Use 0 or 0xFF for all partitions."""
        if partition == 0:
            partition = 0xFF

        payload = _make_payload(Command.ARM_DISARM, [partition, 0x00])
        response = await self._send_and_receive(payload)

        if len(response) > 8 and response[8] == 0x91:
            return True

        return True  # Assume success if no error

    async def panic(self, panic_type: int = 1) -> bool:
        """Trigger a panic alarm."""
        payload = _make_payload(Command.PANIC, [panic_type, 0xA5])
        response = await self._send_and_receive(payload)

        if len(response) > 7 and response[7] == 0xFE:
            return True

        return True

    async def turn_off_siren(self, partition: int = 0xFF) -> bool:
        """Turn off the siren."""
        payload = _make_payload(Command.TURN_OFF_SIREN, [partition])
        await self._send_and_receive(payload)
        return True

    async def clean_firings(self) -> bool:
        """Clean zone firings."""
        payload = _make_payload(Command.CLEAN_FIRING)
        await self._send_and_receive(payload)
        return True

    async def bypass_zone(self, zone: int, bypass: bool = True) -> bool:
        """Bypass/un-bypass a zone. Zone is 1-indexed."""
        action = 0x01 if bypass else 0x00
        payload = _make_payload(Command.BYPASS, [zone - 1, action])
        await self._send_and_receive(payload)
        return True

    async def disconnect(self) -> None:
        """Send disconnect command and close."""
        try:
            if self._writer is not None:
                payload = _make_payload(Command.DISCONNECT)
                self._writer.write(payload)
                await self._writer.drain()
        except Exception:  # noqa: BLE001
            pass
        finally:
            await self.close()


async def test_connection(host: str, port: int, password: str) -> bool:
    """Test if we can connect and authenticate to the alarm."""
    client = AsyncClient(host, port)
    try:
        await client.connect()
        await client.auth(password)
        return True
    finally:
        await client.disconnect()
