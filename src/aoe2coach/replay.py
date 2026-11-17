"""Lectura de archivos .aoe2record (Age of Empires II: Definitive Edition).

Capa 1 del sistema: convierte bytes en hechos observados. No calcula metricas.

Procedencia del conocimiento del formato
- Cuerpo (operaciones y acciones): decodificadores de `mgz.fast` (aoc-mgz, MIT,
  happyleavesaoc). Se usan tal cual; aqui solo se recorre el contenedor.
- Cabecera minima (ajustes y jugadores): esquema de `aoe2rec` (MIT, aoe2ct),
  archivo crates/aoe2rec/src/header/mod.rs, que cubre guardados 68.9.
  `mgz` 1.8.51 no lee cabeceras posteriores a 66.6, por eso no se usa aqui.

Todo lo que este modulo devuelve es un HECHO OBSERVADO en el archivo, salvo
los campos marcados como desconocidos.
"""
from __future__ import annotations

import io
import struct
import warnings
import zlib
from dataclasses import dataclass, field
from typing import Iterator, NamedTuple

with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    from mgz import fast
    from mgz.fast.enums import Action

READER_VERSION = "0.1.0"
# Versiones de guardado contra las que este lector se ha comprobado con un
# archivo real. Fuera de esta lista el cuerpo suele leerse, pero no se promete.
VERIFIED_SAVE_VERSIONS = {(68, 9)}
MIN_HEADER_MAJOR = 67  # el esquema de jugador usado abajo asume >= 67


class UnsupportedReplay(Exception):
    """El archivo no se puede leer con garantias. Nunca se devuelven datos a medias."""


@dataclass(frozen=True)
class Player:
    number: int           # numero de jugador dentro de la partida (1..8)
    name: str
    civ_id: int
    color_id: int
    team_id: int
    is_ai: bool
    profile_id: int


@dataclass(frozen=True)
class Header:
    game: str
    save_major: int
    save_minor: int
    build: int
    timestamp: int                 # epoch Unix del inicio de la partida
    map_id: int
    map_size: int
    speed: float
    population_limit: int
    multiplayer: bool
    cheats: bool
    players: tuple[Player, ...]

    @property
    def save_version(self) -> str:
        return f"{self.save_major}.{self.save_minor}"


@dataclass(frozen=True)
class Event:
    """Una operacion del cuerpo, con trazabilidad al byte de origen."""
    t_ms: int              # tiempo de juego acumulado (suma de SYNC)
    kind: str              # "action" | "chat" | "sync"
    offset: int            # posicion en el archivo: permite auditar cada evento
    action: str | None = None
    player: int | None = None
    payload: dict = field(default_factory=dict)
    raw: bytes = b""


class _R:
    def __init__(self, data: bytes):
        self.b = io.BytesIO(data)

    def take(self, fmt: str):
        size = struct.calcsize(fmt)
        chunk = self.b.read(size)
        if len(chunk) != size:
            raise UnsupportedReplay("cabecera truncada")
        out = struct.unpack(fmt, chunk)
        return out[0] if len(out) == 1 else out

    def skip(self, n: int):
        self.b.seek(n, 1)

    def magic(self, expected: bytes, where: str):
        got = self.b.read(len(expected))
        if got != expected:
            raise UnsupportedReplay(
                f"separador inesperado en {where}: {got.hex()} (se esperaba {expected.hex()})")

    def de_string(self, where: str) -> str:
        self.magic(b"\x60\x0a", where)
        n = self.take("<H")
        return self.b.read(n).decode("utf-8", "replace")


def read_header(data: bytes) -> tuple[Header, int]:
    """Devuelve (cabecera, offset donde empieza el cuerpo)."""
    if len(data) < 16:
        raise UnsupportedReplay("archivo demasiado corto")
    header_end, = struct.unpack_from("<I", data, 0)
    if not 16 < header_end <= len(data):
        raise UnsupportedReplay("longitud de cabecera invalida")
    try:
        raw = zlib.decompress(data[8:header_end], wbits=-15)
    except zlib.error as exc:
        raise UnsupportedReplay(f"cabecera no descomprimible: {exc}") from exc

    nul = raw.find(b"\x00")
    game = raw[:nul].decode("ascii", "replace")
    r = _R(raw[nul + 1:])
    save = r.take("<f")
    if save != -1.0:
        raise UnsupportedReplay(f"formato anterior a DE moderno (save={save})")
    minor_raw, major = r.take("<HH")
    minor = round(minor_raw / 6553.6)
    if major < MIN_HEADER_MAJOR:
        raise UnsupportedReplay(f"guardado {major}.{minor}: cabecera no soportada (< {MIN_HEADER_MAJOR})")
    build, timestamp = r.take("<Ii")
    r.skip(8)                                   # version_2, interval_version

    r.take("<I")                                # game_options_version
    n_dlc = r.take("<I")
    r.skip(4 * n_dlc)
    r.take("<i")                                # dificultad
    map_size, _selected_map, map_id = r.take("<III")
    r.skip(4 * 6)                               # reveal, victoria, recursos, edades, tipo
    r.magic(b"\xa3_\x02\x00\xa3_\x02\x00", "ajustes/velocidad")
    speed, _treaty, pop_limit, n_players = r.take("<fIII")
    r.skip(4 + 1 + 4)                           # color libre, desconocido, cantidad victoria
    r.magic(b"\xa3_\x02\x00", "ajustes/opciones")
    r.skip(5)                                   # trade, team bonus, random pos, all techs, starting units
    _lock_teams, _lock_speed, multiplayer, cheats = r.take("<4b")
    r.skip(6)                                   # record, animals, predators, turbo, shared expl, team pos
    r.skip(4 + 4 + 1 + 1)                       # sub modo, battle royale, handicap, desconocido
    r.magic(b"\xa3_\x02\x00", "ajustes/jugadores")
    if not 1 <= n_players <= 8:
        raise UnsupportedReplay(f"numero de jugadores imposible: {n_players}")

    players = []
    for i in range(n_players):
        w = f"jugador[{i}]"
        r.take("<I")                            # dlc_id
        color_id = r.take("<i")
        _sel_color, _sel_team, team_id = r.take("<3B")
        r.skip(4 + 4 + 1)                       # checksum datamod, crc dat, version mp
        civ_id = r.take("<I")
        r.skip(4 * r.take("<I"))                # civs personalizadas
        ai_type = r.de_string(w)
        r.skip(1)
        ai_name = r.de_string(w)
        r.de_string(w)                          # nombre censurado
        name = r.de_string(w)
        player_type = r.take("<I")
        profile_id = r.take("<i")
        r.skip(4)
        number = r.take("<i")
        r.skip(1 + 1 + 4 + 4 + 4)               # prefer random, custom ai, handicap, de64
        r.de_string(w)                          # de67
        players.append(Player(
            number=number, name=name or ai_name, civ_id=civ_id, color_id=color_id,
            team_id=team_id, is_ai=(player_type == 4 or bool(ai_type)), profile_id=profile_id))

    return Header(game=game, save_major=major, save_minor=minor, build=build,
                  timestamp=timestamp, map_id=map_id, map_size=map_size, speed=speed,
                  population_limit=pop_limit, multiplayer=bool(multiplayer),
                  cheats=bool(cheats), players=tuple(players)), header_end


def _decode_action(aid: int, body: bytes) -> tuple[str, int | None, dict]:
    try:
        action = Action(aid)
    except ValueError:
        return f"UNKNOWN_{aid}", (body[0] if body else None), {}
    payload: dict = {}
    try:
        payload = fast.parse_action(action, body)
    except Exception:  # un payload ilegible no invalida la partida, se conserva el crudo
        payload = {"_decode_error": True}
    player = payload.get("player_id", body[0] if body else None)
    # `mgz` descarta el tipo de edificio de DE_QUEUE; es clave para saber QUE
    # edificio produce, asi que se recupera del crudo (formato >= 71094).
    if action is Action.DE_QUEUE and len(body) >= 15 and len(body) == struct.unpack_from("<h", body, 1)[0] + 3:
        payload["building_type"] = struct.unpack_from("<h", body, 9)[0]
    return action.name, player, payload


def read_events(data: bytes, body_start: int, with_sync: bool = False) -> Iterator[Event]:
    """Recorre el cuerpo. Lanza UnsupportedReplay ante cualquier byte no entendido."""
    f = io.BytesIO(data)
    f.seek(body_start)
    fast.meta(f)
    t = 0
    size = len(data)
    while True:
        pos = f.tell()
        head = f.read(4)
        if len(head) < 4:
            return
        op, = struct.unpack("<I", head)
        try:
            if op == 1:
                length, = struct.unpack("<I", f.read(4))
                if length < 1 or pos + 8 + length > size:
                    raise UnsupportedReplay(f"accion con longitud invalida en 0x{pos:x}")
                aid = f.read(1)[0]
                body = f.read(length - 1)
                f.read(4)
                name, player, payload = _decode_action(aid, body)
                yield Event(t, "action", pos, name, player, payload, body)
            elif op == 2:
                inc, _checksum, payload = fast.sync(f)
                t += inc
                if with_sync and payload:
                    yield Event(t, "sync", pos, payload=payload)
            elif op == 3:
                fast.viewlock(f)
            elif op == 4:
                msg = fast.chat(f)
                yield Event(t, "chat", pos, payload={"text": msg.decode("utf-8", "replace")})
            elif op == 6:
                return  # bloque de fin de partida
            else:
                raise UnsupportedReplay(f"operacion desconocida {op} en 0x{pos:x} (t={t} ms)")
        except struct.error as exc:
            raise UnsupportedReplay(f"cuerpo truncado en 0x{pos:x}") from exc


@dataclass
class Replay:
    path: str
    header: Header
    events: list[Event]
    duration_ms: int
    verified_version: bool

    def player(self, number: int) -> Player:
        for p in self.header.players:
            if p.number == number:
                return p
        raise KeyError(number)


class MapObject(NamedTuple):
    owner: int          # 0 = naturaleza (Gaia)
    object_id: int      # tipo de objeto
    class_id: int
    x: float
    y: float


def load_objects(path: str) -> dict[int, MapObject]:
    """Objetos iniciales del mapa por id de instancia.

    Usa el lector de cabecera de `mgz-fast` 1.0.0 (MIT), copiado en _vendor porque
    su paquete choca de nombre con `mgz`. Si esa cabecera no se entiende devuelve
    un diccionario vacio: el resto del analisis sigue, sin reparto por recurso.
    """
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            from ._vendor import mgzfast_header
            with open(path, "rb") as fh:
                header = mgzfast_header.parse(fh)
        return {o["instance_id"]: MapObject(p["number"], o["object_id"], o["class_id"],
                                            o["position"]["x"], o["position"]["y"])
                for p in header["players"] for o in p["objects"]}
    except Exception:
        return {}


def load(path: str, with_sync: bool = False) -> Replay:
    with open(path, "rb") as fh:
        data = fh.read()
    header, body_start = read_header(data)
    events = list(read_events(data, body_start, with_sync=with_sync))
    duration = max((e.t_ms for e in events), default=0)
    return Replay(path=path, header=header, events=events, duration_ms=duration,
                  verified_version=(header.save_major, header.save_minor) in VERIFIED_SAVE_VERSIONS)
