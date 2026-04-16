import asyncio
import base64
import hashlib
import json
import logging
import os
import struct
import ssl
import socket
from enum import IntEnum
from typing import Optional, Callable, Dict, Any, Tuple


class Opcode(IntEnum):
    CONTINUATION = 0x0
    TEXT = 0x1
    BINARY = 0x2
    CLOSE = 0x8
    PING = 0x9
    PONG = 0xA


class WebSocketFrame:
    def __init__(self, fin: bool = True, opcode: int = Opcode.BINARY, payload: bytes = b''):
        self.fin = fin
        self.rsv1 = False
        self.rsv2 = False
        self.rsv3 = False
        self.opcode = opcode
        self.masked = False
        self.masking_key = [0, 0, 0, 0]
        self.payload = payload

    def serialize(self) -> bytes:
        byte0 = (0x80 if self.fin else 0x00) | (self.opcode & 0x0F)
        if self.rsv1: byte0 |= 0x40
        if self.rsv2: byte0 |= 0x20
        if self.rsv3: byte0 |= 0x10
        header = bytearray([byte0])

        length = len(self.payload)
        mask_bit = 0x80 if self.masked else 0x00
        if length <= 125:
            header.append(mask_bit | length)
        elif length <= 65535:
            header.append(mask_bit | 126)
            header.extend(struct.pack('!H', length))
        else:
            header.append(mask_bit | 127)
            header.extend(struct.pack('!Q', length))

        if self.masked:
            header.extend(self.masking_key)

        data = bytes(header) + self.payload

        if self.masked:
            payload_start = len(header)
            masked_payload = bytearray(self.payload)
            for i in range(len(masked_payload)):
                masked_payload[i] ^= self.masking_key[i % 4]
            data = bytes(header) + masked_payload

        return data

    @classmethod
    def parse(cls, data: bytes) -> Tuple['WebSocketFrame', int]:
        if len(data) < 2:
            raise ValueError("Incomplete frame")
        pos = 0
        byte0 = data[pos]
        pos += 1
        fin = (byte0 & 0x80) != 0
        rsv1 = (byte0 & 0x40) != 0
        rsv2 = (byte0 & 0x20) != 0
        rsv3 = (byte0 & 0x10) != 0
        opcode = byte0 & 0x0F

        byte1 = data[pos]
        pos += 1
        masked = (byte1 & 0x80) != 0
        payload_len = byte1 & 0x7F

        if payload_len == 126:
            if len(data) < pos + 2:
                raise ValueError("Incomplete extended length")
            payload_len = struct.unpack_from('!H', data, pos)[0]
            pos += 2
        elif payload_len == 127:
            if len(data) < pos + 8:
                raise ValueError("Incomplete extended length")
            payload_len = struct.unpack_from('!Q', data, pos)[0]
            pos += 8

        masking_key = [0, 0, 0, 0]
        if masked:
            if len(data) < pos + 4:
                raise ValueError("Incomplete masking key")
            masking_key = list(data[pos:pos+4])
            pos += 4

        if len(data) < pos + payload_len:
            raise ValueError("Incomplete payload")

        payload = data[pos:pos+payload_len]
        if masked:
            payload = bytearray(payload)
            for i in range(len(payload)):
                payload[i] ^= masking_key[i % 4]
            payload = bytes(payload)

        frame = cls(fin, opcode, payload)
        frame.rsv1 = rsv1
        frame.rsv2 = rsv2
        frame.rsv3 = rsv3
        frame.masked = masked
        frame.masking_key = masking_key
        return frame, pos + payload_len


class WebSocketClient:
    def __init__(self, url: str, ssl_context: Optional[ssl.SSLContext] = None):
        self.url = url
        self.ssl_context = ssl_context
        self.reader: Optional[asyncio.StreamReader] = None
        self.writer: Optional[asyncio.StreamWriter] = None
        self._closed = False
        self._receive_task: Optional[asyncio.Task] = None

        self.on_text: Optional[Callable[[str], None]] = None
        self.on_binary: Optional[Callable[[bytes], None]] = None
        self.on_close: Optional[Callable[[int, str], None]] = None

    async def connect(self):
        # Parse URL
        if self.url.startswith("ws://"):
            port = 80
            host = self.url[5:].split("/")[0]
            path = "/" + "/".join(self.url[5:].split("/")[1:]) if "/" in self.url[5:] else "/"
            use_ssl = False
        elif self.url.startswith("wss://"):
            port = 443
            host = self.url[6:].split("/")[0]
            path = "/" + "/".join(self.url[6:].split("/")[1:]) if "/" in self.url[6:] else "/"
            use_ssl = True
        else:
            raise ValueError("URL must start with ws:// or wss://")

        # Resolve hostname with fallback for localhost
        loop = asyncio.get_running_loop()
        try:
            addrs = await loop.getaddrinfo(host, port, family=socket.AF_UNSPEC, type=socket.SOCK_STREAM)
        except socket.gaierror:
            if host == "localhost":
                # Fallback to 127.0.0.1
                logging.warning("localhost resolution failed, using 127.0.0.1")
                addrs = await loop.getaddrinfo("127.0.0.1", port, family=socket.AF_INET, type=socket.SOCK_STREAM)
            else:
                raise

        if not addrs:
            raise ConnectionError(f"Cannot resolve {host}")

        family, _, proto, _, sockaddr = addrs[0]

        if use_ssl:
            if self.ssl_context is None:
                self.ssl_context = ssl.create_default_context()
            self.reader, self.writer = await asyncio.open_connection(
                host, port, ssl=self.ssl_context, server_hostname=host)
        else:
            self.reader, self.writer = await asyncio.open_connection(host, port)

        # WebSocket handshake
        key = base64.b64encode(os.urandom(16)).decode()
        expected_accept = base64.b64encode(
            hashlib.sha1((key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode()).digest()
        ).decode()

        handshake = (
            f"GET {path} HTTP/1.1\r\n"
            f"Host: {host}\r\n"
            f"Upgrade: websocket\r\n"
            f"Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\n"
            f"Sec-WebSocket-Version: 13\r\n"
            f"\r\n"
        )
        self.writer.write(handshake.encode())
        await self.writer.drain()

        response = await self.reader.readuntil(b"\r\n\r\n")
        response_str = response.decode()
        if "101" not in response_str.splitlines()[0]:
            raise ConnectionError(f"Handshake failed: {response_str}")

        for line in response_str.splitlines():
            if line.lower().startswith("sec-websocket-accept:"):
                accept = line.split(":", 1)[1].strip()
                if accept != expected_accept:
                    raise ConnectionError("Invalid accept key")
                break

        self._receive_task = asyncio.create_task(self._receive_loop())

    async def close(self, code: int = 1000, reason: str = ""):
        if self._closed:
            return
        self._closed = True
        payload = struct.pack('!H', code) + reason.encode('utf-8')
        frame = WebSocketFrame(fin=True, opcode=Opcode.CLOSE, payload=payload)
        self.writer.write(frame.serialize())
        await self.writer.drain()
        if self._receive_task:
            self._receive_task.cancel()
        self.writer.close()
        await self.writer.wait_closed()

    async def send_text(self, text: str):
        frame = WebSocketFrame(fin=True, opcode=Opcode.TEXT, payload=text.encode('utf-8'))
        self.writer.write(frame.serialize())
        await self.writer.drain()

    async def send_binary(self, data: bytes):
        frame = WebSocketFrame(fin=True, opcode=Opcode.BINARY, payload=data)
        self.writer.write(frame.serialize())
        await self.writer.drain()

    async def _receive_loop(self):
        buffer = bytearray()
        while not self._closed:
            try:
                data = await self.reader.read(4096)
                if not data:
                    break
                buffer.extend(data)
                while True:
                    try:
                        frame, consumed = WebSocketFrame.parse(buffer)
                        buffer = buffer[consumed:]
                        await self._handle_frame(frame)
                    except (ValueError, IndexError):
                        break
            except asyncio.CancelledError:
                break
            except Exception as e:
                if self.on_close:
                    self.on_close(1006, str(e))
                break

    async def _handle_frame(self, frame: WebSocketFrame):
        if frame.opcode == Opcode.CLOSE:
            code = 1000
            reason = ""
            if len(frame.payload) >= 2:
                code = struct.unpack('!H', frame.payload[:2])[0]
                reason = frame.payload[2:].decode('utf-8', errors='replace')
            if self.on_close:
                self.on_close(code, reason)
            await self.close(code, reason)
        elif frame.opcode == Opcode.PING:
            pong = WebSocketFrame(fin=True, opcode=Opcode.PONG, payload=frame.payload)
            self.writer.write(pong.serialize())
            await self.writer.drain()
        elif frame.opcode == Opcode.PONG:
            pass
        elif frame.opcode == Opcode.TEXT:
            if self.on_text:
                self.on_text(frame.payload.decode('utf-8'))
        elif frame.opcode == Opcode.BINARY:
            if self.on_binary:
                self.on_binary(frame.payload)


class ProtocolWebsocket:
    def __init__(self, url: str, binary_protocol):
        self.client = WebSocketClient(url)
        self.binary = binary_protocol
        self.client.on_binary = self._on_binary
        self.client.on_close = self._on_close
        self._binary_handler: Optional[Callable[[bytes], None]] = None

    async def connect(self):
        await self.client.connect()

    async def close(self):
        await self.client.close()

    def set_binary_handler(self, handler: Callable[[bytes], None]):
        self._binary_handler = handler

    def _on_binary(self, data: bytes):
        if self._binary_handler:
            self._binary_handler(data)

    def _on_close(self, code: int, reason: str):
        if self._binary_handler:
            self._binary_handler(b'')

    async def send_binary_message(self, msg: bytes):
        await self.client.send_binary(msg)

    async def send_json(self, data: Any):
        await self.client.send_text(json.dumps(data))