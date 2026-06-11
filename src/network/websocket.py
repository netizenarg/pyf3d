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
from typing import Optional, Callable, Any, Tuple


class Opcode(IntEnum):
    CONTINUATION = 0x0
    JSON = 0x1
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
        self.on_json: Optional[Callable[[str], None]] = None
        self.on_binary: Optional[Callable[[bytes], None]] = None
        self.on_close: Optional[Callable[[int, str], None]] = None
        self._message_buffer = b''
        self._message_opcode = None

    async def connect(self):
        if self.url.startswith("ws://"):
            rest = self.url[5:]
            use_ssl = False
            default_port = 80
        elif self.url.startswith("wss://"):
            rest = self.url[6:]
            use_ssl = True
            default_port = 443
        else:
            raise ValueError("URL must start with ws:// or wss://")

        if '/' in rest:
            host_part, path = rest.split('/', 1)
            path = '/' + path
        else:
            host_part = rest
            path = '/'

        if ':' in host_part:
            if host_part.startswith('['):
                bracket_end = host_part.find(']')
                if bracket_end == -1:
                    raise ValueError("Invalid IPv6 address")
                host = host_part[1:bracket_end]
                if host_part[bracket_end+1:].startswith(':'):
                    port_str = host_part[bracket_end+2:]
                    port = int(port_str) if port_str else default_port
                else:
                    port = default_port
            else:
                host, port_str = host_part.split(':', 1)
                port = int(port_str)
        else:
            host = host_part
            port = default_port

        if host == "localhost":
            host = "127.0.0.1"
            logging.debug("Replaced localhost with 127.0.0.1")

        try:
            if use_ssl:
                if self.ssl_context is None:
                    self.ssl_context = ssl.create_default_context()
                self.reader, self.writer = await asyncio.open_connection(
                    host, port, ssl=self.ssl_context, server_hostname=host)
            else:
                self.reader, self.writer = await asyncio.open_connection(host, port)
        except Exception as e:
            raise ConnectionError(f"Failed to connect {host}:{port}: {e}")

        key = base64.b64encode(os.urandom(16)).decode()
        expected_accept = base64.b64encode(
            hashlib.sha1((key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode()).digest()
        ).decode()

        handshake = (
            f"GET {path} HTTP/1.1\r\n"
            f"Host: {host}:{port}\r\n"
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

        lines = response_str.splitlines()
        if not lines:
            raise ConnectionError("Empty response")
        status_line = lines[0]
        if "101" not in status_line:
            raise ConnectionError(f"Handshake failed: {status_line}")

        headers = {}
        for line in lines[1:]:
            if ':' not in line:
                continue
            name, value = line.split(':', 1)
            headers[name.strip().lower()] = value.strip()

        accept = headers.get("sec-websocket-accept")
        if not accept:
            raise ConnectionError("Missing Sec-WebSocket-Accept header")

        logging.debug(f"Server accept key: {accept}")
        logging.debug(f"Expected accept key: {expected_accept}")

        if accept != expected_accept:
            raise ConnectionError(f"Invalid accept key: expected '{expected_accept}', got '{accept}'")

        self._receive_task = asyncio.create_task(self._receive_loop())
        #logging.debug(f"WebSocketClient.connect: receive task created {self._receive_task}")

    async def close(self, code: int = 1000, reason: str = ""):
        #logging.debug(f"WebSocketClient.close({code}, {reason})")
        if self._closed:
            return
        self._closed = True
        if self.writer and not self.writer.is_closing():
            try:
                payload = struct.pack('!H', code) + reason.encode('utf-8')
                frame = WebSocketFrame(fin=True, opcode=Opcode.CLOSE, payload=payload)
                self.writer.write(frame.serialize())
                await self.writer.drain()
            except Exception as err:
                logging.error(f'WebSocketClient.close: {err}')
        if self._receive_task:
            self._receive_task.cancel()
            try:
                await self._receive_task
            except asyncio.CancelledError as err:
                logging.error(f'WebSocketClient.close: {err}')
        if self.writer:
            try:
                self.writer.close()
                await self.writer.wait_closed()
            except Exception as err:
                logging.error(f'WebSocketClient.close: {err}')

    async def send_ping(self, payload=b''):
        frame = WebSocketFrame(fin=True, opcode=Opcode.PING, payload=payload)
        self.writer.write(frame.serialize())
        await self.writer.drain()

    async def send_text(self, text: str):
        frame = WebSocketFrame(fin=True, opcode=Opcode.JSON, payload=text.encode('utf-8'))
        self.writer.write(frame.serialize())
        await self.writer.drain()

    async def send_binary(self, data: bytes):
        frame = WebSocketFrame(fin=True, opcode=Opcode.BINARY, payload=data)
        self.writer.write(frame.serialize())
        await self.writer.drain()

    async def _read_frame(self):
        #logging.debug("WebSocketClient._read_frame ========== STARTED ==========")
        header = await self.reader.readexactly(2)
        # try:
        #     header = await asyncio.wait_for(self.reader.readexactly(2), timeout=0.5)
        # except asyncio.TimeoutError:
        #     logging.error("WebSocketClient._read_frame: TIMEOUT")
        #     return None
        # logging.debug(f"WebSocketClient._read_frame: header={header.hex()}")
        byte0 = header[0]
        byte1 = header[1]
        fin = (byte0 & 0x80) != 0
        opcode = byte0 & 0x0F
        masked = (byte1 & 0x80) != 0
        payload_len = byte1 & 0x7F
        if payload_len == 126:
            ext = await self.reader.readexactly(2)
            payload_len = struct.unpack('!H', ext)[0]
        elif payload_len == 127:
            ext = await self.reader.readexactly(8)
            payload_len = struct.unpack('!Q', ext)[0]
        masking_key = [0, 0, 0, 0]
        if masked:
            key_data = await self.reader.readexactly(4)
            masking_key = list(key_data)
        payload = await self.reader.readexactly(payload_len)
        if masked:
            payload = bytearray(payload)
            for i in range(len(payload)):
                payload[i] ^= masking_key[i % 4]
            payload = bytes(payload)
        frame = WebSocketFrame(fin=fin, opcode=opcode, payload=payload)
        #logging.debug("WebSocketClient._read_frame ========== FINISHED ==========")
        return frame

    def _deliver_message(self):
        if self._message_opcode == Opcode.JSON and self.on_json:
            #self.on_json(self._message_buffer.decode('utf-8'))
            text = self._message_buffer.decode('utf-8')
            logging.info(f"WebSocketClient._deliver_message: {text[:30]}")
            self.on_json(text)
        elif self._message_opcode == Opcode.BINARY and self.on_binary:
            self.on_binary(self._message_buffer)
        self._message_buffer = b''
        self._message_opcode = None

    async def _handle_frame(self, frame: WebSocketFrame):
        logging.debug(f"WebSocketClient._handle_frame: opcode={frame.opcode}, len={len(frame.payload)}")
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
        elif frame.opcode == Opcode.JSON:
            logging.debug(f"HANDLING JSON frame")
            self._message_buffer = frame.payload
            self._message_opcode = Opcode.JSON
            if frame.fin:
                self._deliver_message()
        elif frame.opcode == Opcode.BINARY:
            if self.on_binary:
                self.on_binary(frame.payload)
        elif frame.opcode == Opcode.CONTINUATION:
            if self._message_opcode is None:
                return # Protocol error – ignore
            self._message_buffer += frame.payload
            if frame.fin:
                self._deliver_message()
        else:
            pass # Unknown opcode – ignore

    async def _receive_loop(self):
        logging.debug("WebSocketClient._receive_loop ========== STARTED ==========")
        while not self._closed:
            try:
                try:
                    frame = await self._read_frame()
                except asyncio.IncompleteReadError as err:
                    logging.error(f'WebSocketClient._receive_loop (IncompleteReadError): {err}')
                    await self.close(1011, str(err))
                    break
                except IndexError as err:
                    logging.error(f'WebSocketClient._receive_loop (IndexError): {err}')
                    break
                except ValueError as err:
                    logging.error(f'WebSocketClient._receive_loop (ValueError): {err}')
                    break
                else:
                    if frame is None:
                        await self.close(1011, "frame is None, connection closed")
                        break
                    ###########################################################################################
                    logging.debug(f"WebSocketClient._receive_loop: RECEIVED FRAME opcode={frame.opcode}, payload_len={len(frame.payload)}")
                    if frame.opcode == Opcode.JSON:
                        logging.debug(f"JSON text: {frame.payload[:200]}")
                    elif frame.opcode == Opcode.BINARY:
                        logging.debug(f"WebSocketClient._receive_loop: binary payload first 20 bytes <{frame.payload[:20].hex()}>")
                    ###########################################################################################
                    try:
                        await self._handle_frame(frame)
                    except Exception as err:
                        logging.error(f'WebSocketClient._receive_loop (common Exception): {err}')
                        break
            except asyncio.CancelledError as err:
                if err.args:
                    logging.warning(f'WebSocketClient._receive_loop (CancelledError): {err}')
                else:
                    logging.debug('WebSocketClient._receive_loop close connection.')
                break
            except Exception as err:
                logging.error(f'WebSocketClient._receive_loop (common Exception): {err}')
                await self.close(1011, str(err))
                break
        logging.debug("WebSocketClient._receive_loop ========== FINISHED ==========")


class ProtocolWebsocket:
    def __init__(self, url: str, binary_protocol):
        self.client = WebSocketClient(url)
        self.binary = binary_protocol
        self.client.on_binary = self._on_binary
        self.client.on_close = self._on_close
        self._binary_handler: Optional[Callable[[bytes], Any]] = None

    async def connect(self):
        await self.client.connect()

    async def close(self, code: int = 1000, description: str = ""):
        if self.client:
            await self.client.close(code, description)

    def set_binary_handler(self, handler: Callable[[bytes], Any]):
        self._binary_handler = handler

    def _on_binary(self, data: bytes):
        if self._binary_handler:
            asyncio.create_task(self._binary_handler(data))

    def _on_close(self, code: int, reason: str):
        if self._binary_handler:
            asyncio.create_task(self._binary_handler(b''))

    async def send_binary_message(self, msg: bytes):
        await self.client.send_binary(msg)

    async def send_json(self, data: Any):
        await self.client.send_text(json.dumps(data))
