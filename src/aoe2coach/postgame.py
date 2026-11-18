"""Estadisticas finales de la partida (pantalla de resultados).

Al acabar, el juego anade al archivo un bloque con la tabla de puntuaciones:
quien gano, los tiempos de edad de CADA jugador, los recursos recogidos, las
bajas y el maximo de aldeanos. Todo esto es OBSERVADO: lo escribe el juego, no
se estima.

No siempre esta. Si el jugador cierra antes de que acabe la partida, o la
grabacion se corta, el bloque falta y `read` devuelve None. El resto del
analisis no depende de el.

Estructura: `mgz.body.achievements` (MIT), que documenta el bloque de
UserPatch 1.4+ que DE sigue escribiendo.
"""
from __future__ import annotations

import warnings
from dataclasses import dataclass

from .replay import Replay

# Un tiempo de edad que el juego no alcanzo viene como -1 o como un valor absurdo.
_MAX_AGE_S = 6 * 3600


@dataclass(frozen=True)
class Stats:
    """Lo que el juego anoto de un jugador al acabar."""
    slot: int                  # posicion en la tabla final (1..n)
    name: str
    victory: bool
    civ_id: int
    color_id: int
    team: int
    score: int
    # militar
    units_killed: int
    units_lost: int
    buildings_razed: int
    buildings_lost: int
    units_converted: int
    # economia: recogido de verdad, no estimado
    food: int
    wood: int
    stone: int
    gold: int
    tribute_sent: int
    tribute_received: int
    trade_gold: int
    relic_gold: int
    # tecnologia
    feudal_s: int | None
    castle_s: int | None
    imperial_s: int | None
    explored_pct: int
    research_count: int
    research_pct: int
    # sociedad
    wonders: int
    castles: int
    relics: int
    villager_high: int

    @property
    def collected(self) -> int:
        return self.food + self.wood + self.stone + self.gold

    def age_s(self, age: str) -> int | None:
        return {"Feudal": self.feudal_s, "Castle": self.castle_s, "Imperial": self.imperial_s}.get(age)


@dataclass(frozen=True)
class Postgame:
    duration_s: int
    complete: bool
    players: tuple[Stats, ...]

    def by_color(self, color_id: int) -> Stats | None:
        return next((p for p in self.players if p.color_id == color_id), None)

    def by_name(self, name: str) -> Stats | None:
        return next((p for p in self.players if p.name == name), None)

    def winners(self) -> tuple[Stats, ...]:
        return tuple(p for p in self.players if p.victory)


def _age(value: int | None) -> int | None:
    if value is None or value < 0 or value > _MAX_AGE_S:
        return None
    return int(value)


def _parse(body: bytes) -> Postgame | None:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        from mgz.body.actions import postgame as struct_postgame
    for skip in (0, 1, 2, 3, 4):           # el desplazamiento exacto varia entre versiones
        try:
            raw = struct_postgame.parse(body[skip:])
        except Exception:
            continue
        if not 1 <= int(raw.player_num) <= 8:
            continue
        players = []
        for i, p in enumerate(raw.achievements, start=1):
            name = bytes(p.player_name).split(b"\x00")[0].decode("latin-1", "replace").strip()
            players.append(Stats(
                slot=i, name=name, victory=bool(p.victory), civ_id=int(p.civilization),
                color_id=int(p.color_id), team=int(p.team), score=int(p.total_score),
                units_killed=int(p.military.units_killed), units_lost=int(p.military.units_lost),
                buildings_razed=int(p.military.buildings_razed), buildings_lost=int(p.military.buildings_lost),
                units_converted=int(p.military.units_converted),
                food=int(p.economy.food_collected), wood=int(p.economy.wood_collected),
                stone=int(p.economy.stone_collected), gold=int(p.economy.gold_collected),
                tribute_sent=int(p.economy.tribute_sent), tribute_received=int(p.economy.tribute_received),
                trade_gold=int(p.economy.trade_gold), relic_gold=int(p.economy.relic_gold),
                feudal_s=_age(int(p.technology.feudal_time_int)),
                castle_s=_age(int(p.technology.castle_time_int)),
                imperial_s=_age(int(p.technology.imperial_time_int)),
                explored_pct=int(p.technology.explored_percent),
                research_count=int(p.technology.research_count),
                research_pct=int(p.technology.research_percent),
                wonders=int(p.society.total_wonders), castles=int(p.society.total_castles),
                relics=int(p.society.relics_captured), villager_high=int(p.society.villager_high)))
        if not players or all(p.score == 0 and p.collected == 0 for p in players):
            continue
        return Postgame(duration_s=int(raw.duration_int), complete=bool(raw.complete),
                        players=tuple(players))
    return None


def read(replay: Replay) -> Postgame | None:
    """Estadisticas finales, o None si la grabacion no las trae."""
    for e in reversed(replay.events):
        if e.kind == "action" and e.action == "POSTGAME" and e.raw:
            if (pg := _parse(e.raw)) is not None:
                return pg
    return None
