import asyncio
import json
import logging
import math
import queue
import random
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
        self._thread = threading.Thread(target=self._run_async_loop, daemon=True)
        self._thread.start()

    def _run_async_loop(self):
        try:
            asyncio.run(self._async_main())
        except Exception as err:
            logging.error(f"NetworkClient background thread failed: {err}")

    async def _authenticate(self):
        if self.protocol == "binary":
            writer = BinaryWriter()
            writer.write_string(self.player.name)#login
            writer.write_string(self.password)
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
                "password": self.password
            })
        logging.info("Authentication request sent")

    async def _async_main(self):
        self.ws_proto = ProtocolWebsocket(self.server_url, self.binary_proto)
        self.ws_proto.set_binary_handler(self._on_binary_message)
        self.ws_proto.client.on_text = self._on_text_message
        try:
            await self.ws_proto.connect()
        except Exception as e:
            logging.error(f"Failed to connect to {self.server_url}: {e}")
            self._stop_event.set()
            return
        logging.info("WebSocket connected, sending protocol negotiation...")
        if self.protocol == "binary": # Send binary protocol capabilities
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
        else: # For WebSocket JSON protocol, just send a welcome message
            await self.ws_proto.send_json({
                "msg": "protocol_negotiation",
                "protocol": "websocket",
                "version": 1
            })
        logging.info("Protocol negotiation sent")
        if self.player.name:
            await self._authenticate()
        asyncio.create_task(self._process_requests())
        process_task = asyncio.create_task(self._process_requests())
        try:
            while not self._stop_event.is_set():
                await asyncio.sleep(0.1)
        finally:
            process_task.cancel()
            try:
                await process_task
            except asyncio.CancelledError:
                pass
            await self.ws_proto.close()

    async def _process_requests(self):
        while not self._stop_event.is_set():
            try:
                cx, cz = await asyncio.get_event_loop().run_in_executor(
                    None, self._request_queue.get, True, 0.1
                )
                if self._stop_event.is_set():
                    break
                await self._request_chunk_async(cx, cz)
            except queue.Empty:
                await asyncio.sleep(0.01)
            except (asyncio.CancelledError, RuntimeError, ConnectionError):
                break
            except Exception as err:
                logging.error(f"Request processing error: {err}")
                break

    async def _request_chunk_async(self, cx: int, cz: int):
        if self._stop_event.is_set() or not self.is_connected():
            return
        if self.protocol == "binary":
            writer = BinaryWriter()
            writer.write_int32(cx)
            writer.write_int32(cz)
            msg = self.binary_proto.create_message(
                MessageType.CHUNK_REQUEST,
                writer.get_buffer(),
                flags=ProtocolFlags.RELIABLE
            )
            await self.ws_proto.send_binary_message(msg.serialize())
        else: # JSON request
            logging.debug(f"Sending JSON chunk request: {cx},{cz}")
            await self.ws_proto.send_json({
                "msg": "get_chunk",
                "x": cx,
                "z": cz,
                "lod": 0
            })
        logging.debug(f"Requested chunk ({cx},{cz})")

    async def _on_binary_message(self, data: bytes):
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
                case MessageType.CHUNK_DATA:
                    # TODO: also need fix for valid chunk generation
                    # see local generate_chunk_data(cx, cz, chunk_size, spacing)
                    reader = BinaryReader(msg.payload)
                    cx = reader.read_int32()
                    cz = reader.read_int32()
                    size = reader.read_int32()
                    vertices = numpy.frombuffer(reader.read_bytes(reader.read_uint32()), dtype=numpy.float32).reshape(-1, 6)
                    indices = numpy.frombuffer(reader.read_bytes(reader.read_uint32()), dtype=numpy.uint32)
                    tree_count = reader.read_uint32()
                    trees = []
                    for _ in range(tree_count):
                        trees.append({
                            'x': reader.read_float(),
                            'z': reader.read_float(),
                            'type': reader.read_uint8()
                        })
                    self._queue_chunks.put((cx, cz, vertices, indices, trees))
                    logging.debug(f"Received chunk ({cx},{cz}) with {len(vertices)} vertices")
                case MessageType.PLAYERS_UPDATE:
                    reader = BinaryReader(msg.payload)
                    plid = reader.read_uint64()
                    if plid == self.player.get_id():
                        return
                    x, y, z = reader.read_vector3()
                    yaw = reader.read_float()
                    health = reader.read_float()
                    max_health = reader.read_float()
                    name = reader.read_string()
                    timestamp = reader.read_uint64()
                    with self.remote_players_lock:
                        if plid in self.remote_players:
                            self.remote_players[plid].update((x, y, z), yaw, health, max_health)
                        else:
                            self.remote_players[plid] = RemotePlayer(plid, name, (x, y, z), yaw, health, max_health)
                case MessageType.PLAYER_SPAWN:
                    reader = BinaryReader(msg.payload)
                    plid = reader.read_uint64()
                    name = reader.read_string()
                    x, y, z = reader.read_vector3()
                    yaw = reader.read_float()
                    health = reader.read_float()
                    max_health = reader.read_float()
                    if plid != self.player.get_id():
                        with self.remote_players_lock:
                            self.remote_players[plid] = RemotePlayer(plid, name, (x, y, z), yaw, health, max_health)
                case MessageType.PLAYER_DESPAWN:
                    reader = BinaryReader(msg.payload)
                    plid = reader.read_uint64()
                    with self.remote_players_lock:
                        if plid in self.remote_players:
                            del self.remote_players[plid]
                case MessageType.AUTHENTICATION:
                    reader = BinaryReader(msg.payload)
                    success = reader.read_uint8() != 0
                    player_id = reader.read_uint64()
                    message = reader.read_string()
                    if success:
                        logging.info(f"Authentication successful: {message}")
                        self.authenticated = True
                        self.player.set_id(player_id)
                    else:
                        logging.error(f"Authentication failed: {message}")
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

    def _on_text_message(self, text: str):
        try:
            data = json.loads(text)
            msg_type = data.get("msg")
            match msg_type:
                case "get_chunk":
                    cx = data.get("x", 0)
                    cz = data.get("z", 0)
                    logging.debug(f"Chunk ({cx},{cz}) data keys: {list(data.keys())}")
                    size = data.get("size", 32) # chunk size
                    vertices_raw = data.get("vertices", [])
                    indices_raw = data.get("indices", [])
                    if len(vertices_raw) == 0 or len(indices_raw) == 0:
                        logging.warning(f"Chunk ({cx},{cz}) has NO vertices or indices!")
                        return
                    if len(vertices_raw) % 6 != 0:
                        logging.error(f"Chunk ({cx},{cz}) vertices length {len(vertices_raw)} not divisible by 6!")
                        if isinstance(vertices_raw[0], list):
                            vertices = numpy.array(vertices_raw, dtype=numpy.float32)
                        else:
                            vertices = numpy.array(vertices_raw, dtype=numpy.float32).reshape(-1, 1)
                    else:
                        vertices = numpy.array(vertices_raw, dtype=numpy.float32).reshape(-1, 6)
                    indices = numpy.array(indices_raw, dtype=numpy.uint32)
                    spacing = 1.0
                    phys_width = (size - 1) * spacing
                    phys_height = (size - 1) * spacing
                    world_origin_x = cx * phys_width
                    world_origin_z = cz * phys_height
                    stones = []
                    trees = []
                    rng = random.Random((cx * 1000003) ^ (cz * 1000033))
                    num_items = rng.randint(5, 10)
                    for _ in range(num_items):
                        x = float(world_origin_x + rng.uniform(1.5, phys_width - 1.5))
                        z = float(world_origin_z + rng.uniform(1.5, phys_height - 1.5))
                        y_val = float(vertices[0, 1]) if len(vertices) > 0 else 0.0
                        trunk_height = float(rng.uniform(1.8, 2.2))
                        foliage_radius = float(rng.uniform(1.0, 1.4))
                        rotation_y = float(rng.uniform(0, 2 * math.pi))
                        stones.append({
                            'x': x, 'y': y_val, 'z': z,
                            'trunk_height': trunk_height,
                            'foliage_radius': foliage_radius,
                            'rotation_y': rotation_y
                        })
                        trees.append({
                            'x': x+.5, 'y': y_val, 'z': z+.5,
                            'trunk_height': trunk_height,
                            'foliage_radius': foliage_radius,
                            'rotation_y': rotation_y
                        })
                    PORTAL_PROBABILITY = 0.1
                    portal = None
                    if rng.random() < PORTAL_PROBABILITY:
                        margin = 2.0
                        x = float(world_origin_x + rng.uniform(margin, phys_width - margin))
                        z = float(world_origin_z + rng.uniform(margin, phys_height - margin))
                        y_val = float(vertices[0, 1]) if len(vertices) > 0 else 0.0
                        portal = {
                            'name': f"{int(round(x))}_{int(round(y_val))}_{int(round(z))}",
                            'x': x, 'z': z,
                            'rotation_y': float(rng.uniform(0, 2 * math.pi)),
                            'scale': float(rng.uniform(0.9, 1.1))
                        }
                    logging.debug(f"Chunk ({cx},{cz}): {len(vertices)} verts, {len(indices)} indices, format: {vertices.shape}")
                    self._queue_chunks.put((cx, cz, vertices, indices, stones, trees, portal))
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
                case "authentication":
                    player_id = data.get("player_id", 0)
                    description = data.get("desc", "")
                    if player_id:
                        logging.info(f"Authentication successful: {description}")
                        self.authenticated = True
                        self.player.set_id(player_id)
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

    def stop(self):
        self._stop_event.set()
        if self._thread.is_alive():
            self._thread.join(timeout=2.0)

    def is_connected(self):
        return not self._stop_event.is_set() and self.ws_proto and self.ws_proto.client and not self.ws_proto.client._closed

    def get_remote_players_snapshot(self):
        with self.remote_players_lock:
            return dict(self.remote_players)
