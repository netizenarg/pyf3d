import asyncio
import json
import logging
import math
import queue
import random
import time
import threading
from typing import List, Tuple, Optional

import numpy

from network.binary import (
    BinaryMessage, ProtocolBinary, MessageType, ProtocolFlags,
    BinaryReader, BinaryWriter, is_valid_binary_message
)
from network.websocket import ProtocolWebsocket
from player import Player
from remote_player import RemotePlayer


class NetworkClient:
    """Synchronous network client that runs asyncio in a background thread."""

    def __init__(self, server_url: str, protocol: str = "binary", player: Player = None, password: str = ""):
        self._stop_async_event = asyncio.Event()
        if server_url.startswith("http://"):
            server_url = server_url.replace("http://", "ws://", 1)
        elif server_url.startswith("https://"):
            server_url = server_url.replace("https://", "wss://", 1)
        elif not (server_url.startswith("ws://") or server_url.startswith("wss://")):
            server_url = "ws://" + server_url
        if server_url.endswith("/"):
            server_url = server_url[:-1]
        self.authenticated = False
        self.server_url = server_url
        self.protocol = protocol
        self.player = player
        self.password = password
        self.remote_players = {}
        self.remote_players_lock = threading.Lock()
        self.binary_proto = ProtocolBinary()
        self._request_queue = queue.Queue()
        self._queue_chunks = queue.Queue()
        self._stop_event = threading.Event()
        self.pending_chunk_size = 0
        self.pending_chunk_spacing = 0
        self.chunk_manager = None
        self.async_event_loop = None
        self._thread = threading.Thread(target=self._run_async_event_loop, daemon=True)
        self._thread.start()

    def timestamp(self):
        return int(time.time()) * 1000

    def _run_async_event_loop(self):
        self.async_event_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.async_event_loop)
        self.async_event_loop.create_task(self._async_main())
        try:
            self.async_event_loop.run_forever()
        finally:
            self.async_event_loop.close()

    async def _heartbeat_loop(self):
        while not self._stop_event.is_set():
            await asyncio.sleep(5)
            if self.is_connected():
                await self.ws_proto.client.send_ping()

    async def _authenticate(self):
        if self.protocol == "binary":
            writer = BinaryWriter()
            writer.write_string(self.player.name)
            writer.write_string(self.password)
            writer.write_float(self.player.position[0])
            writer.write_float(self.player.position[1])
            writer.write_float(self.player.position[2])
            msg = self.binary_proto.create_message(
                MessageType.AUTHENTICATION,
                writer.get_buffer(),
                flags=ProtocolFlags.RELIABLE
            )
            await self.ws_proto.send_binary_message(msg.serialize())
        else:
            await self.ws_proto.send_json({
                "msg": "authentication",
                "login": self.player.name,
                "password": self.password,
                "x": self.player.position[0],
                "y": self.player.position[1],
                "z": self.player.position[2]
            })
        logging.info("Authentication request sent")

    async def _async_main(self):
        self.ws_proto = ProtocolWebsocket(self.server_url, self.binary_proto)
        self.ws_proto.set_binary_handler(self._on_binary)
        self.ws_proto.client.on_json = self._on_json
        try:
            await self.ws_proto.connect()
        except Exception as err:
            logging.error(f"Failed to connect to {self.server_url}: {err}")
            self._stop_event.set()
            return
        logging.info("WebSocket connected, sending protocol negotiation...")
        if self.protocol == "binary":
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
        else:
            await self.ws_proto.send_json({
                "msg": "protocol_negotiation",
                "protocol": "websocket",
                "version": 1
            })
        if self.player.name:
            await self._authenticate()
        self.heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        self.process_task = asyncio.create_task(self._process_requests())
        await self._stop_async_event.wait()
        self._stop_event.set()
        for task in (self.process_task, self.heartbeat_task):
            if task and not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        logging.debug(f"NetworkClient._async_main: run _safe_close")
        await self._safe_close()
        self.async_event_loop.stop()

    async def _process_requests(self):
        while not self._stop_event.is_set():
            if self._request_queue.empty():
                await asyncio.sleep(0.1)
                continue
            try:
                cx, cz = await asyncio.get_event_loop().run_in_executor(None, self._request_queue.get, True, 0.1)
                if self._stop_event.is_set():
                    break
                self._request_queue.task_done()
                await self._request_chunk_async(cx, cz)
            except queue.Empty as err:
                logging.error(f"Request processing (queue.Empty): {err}")
                await asyncio.sleep(0.1)
            except asyncio.CancelledError as err:
                logging.error(f"Request processing (CancelledError): {err}")
                break
            except RuntimeError as err:
                logging.error(f"Request processing (RuntimeError): {err}")
                break
            except ConnectionError as err:
                logging.error(f"Request processing (ConnectionError): {err}")
                break
            except Exception as err:
                logging.error(f"Request processing: {err}")
                break

    async def _safe_close(self):
        if self.ws_proto and self.ws_proto.client:
            try:
                await asyncio.wait_for(self.ws_proto.close(1000, "client finish"), timeout=1)
            except asyncio.TimeoutError:
                if not self.ws_proto.client._closed:
                    await self.ws_proto.client.close()
            except Exception as err:
                logging.error(f"NetworkClient._safe_close ignored: {err}")
            else:
                logging.debug(f"NetworkClient._safe_close() - running...")

    def is_connected(self):
        return not self._stop_event.is_set() and self.ws_proto and self.ws_proto.client and not self.ws_proto.client._closed

    def close(self):
        self._request_queue.shutdown()
        self._stop_event.set()
        if self.async_event_loop and not self.async_event_loop.is_closed():
            self.async_event_loop.call_soon_threadsafe(self._stop_async_event.set)
        if self._thread.is_alive():
            self._thread.join(timeout=1)

    def __del__(self):
        self.close()

    def request_chunk_params(self):
        if self.protocol == "binary":
            writer = BinaryWriter()
            msg = self.binary_proto.create_message(
                MessageType.CHUNK_PARAMS,
                writer.get_buffer(),
                flags=ProtocolFlags.RELIABLE
            )
            asyncio.run_coroutine_threadsafe(self.ws_proto.send_binary_message(msg.serialize()), self.async_event_loop)
        else:
            asyncio.run_coroutine_threadsafe(
                self.ws_proto.send_json({"msg": "chunk_params"}),
                self.async_event_loop
            )
        logging.debug("Chunk parameters request sent")

    async def _request_chunk_async(self, cx: int, cz: int):
        if self._stop_event.is_set() or not self.is_connected():
            return
        if self.protocol == "binary":
            writer = BinaryWriter()
            writer.write_int32(cx)
            writer.write_int32(cz)
            writer.write_float(round(self.player.position[0], 3))
            writer.write_float(round(self.player.position[1], 3))
            writer.write_float(round(self.player.position[2], 3))
            msg = self.binary_proto.create_message(
                MessageType.CHUNK_DATA,
                writer.get_buffer(),
                flags=ProtocolFlags.RELIABLE
            )
            await self.ws_proto.send_binary_message(msg.serialize())
        else:
            logging.debug(f"Sending JSON chunk request: {cx},{cz} with player position")
            player_x = round(self.player.position[0], 3)
            player_y = round(self.player.position[1], 3)
            player_z = round(self.player.position[2], 3)
            await self.ws_proto.send_json({
                "msg": "get_chunk",
                "x": cx,
                "z": cz,
                "lod": 0,
                "player_x": player_x,
                "player_y": player_y,
                "player_z": player_z
            })
        logging.debug(f"Requested chunk ({cx},{cz}) player at {(player_x, player_y, player_z)}")

    def request_chunk(self, cx: int, cz: int):
        self._request_queue.put((cx, cz))

    def get_chunks(self) -> List[Tuple[int, int, numpy.ndarray, numpy.ndarray, list]]:
        completed = []
        while True:
            try:
                completed.append(self._queue_chunks.get_nowait())
            except queue.Empty:
                break
        return completed

    async def _on_binary(self, data: bytes):
        if not data:
            logging.warning("WebSocket closed")
            self._stop_event.set()
            return

        if not is_valid_binary_message(data):
            logging.warning(f"Ignoring non-binary-protocol data: {data[:20].hex()}")
            return

        try:
            msg = BinaryMessage.deserialize(data)
            match msg.header.message_type:
                case MessageType.HEARTBEAT:
                    pong = self.binary_proto.create_message(MessageType.HEARTBEAT, b'')
                    await self.ws_proto.send_binary_message(pong.serialize())
                case MessageType.CHUNK_PARAMS:
                    reader = BinaryReader(msg.payload)
                    timestamp = reader.read_uint64()
                    self.pending_chunk_size = reader.read_uint32()
                    self.pending_chunk_spacing = reader.read_float()
                    if self.chunk_manager:
                        self.chunk_manager.update_chunk_params(self.pending_chunk_size, self.pending_chunk_spacing)
                    logging.debug(f"Chunk parameters received (srvtime {timestamp}): size={self.pending_chunk_size}, spacing={self.pending_chunk_spacing}")
                case MessageType.CHUNK_DATA:
                    reader = BinaryReader(msg.payload)
                    timestamp = reader.read_uint64()
                    cx = reader.read_int32()
                    cz = reader.read_int32()
                    vertices = numpy.frombuffer(reader.read_bytes(reader.read_uint32()), dtype=numpy.float32).reshape(-1, 6)
                    indices = numpy.frombuffer(reader.read_bytes(reader.read_uint32()), dtype=numpy.uint32)
                    self._queue_chunks.put((cx, cz, vertices, indices, [], [], None))
                    logging.debug(f"Received chunk (srvtime {timestamp}): ({cx},{cz}) with {len(vertices)} vertices")
                case MessageType.PLAYERS_UPDATE:
                    reader = BinaryReader(msg.payload)
                    timestamp = reader.read_uint64()
                    plid = reader.read_uint64()
                    if plid == self.player.get_id():
                        return
                    x, y, z = reader.read_vector3()
                    yaw = reader.read_float()
                    health = reader.read_float()
                    max_health = reader.read_float()
                    name = reader.read_string()
                    with self.remote_players_lock:
                        if plid in self.remote_players:
                            self.remote_players[plid].update((x, y, z), yaw, health, max_health)
                        else:
                            self.remote_players[plid] = RemotePlayer(plid, name, (x, y, z), yaw, health, max_health)
                    logging.debug(f"player spawn (srvtime {timestamp}): {plid} ({name})")
                case MessageType.PLAYER_SPAWN:
                    reader = BinaryReader(msg.payload)
                    timestamp = reader.read_uint64()
                    plid = reader.read_uint64()
                    name = reader.read_string()
                    x, y, z = reader.read_vector3()
                    yaw = reader.read_float()
                    health = reader.read_float()
                    max_health = reader.read_float()
                    if plid != self.player.get_id():
                        with self.remote_players_lock:
                            self.remote_players[plid] = RemotePlayer(plid, name, (x, y, z), yaw, health, max_health)
                    logging.debug(f"player spawn (srvtime {timestamp}): {plid} ({name})")
                case MessageType.PLAYER_DESPAWN:
                    reader = BinaryReader(msg.payload)
                    timestamp = reader.read_uint64()
                    plid = reader.read_uint64()
                    with self.remote_players_lock:
                        if plid in self.remote_players:
                            del self.remote_players[plid]
                    logging.debug(f"player despawn (srvtime {timestamp}): {plid}")
                case MessageType.CHAT_MESSAGE:
                    reader = BinaryReader(msg.payload)
                    sender = reader.read_string()
                    text = reader.read_string()
                    ts = reader.read_uint64()
                    if self.chat_callback:
                        self.chat_callback(sender, text, ts)
                case MessageType.AUTHENTICATION:
                    reader = BinaryReader(msg.payload)
                    timestamp = reader.read_uint64()
                    player_id = reader.read_uint64()
                    message = reader.read_string()
                    if player_id:
                        logging.debug(f"Authentication successful (srvtime {timestamp}): {message}")
                        self.authenticated = True
                        self.player.set_id(player_id)
                        self.request_chunk_params()
                    else:
                        logging.error(f"Authentication failed (srvtime {timestamp}): {message}")
                        self._stop_event.set()
                case MessageType.SUCCESS:
                    logging.info("Server success: " + msg.payload.decode('utf-8', errors='replace'))
                case MessageType.ERROR:
                    logging.error("Server error: " + msg.payload.decode('utf-8', errors='replace'))
                case _:
                    logging.warning(f"Unhandled binary message type {msg.header.message_type}")
        except Exception as err:
            logging.error(f"Failed to process binary message: {err}")
            logging.debug(f"First 20 bytes: {data[:20].hex()}")

    def _on_json(self, text: str):
        logging.debug(f"RECEIVED: {text[:100]}")
        try:
            data = json.loads(text)
            msg_type = data.get("msg")
            match msg_type:
                case "chunk_params":
                    self.pending_chunk_size = data.get("size", 32)
                    self.pending_chunk_spacing = data.get("spacing", 1.0)
                    logging.info(f"Chunk parameters received: size={self.pending_chunk_size}, spacing={self.pending_chunk_spacing}")
                    if self.chunk_manager:
                        self.chunk_manager.update_chunk_params(self.pending_chunk_size, self.pending_chunk_spacing)
                case "get_chunk":
                    cx = data.get("x", 0)
                    cz = data.get("z", 0)
                    vertices_raw = data.get("vertices", [])
                    indices_raw = data.get("indices", [])
                    if len(vertices_raw) == 0 or len(indices_raw) == 0:
                        logging.warning(f"Chunk ({cx},{cz}) has NO vertices or indices!")
                        return
                    vertices = numpy.array(vertices_raw, dtype=numpy.float32).reshape(-1, 6)
                    indices = numpy.array(indices_raw, dtype=numpy.uint32)
                    self._queue_chunks.put((cx, cz, vertices, indices, [], [], None))
                    logging.debug(f"Received chunk ({cx},{cz}) with {len(vertices)} vertices")
                case "entity_sync":
                    pass
                case "player_position":
                    pass
                case "player_spawn":
                    plid = data["player_id"]
                    name = data["name"]
                    pos = (data["position"][0], data["position"][1], data["position"][2])
                    yaw = data["yaw"]
                    health = data["health"]
                    max_health = data["max_health"]
                    if plid != self.player.get_id():
                        with self.remote_players_lock:
                            self.remote_players[plid] = RemotePlayer(plid, name, pos, yaw, health, max_health)
                    logging.debug(f"Player {name} (ID:{plid}) spawned")
                case "player_despawn":
                    plid = data["player_id"]
                    with self.remote_players_lock:
                        if plid in self.remote_players:
                            del self.remote_players[plid]
                    logging.debug(f"Player ID:{plid} despawned")
                case "player_update":
                    players_data = data.get("players", [])
                    current_ids = set()
                    for p in players_data:
                        plid = p["id"]
                        current_ids.add(plid)
                        if plid == self.player.get_id():
                            continue
                        pos = (p["x"], p["y"], p["z"])
                        yaw = p["yaw"]
                        health = p["health"]
                        max_health = p["max_health"]
                        name = p["name"]
                        with self.remote_players_lock:
                            if plid in self.remote_players:
                                self.remote_players[plid].update(pos, yaw, health, max_health)
                            else:
                                self.remote_players[plid] = RemotePlayer(plid, name, pos, yaw, health, max_health)
                    with self.remote_players_lock:
                        for plid in list(self.remote_players.keys()):
                            if plid not in current_ids:
                                del self.remote_players[plid]
                case "chat_message":
                    sender = data.get("sender", "")
                    text = data.get("message", "")
                    ts = data.get("timestamp", 0)
                    if self.chat_callback:
                        self.chat_callback(sender, text, ts)
                    logging.debug(f"Receive chat message: {(sender, text)}")
                case "authentication":
                    player_id = data.get("player_id", 0)
                    description = data.get("desc", "")
                    if player_id:
                        logging.info(f"NetworkClient._on_json: authentication successful ({description})")
                        self.authenticated = True
                        self.player.set_id(player_id)
                        self.request_chunk_params()
                    else:
                        logging.error(f"Authentication failed: {description}")
                        self._stop_event.set()
                case "error":
                    logging.error(f"Server error: {data.get('desc', 'Unknown error')}")
                case "success":
                    logging.info(f"Server success: {data.get('desc', '')}")
                case "server_status": # Silently ignore – just a periodic update from the master
                    pass
                case _:
                    logging.debug(f"Unhandled JSON message type: {msg_type}")
        except Exception as err:
            logging.error(f"Failed to parse JSON message: {err}")

    def get_remote_players_snapshot(self):
        with self.remote_players_lock:
            return dict(self.remote_players)

    def send_player_position(self, x, y, z):
        if not self.authenticated:
            logging.warning("send_player_position: network client not authenticated")
        elif self.protocol == "binary":
            writer = BinaryWriter()
            writer.write_uint64(self.timestamp())
            writer.write_uint64(self.player.get_id())
            writer.write_vector3(x, y, z)
            writer.write_vector3(0.0, 0.0, 0.0)
            msg = self.binary_proto.create_message(
                MessageType.PLAYER_POSITION,
                writer.get_buffer(),
                flags=ProtocolFlags.RELIABLE
            )
            self.async_event_loop.call_soon_threadsafe(
                lambda: asyncio.ensure_future(
                    self.ws_proto.send_binary_message(msg.serialize())
                )
            )
        else:
            data = {
                "msg": "player_position",
                "timestamp": self.timestamp(),
                "player_id": self.player.get_id(),
                "x": round(x, 3), "y": round(y, 3), "z": round(z, 3)
            }
            logging.debug(f"SEND: {data}")
            self.async_event_loop.call_soon_threadsafe(
                lambda: asyncio.ensure_future(
                    self.ws_proto.send_json(data)
                )
            )

    def set_chat_callback(self, callback):
        self.chat_callback = callback

    def send_chat_message(self, message):
        if not self.authenticated:
            logging.warning("send_chat_message: network client not authenticated")
        else:
            if self.protocol == "binary":
                writer = BinaryWriter()
                writer.write_string(self.player.name)
                writer.write_string(message)
                writer.write_uint64(int(time.time() * 1000))
                msg = self.binary_proto.create_message(
                    MessageType.CHAT_MESSAGE,
                    writer.get_buffer(),
                    flags=ProtocolFlags.RELIABLE
                )
                self.async_event_loop.call_soon_threadsafe(
                    lambda: asyncio.ensure_future(self.ws_proto.send_binary_message(msg.serialize()))
                )
            else:
                data = {
                    "msg": "chat_message",
                    "sender": self.player.name,
                    "message": message,
                    "timestamp": int(time.time() * 1000)
                }
                async def send():
                    try:
                        await self.ws_proto.send_json(data)
                        logging.debug(f"Chat JSON sent: {data}")
                    except Exception as err:
                        logging.error(f"Chat send failed: {err}")
                self.async_event_loop.call_soon_threadsafe(
                    lambda: asyncio.ensure_future(send())
                )
        #logging.debug(f"send chat message: {message}")
