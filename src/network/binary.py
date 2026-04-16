import struct
import zlib
from typing import List, Tuple, Optional
from enum import IntEnum, IntFlag


class MessageType(IntEnum):
    INVALID = 0
    HEARTBEAT = 1
    PROTOCOL_NEGOTIATION = 2
    AUTHENTICATION = 3
    ERROR = 4
    SUCCESS = 5
    CHUNK_DATA = 100
    CHUNK_REQUEST = 101
    TERRAIN_HEIGHT = 102
    BIOME_DATA = 103
    ENTITY_SPAWN = 200
    ENTITY_UPDATE = 201
    ENTITY_DESPAWN = 202
    ENTITY_BATCH_UPDATE = 203
    PLAYER_POSITION = 300
    PLAYER_VELOCITY = 301
    PLAYER_ROTATION = 302
    PLAYER_STATE = 303
    PLAYER_POSITION_CORRECTION = 304
    NPC_SPAWN = 400
    NPC_UPDATE = 401
    NPC_DESPAWN = 402
    NPC_INTERACTION = 403
    COMBAT_EVENT = 500
    DAMAGE_EVENT = 501
    HEALTH_UPDATE = 502
    INVENTORY_UPDATE = 600
    LOOT_SPAWN = 601
    LOOT_PICKUP = 602
    CHAT_MESSAGE = 700
    SYSTEM_MESSAGE = 701
    CUSTOM_EVENT = 1000


class ProtocolFlags(IntFlag):
    COMPRESSED = 0x01
    ENCRYPTED = 0x02
    RELIABLE = 0x04
    ORDERED = 0x08
    PRIORITY_HIGH = 0x10
    PRIORITY_LOW = 0x20


CURRENT_PROTOCOL_VERSION = 1
MAX_MESSAGE_SIZE = 10 * 1024 * 1024


HEADER_FORMAT = '!BB H I I I'
HEADER_SIZE = struct.calcsize(HEADER_FORMAT)
HEADER_FORMAT = '!BB H I I I'
HEADER_SIZE = struct.calcsize(HEADER_FORMAT)

class NetworkHeader:
    __slots__ = ('version', 'flags', 'message_type', 'sequence', 'timestamp', 'length', 'checksum')
    def __init__(self, message_type: int = 0, sequence: int = 0, version: int = CURRENT_PROTOCOL_VERSION, flags: int = 0):
        self.version = version
        self.flags = flags
        self.message_type = message_type
        self.sequence = sequence
        self.timestamp = 0
        self.length = 0
        self.checksum = 0

    def pack(self) -> bytes:
        return struct.pack(HEADER_FORMAT,
                           self.version, self.flags, self.message_type,
                           self.sequence, self.timestamp, self.length)

    @classmethod
    def unpack(cls, data: bytes) -> 'NetworkHeader':
        (version, flags, msg_type, seq, ts, length) = struct.unpack(HEADER_FORMAT, data)
        header = cls(msg_type, seq, version, flags)
        header.timestamp = ts
        header.length = length
        header.checksum = 0  # checksum is separate
        return header


class BinaryWriter:
    def __init__(self):
        self.buffer = bytearray()

    def write_uint8(self, v: int):
        self.buffer.append(v & 0xFF)

    def write_uint16(self, v: int):
        self.buffer.extend(struct.pack('!H', v))

    def write_uint32(self, v: int):
        self.buffer.extend(struct.pack('!I', v))

    def write_uint64(self, v: int):
        self.buffer.extend(struct.pack('!Q', v))

    def write_int32(self, v: int):
        self.buffer.extend(struct.pack('!i', v))

    def write_int64(self, v: int):
        self.buffer.extend(struct.pack('!q', v))

    def write_float(self, v: float):
        self.buffer.extend(struct.pack('!f', v))

    def write_double(self, v: float):
        self.buffer.extend(struct.pack('!d', v))

    def write_string(self, s: str):
        encoded = s.encode('utf-8')
        self.write_uint32(len(encoded))
        self.buffer.extend(encoded)

    def write_bytes(self, data: bytes):
        self.buffer.extend(data)

    def write_vector3(self, x: float, y: float, z: float):
        self.write_float(x)
        self.write_float(y)
        self.write_float(z)

    def write_quaternion(self, x: float, y: float, z: float, w: float):
        self.write_float(x)
        self.write_float(y)
        self.write_float(z)
        self.write_float(w)

    def write_json(self, obj):
        import json
        s = json.dumps(obj)
        self.write_string(s)

    def get_buffer(self) -> bytes:
        return bytes(self.buffer)

    def clear(self):
        self.buffer.clear()


class BinaryReader:
    def __init__(self, data: bytes):
        self.data = data
        self.pos = 0

    def remaining(self) -> int:
        return len(self.data) - self.pos

    def _check(self, size: int):
        if self.pos + size > len(self.data):
            raise EOFError("Not enough data")

    def read_uint8(self) -> int:
        self._check(1)
        v = self.data[self.pos]
        self.pos += 1
        return v

    def read_uint16(self) -> int:
        self._check(2)
        v = struct.unpack_from('!H', self.data, self.pos)[0]
        self.pos += 2
        return v

    def read_uint32(self) -> int:
        self._check(4)
        v = struct.unpack_from('!I', self.data, self.pos)[0]
        self.pos += 4
        return v

    def read_uint64(self) -> int:
        self._check(8)
        v = struct.unpack_from('!Q', self.data, self.pos)[0]
        self.pos += 8
        return v

    def read_int32(self) -> int:
        self._check(4)
        v = struct.unpack_from('!i', self.data, self.pos)[0]
        self.pos += 4
        return v

    def read_int64(self) -> int:
        self._check(8)
        v = struct.unpack_from('!q', self.data, self.pos)[0]
        self.pos += 8
        return v

    def read_float(self) -> float:
        self._check(4)
        v = struct.unpack_from('!f', self.data, self.pos)[0]
        self.pos += 4
        return v

    def read_double(self) -> float:
        self._check(8)
        v = struct.unpack_from('!d', self.data, self.pos)[0]
        self.pos += 8
        return v

    def read_string(self) -> str:
        length = self.read_uint32()
        self._check(length)
        s = self.data[self.pos:self.pos+length].decode('utf-8')
        self.pos += length
        return s

    def read_bytes(self, length: int) -> bytes:
        self._check(length)
        data = self.data[self.pos:self.pos+length]
        self.pos += length
        return data

    def read_vector3(self) -> Tuple[float, float, float]:
        return (self.read_float(), self.read_float(), self.read_float())

    def read_quaternion(self) -> Tuple[float, float, float, float]:
        return (self.read_float(), self.read_float(), self.read_float(), self.read_float())

    def read_json(self):
        import json
        s = self.read_string()
        return json.loads(s)


class BinaryMessage:
    def __init__(self, header: NetworkHeader = None, payload: bytes = b''):
        self.header = header or NetworkHeader()
        self.payload = payload

    @staticmethod
    def calculate_crc32(data: bytes) -> int:
        return zlib.crc32(data) & 0xFFFFFFFF

    @staticmethod
    def compress(data: bytes, level: int = 6) -> bytes:
        return zlib.compress(data, level)

    @staticmethod
    def decompress(data: bytes) -> bytes:
        return zlib.decompress(data)

    def serialize(self) -> bytes:
        final_payload = self.payload
        if self.header.flags & ProtocolFlags.COMPRESSED:
            final_payload = self.compress(self.payload)

        self.header.length = len(final_payload)
        self.header.checksum = self.calculate_crc32(final_payload)

        header_bytes = self.header.pack()
        return header_bytes + final_payload

    @classmethod
    def deserialize(cls, data: bytes) -> 'BinaryMessage':
        if len(data) < HEADER_SIZE:
            raise ValueError("Message too short")
        header = NetworkHeader.unpack(data[:HEADER_SIZE])
        if header.length > MAX_MESSAGE_SIZE:
            raise ValueError(f"Message too large: {header.length} bytes")
        payload = data[HEADER_SIZE:HEADER_SIZE + header.length]
        if len(payload) != header.length:
            raise ValueError("Payload length mismatch")

        if header.checksum != 0:
            computed = cls.calculate_crc32(payload)
            if computed != header.checksum:
                raise ValueError("Checksum mismatch")

        if header.flags & ProtocolFlags.COMPRESSED:
            payload = cls.decompress(payload)

        return cls(header, payload)


class ProtocolBinary:
    def __init__(self):
        self.next_sequence = 1
        self.pending_acks = {}   # seq -> timestamp

    def create_message(self, msg_type: int, payload: bytes, flags: int = 0, reliable: bool = False) -> BinaryMessage:
        header = NetworkHeader(message_type=msg_type, sequence=self.next_sequence, flags=flags)
        if reliable:
            header.flags |= ProtocolFlags.RELIABLE
        self.next_sequence += 1
        return BinaryMessage(header, payload)

    def send_message(self, writer, msg: BinaryMessage):
        writer.write(msg.serialize())
