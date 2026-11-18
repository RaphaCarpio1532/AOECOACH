"""Lo militar: que pidio cada jugador, que contrarrestaba a que, y como acabo.

La grabacion guarda las ordenes de TODOS los jugadores, no solo las tuyas. Y
cada sincronizacion trae, por jugador, los recursos almacenados y cuantos
objetos tiene en el mapa. Con eso se puede contar la partida de los dos lados
sin estimar nada del rival.

Los contraataques NO son opinion: cada unidad del juego lleva sus clases de
armadura y sus bonus de ataque contra clases. Si tu unidad tiene un bonus
contra una clase que la suya lleva en la armadura, la contrarresta, y el numero
sale de la tabla del juego.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field

from . import refdata
from .replay import Replay

QUEUE_ACTIONS = {"QUEUE", "DE_QUEUE", "MULTIQUEUE", "MAKE"}
# Clases de armadura que lleva casi todo: no distinguen nada, no son un contraataque.
BASE_ARMOUR_CLASSES = {3, 4, 31, 19}
MIN_BONUS = 1


@dataclass
class Production:
    """Lo que un jugador pidio producir, por tipo de unidad."""
    player: int
    ordered: Counter = field(default_factory=Counter)        # unit_id -> unidades pedidas
    first: dict = field(default_factory=dict)                # unit_id -> primer instante
    timeline: list = field(default_factory=list)             # (t, unit_id, cantidad)

    def military(self) -> Counter:
        return Counter({u: n for u, n in self.ordered.items()
                        if u not in refdata.VILLAGER_IDS and _is_unit(u)})

    def villagers(self) -> int:
        return sum(n for u, n in self.ordered.items() if u in refdata.VILLAGER_IDS)


def _is_unit(unit_id: int) -> bool:
    return str(unit_id) in refdata._tree()["Unit"]


def production(replay: Replay) -> dict[int, Production]:
    out: dict[int, Production] = {}
    for e in replay.events:
        if e.kind != "action" or e.action not in QUEUE_ACTIONS or e.player is None:
            continue
        unit = e.payload.get("unit_id")
        if unit is None:
            continue
        amount = int(e.payload.get("amount", 1) or 1)
        p = out.setdefault(e.player, Production(e.player))
        p.ordered[unit] += amount
        p.first.setdefault(unit, e.t_ms)
        p.timeline.append((e.t_ms, unit, amount))
    return out


# ------------------------------------------------------------------ contraataques

def _armour_classes(unit_id: int) -> set[int]:
    u = refdata._tree()["Unit"].get(str(unit_id))
    if not u:
        return set()
    return {a["Class"] for a in u.get("Armours", [])} - BASE_ARMOUR_CLASSES


def _bonuses(unit_id: int) -> dict[int, int]:
    u = refdata._tree()["Unit"].get(str(unit_id))
    if not u:
        return {}
    return {a["Class"]: a["Amount"] for a in u.get("Attacks", [])
            if a["Amount"] >= MIN_BONUS and a["Class"] not in BASE_ARMOUR_CLASSES}


@dataclass(frozen=True)
class Counterplay:
    attacker: int          # unidad que contrarresta
    target: int            # unidad contrarrestada
    bonus: int             # dano extra por golpe, de la tabla del juego

    @property
    def attacker_name(self) -> str:
        return refdata.object_name(self.attacker)

    @property
    def target_name(self) -> str:
        return refdata.object_name(self.target)


def counters(attacker_ids, target_ids) -> list[Counterplay]:
    """Que unidad de las primeras hace dano extra a cual de las segundas."""
    out = []
    for a in attacker_ids:
        bon = _bonuses(a)
        if not bon:
            continue
        for t in target_ids:
            if t == a:
                continue
            hit = [bon[c] for c in _armour_classes(t) if c in bon]
            if hit:
                out.append(Counterplay(a, t, max(hit)))
    return sorted(out, key=lambda c: -c.bonus)


# ------------------------------------------------------------------ fuerza en el mapa

@dataclass
class Curves:
    """Series por jugador tomadas de las sincronizaciones de la grabacion."""
    objects: dict[int, list[tuple[float, int]]] = field(default_factory=lambda: defaultdict(list))
    stock: dict[int, list[tuple[float, int]]] = field(default_factory=lambda: defaultdict(list))


def curves(replay: Replay, every_ms: int = 15000) -> Curves:
    c = Curves()
    last: dict[int, float] = {}
    for e in replay.events:
        if e.kind != "sync":
            continue
        for pid, vals in e.payload.items():
            if not isinstance(pid, int) or not isinstance(vals, dict):
                continue
            if e.t_ms - last.get(pid, -every_ms) < every_ms:
                continue
            last[pid] = e.t_ms
            c.objects[pid].append((float(e.t_ms), int(vals.get("obj_count", 0))))
            c.stock[pid].append((float(e.t_ms), int(vals.get("total_res", 0))))
    return c


# ------------------------------------------------------------------ el desenlace

@dataclass
class Ending:
    resign_t: float | None = None
    resign_player: int | None = None
    last_push_start: float | None = None      # primer aviso de la ultima tanda de ataques
    push_warnings: int = 0


def ending(replay: Replay, player: int, attacks: list[int], gap_ms: int = 150_000) -> Ending:
    end = Ending()
    for e in replay.events:
        if e.kind == "action" and e.action == "RESIGN":
            who = e.payload.get("player_id")
            if end.resign_t is None or e.t_ms > end.resign_t:
                end.resign_t, end.resign_player = float(e.t_ms), who
    if attacks:
        run = [attacks[-1]]
        for t in reversed(attacks[:-1]):
            if run[-1] - t <= gap_ms:
                run.append(t)
            else:
                break
        end.last_push_start = float(min(run))
        end.push_warnings = len(run)
    return end
