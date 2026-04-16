import asyncio
import logging
import queue
import threading
from typing import List, Tuple

import numpy

from network.binary import (
    BinaryMessage, ProtocolBinary, MessageType, ProtocolFlags,
    BinaryReader, BinaryWriter
)
from network.websocket import ProtocolWebsocket


class NetworkClient:
    """Synchronous network client that runs asyncio in a background thread."""

    def __init__(self, server_url: str):
        # Normalize URL: convert http(s):// to ws(s)://, add scheme if missing
        if server_url.startswith("http://"):
            server_url = server_url.replace("http://", "ws://", 1)
        elif server_url.startswith("https://"):
            server_url = server_url.replace("https://", "wss://", 1)
        elif not (server_url.startswith("ws://") or server_url.startswith("wss://")):
            server_url = "ws://" + server_url
        # Remove trailing slash if present
        if server_url.endswith("/"):
            server_url = server_url[:-1]
        self.server_url = server_url
        self.binary_proto = ProtocolBinary()
        self._request_queue = queue.Queue()
        self._response_queue = queue.Queue()
        self._stop_event = threading.Event()
        self._thread = threading.Thread(target=self._run_async_loop, daemon=True)
        self._thread.start()

    def _run_async_loop(self):
        try:
            asyncio.run(self._async_main())
        except Exception as e:
            logging.error(f"NetworkClient background thread failed: {e}")

    async def _async_main(self):
        self.ws_proto = ProtocolWebsocket(self.server_url, self.binary_proto)
        self.ws_proto.set_binary_handler(self._on_binary_message)
        try:
            await self.ws_proto.connect()
        except Exception as e:
            logging.error(f"Failed to connect to {self.server_url}: {e}")
            self._stop_event.set()
            return

        logging.info("WebSocket connected, sending protocol negotiation...")
        cap_writer = BinaryWriter()
        cap_writer.write_uint8(1)
        cap_writer.write_uint8(1)
        cap_writer.write_uint8(0)
        cap_writer.write_uint32(10 * 1024 * 1024)
        cap_writer.write_uint16(len(MessageType))
        for mt in MessageType:
            cap_writer.write_uint16(mt.value)

        msg = self.binary_proto.create_message(
            MessageType.PROTOCOL_NEGOTIATION,
            cap_writer.get_buffer(),
            flags=ProtocolFlags.RELIABLE
        )
        await self.ws_proto.send_binary_message(msg.serialize())
        logging.info("Protocol negotiation sent")

        asyncio.create_task(self._process_requests())

        while not self._stop_event.is_set():
            await asyncio.sleep(0.1)

        await self.ws_proto.close()

    async def _process_requests(self):
        while not self._stop_event.is_set():
            try:
                cx, cz = await asyncio.get_event_loop().run_in_executor(
                    None, self._request_queue.get, True, 0.1
                )
                await self._request_chunk_async(cx, cz)
            except queue.Empty:
                await asyncio.sleep(0.01)
            except Exception as e:
                logging.error(f"Request processing error: {e}")

    async def _request_chunk_async(self, cx: int, cz: int):
        writer = BinaryWriter()
        writer.write_int32(cx)
        writer.write_int32(cz)
        msg = self.binary_proto.create_message(
            MessageType.CHUNK_REQUEST,
            writer.get_buffer(),
            flags=ProtocolFlags.RELIABLE
        )
        await self.ws_proto.send_binary_message(msg.serialize())
        logging.debug(f"Requested chunk ({cx},{cz})")

    async def _on_binary_message(self, data: bytes):
        if not data:
            logging.warning("WebSocket closed")
            self._stop_event.set()
            return
        try:
            msg = BinaryMessage.deserialize(data)
            if msg.header.message_type == MessageType.CHUNK_DATA:
                reader = BinaryReader(msg.payload)
                cx = reader.read_int32()
                cz = reader.read_int32()
                vertices_data = reader.read_bytes(reader.read_uint32())
                indices_data = reader.read_bytes(reader.read_uint32())
                tree_count = reader.read_uint32()
                vertices = numpy.frombuffer(vertices_data, dtype=numpy.float32).reshape(-1, 6)
                indices = numpy.frombuffer(indices_data, dtype=numpy.uint32)
                trees = []
                for _ in range(tree_count):
                    trees.append({
                        'x': reader.read_float(),
                        'z': reader.read_float(),
                        'type': reader.read_uint8()
                    })
                self._response_queue.put((cx, cz, vertices, indices, trees))
                logging.debug(f"Received chunk ({cx},{cz}) with {len(vertices)} vertices")
            elif msg.header.message_type == MessageType.HEARTBEAT:
                pong = self.binary_proto.create_message(MessageType.HEARTBEAT, b'')
                await self.ws_proto.send_binary_message(pong.serialize())
            elif msg.header.message_type == MessageType.SUCCESS:
                logging.info("Server success: " + msg.payload.decode('utf-8', errors='replace'))
            elif msg.header.message_type == MessageType.ERROR:
                logging.error("Server error: " + msg.payload.decode('utf-8', errors='replace'))
            else:
                logging.warning(f"Unhandled message type {msg.header.message_type}")
        except Exception as e:
            logging.error(f"Failed to process binary message: {e}")

    def request_chunk(self, cx: int, cz: int):
        self._request_queue.put((cx, cz))

    def get_completed(self) -> List[Tuple[int, int, numpy.ndarray, numpy.ndarray, list]]:
        completed = []
        while True:
            try:
                completed.append(self._response_queue.get_nowait())
            except queue.Empty:
                break
        return completed

    def stop(self):
        self._stop_event.set()
        if self._thread.is_alive():
            self._thread.join(timeout=2.0)