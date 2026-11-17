"""Que hace cada aldeano: modelo de asignacion a recursos.

[ESTIMADO] Todo este modulo es un modelo. Sus reglas son hipotesis sobre el
comportamiento del juego y se contrastan contra un hecho duro (las compras
aceptadas) en `economy.analyze`.

Piezas
- Registro de edificios propios: cada orden de construir da tipo y posicion.
  Una orden posterior cuyo clic cae en esa posicion apunta a ese edificio, y
  desde ese momento su id de instancia queda identificado.
- Conjunto de aldeanos: los iniciales, todo el que construye algo y todo el
  que recibe una orden de recoger. Asi las ordenes al ejercito no cuentan.
- Reglas de tarea (ver `Rules`): cada una se puede activar o desactivar para
  medir si mejora o empeora el acuerdo con las compras.
"""
from __future__ import annotations

from bisect import bisect_right
from collections import Counter
from dataclasses import dataclass, field

from . import refdata
from .replay import MapObject, Replay

RES = ("Food", "Wood", "Gold", "Stone")
FARM = 50
# Puntos de entrega y los recursos que se recogen junto a ellos.
DROP_SITES = {
    68: ("Food",),                           # molino
    562: ("Wood",),                          # campamento maderero
    584: ("Gold", "Stone"),                  # campamento minero
    1808: ("Wood", "Gold", "Stone", "Food"), # carro de mulas (armenios y georgianos)
}
TOWN_CENTERS = refdata.TOWN_CENTER_IDS
MATCH_RADIUS = 0.75          # casillas entre el clic y el centro del edificio
AUTO_GATHER_RADIUS = 6.0     # casillas alrededor de un punto de entrega
FARM_BURST_MS = 15_000       # granjas encadenadas al mismo grupo
FOOD_ANIMALS = {"Goose", "Deer", "Sheep", "Wild Boar", "Boar", "Turkey", "Cow", "Llama", "Pig",
                "Javelina", "Elephant", "Rhinoceros", "Zebra", "Ostrich", "Ibex", "Goat"}
MILITARY_ACTIONS = {"PATROL", "DE_ATTACK_MOVE", "FORMATION", "DE_RETREAT", "ATTACK_GROUND"}


def resource_of(object_id: int, class_id: int | None = None) -> str | None:
    name = refdata.object_name(object_id)
    if name.startswith("Tree"):
        return "Wood"
    if name == "Gold Mine":
        return "Gold"
    if name == "Stone Mine":
        return "Stone"
    if object_id == FARM or name in ("Fruit Bush", "Forage Bush", "Farm") or name in FOOD_ANIMALS:
        return "Food"
    if class_id == 70 and name.startswith("objeto#"):
        return "Food"        # animal sin nombre en la tabla, usado como objetivo de recoleccion: inferido
    return None


@dataclass(frozen=True)
class Rules:
    """Hipotesis de comportamiento. Los valores por defecto son los que mejor
    encajan con las compras de la partida de prueba (ver docs/03)."""
    drop_site_auto_gather: bool = True   # quien termina un punto de entrega recoge lo que tiene al lado
    return_after_building: bool = True   # quien termina otro edificio vuelve a su tarea anterior
    dropoff_keeps_task: bool = True      # llevar carga a un punto de entrega no cambia la tarea
    farm_burst_split: bool = True        # n granjas encadenadas ocupan a n constructores, no a uno


@dataclass
class Building:
    kind: int
    x: float
    y: float
    t: int
    instance: int | None = None


@dataclass
class Allocation:
    times: list[int] = field(default_factory=list)
    counts: list[dict] = field(default_factory=list)   # {recurso | None: aldeanos} tras cada cambio
    villagers: int = 0
    matched_orders: int = 0
    unmatched_orders: int = 0
    rules: Rules = field(default_factory=Rules)

    def at(self, t: float) -> dict:
        i = bisect_right(self.times, t) - 1
        return self.counts[i] if i >= 0 else {}

    def shares(self, t: float) -> tuple[dict, float]:
        c = self.at(t)
        known = sum(v for k, v in c.items() if k)
        total = sum(c.values())
        if not known:
            return {}, 0.0
        return {r: c.get(r, 0) / known for r in RES}, known / total


class _World:
    def __init__(self, objects: dict[int, MapObject], player: int):
        self.objects = objects
        self.player = player
        self.buildings: list[Building] = []
        self.by_instance: dict[int, Building] = {}
        self.resources = [(o.x, o.y, r) for o in objects.values()
                          if o.owner == 0 and (r := resource_of(o.object_id, o.class_id))]
        for iid, o in objects.items():
            if o.owner == player and o.class_id == 80:
                b = Building(o.object_id, o.x, o.y, 0, iid)
                self.buildings.append(b)
                self.by_instance[iid] = b

    def place(self, kind: int, x: float, y: float, t: int):
        self.buildings.append(Building(kind, x, y, t))

    def resolve(self, target: int, x: float, y: float) -> Building | None:
        if target in self.by_instance:
            return self.by_instance[target]
        best, dist = None, MATCH_RADIUS
        for b in self.buildings:
            d = ((b.x - x) ** 2 + (b.y - y) ** 2) ** 0.5
            if b.instance is None and d <= dist:
                best, dist = b, d
        if best is not None and target > 0:
            best.instance = target
            self.by_instance[target] = best
        return best

    def nearby_resource(self, x: float, y: float, allowed: tuple[str, ...]) -> str | None:
        best, dist = None, AUTO_GATHER_RADIUS ** 2
        for rx, ry, r in self.resources:
            if r in allowed:
                d = (rx - x) ** 2 + (ry - y) ** 2
                if d < dist:
                    best, dist = r, d
        return best

    def gaia_resource(self, target: int) -> str | None:
        o = self.objects.get(target)
        if o is None:
            return None
        res = resource_of(o.object_id, o.class_id)
        if o.owner == 0 or (res == "Food" and o.class_id == 70):   # el ganado ya capturado tiene dueño
            return res
        return None


def _villager_ids(replay: Replay, player: int, world: _World) -> set[int]:
    ids = {i for i, o in world.objects.items() if o.owner == player and o.object_id in refdata.VILLAGER_IDS}
    # Objetos de tipo conocido que no son aldeanos: los del mapa inicial (TC,
    # explorador, ovejas) y los edificios que producen o investigan.
    not_villager = {i for i, o in world.objects.items() if o.object_id not in refdata.VILLAGER_IDS}
    military: set[int] = set()
    for e in replay.events:
        if e.kind != "action" or e.player != player:
            continue
        sel = e.payload.get("object_ids") or []
        if e.action == "BUILD":
            ids.update(sel)
        elif e.action == "ORDER" and world.gaia_resource(e.payload.get("target_id", -1)):
            ids.update(sel)
        elif e.action in MILITARY_ACTIONS:
            military.update(sel)
        elif e.action in ("DE_QUEUE", "RESEARCH", "GATHER_POINT"):
            not_villager.update(sel)
    return ids - not_villager - (military - {i for i, o in world.objects.items() if o.owner == player})


def allocate(replay: Replay, player: int, objects: dict[int, MapObject],
             creations: list[tuple[float, int]], rules: Rules = Rules()) -> Allocation:
    """creations: (instante, TC) de cada aldeano creado.
    Supuestos que no dependen de `rules`: un aldeano sigue en su ultima tarea
    conocida; uno nuevo va al recurso del punto de reunion de su TC; no muere
    nadie; las tareas cambian al dar la orden, no al llegar."""
    world = _World(objects, player)
    villagers = _villager_ids(replay, player, world)
    task: dict[int, str | None] = {i: None for i in villagers if i in objects}
    anon: list[str | None] = []
    rally: dict[int, str | None] = {}
    farm_bursts: dict[tuple, list[int]] = {}
    out = Allocation(rules=rules)

    debt = 0   # aldeanos vistos antes de que el modelo los cree: no se cuentan dos veces

    def identify(vid: int):
        nonlocal debt
        if vid in task:
            return
        if anon:   # el aldeano recien visto sale del grupo sin identificar: primero uno sin tarea
            anon.pop(anon.index(None) if None in anon else 0)
        else:
            debt += 1
        task[vid] = None

    def snapshot(t: float):
        out.times.append(int(t))
        out.counts.append(dict(Counter(task.values()) + Counter(anon)))

    merged: list[tuple[float, int, object]] = [(t, 0, tc) for t, tc in creations]
    merged += [(e.t_ms, 1, e) for e in replay.events if e.kind == "action" and e.player == player
               and e.action in ("GATHER_POINT", "ORDER", "BUILD", "MOVE", "STOP", "DE_QUEUE", "RESEARCH")]
    merged.sort(key=lambda x: (x[0], x[1]))
    snapshot(0)
    for t, kind, obj in merged:
        if kind == 0:
            if debt:
                debt -= 1
            else:
                anon.append(rally.get(obj))
            snapshot(t)
            continue
        e = obj
        p = e.payload
        sel = [i for i in (p.get("object_ids") or [])]
        if e.action == "DE_QUEUE":                     # identifica edificios de produccion
            for b in sel:
                if b not in world.by_instance and p.get("building_type", -1) > 0:
                    world.by_instance[b] = Building(p["building_type"], -1, -1, t, b)
            continue
        if e.action == "RESEARCH":
            continue
        if e.action == "GATHER_POINT":
            tid = p.get("target_id", -1)
            res = world.gaia_resource(tid)
            if res is None and p.get("target_type", -1) == FARM:
                res = "Food"
            for b in sel:
                rally[b] = res
            continue
        vills = [i for i in sel if i in villagers]
        if not vills:
            continue
        if e.action == "BUILD":
            kind_id = p.get("building_id", -1)
            world.place(kind_id, p["x"], p["y"], t)
            for vid in vills:
                identify(vid)
            if kind_id == FARM:
                key = tuple(sorted(vills))
                burst = [x for x in farm_bursts.get(key, []) if t - x <= FARM_BURST_MS] + [t]
                farm_bursts[key] = burst
                n = len(burst) if rules.farm_burst_split else 1
                for i, vid in enumerate(vills):
                    task[vid] = "Food" if i < n else None
            elif kind_id in DROP_SITES and rules.drop_site_auto_gather:
                res = world.nearby_resource(p["x"], p["y"], DROP_SITES[kind_id])
                for vid in vills:
                    task[vid] = res
            elif not rules.return_after_building:
                for vid in vills:
                    task[vid] = None
        elif e.action == "ORDER":
            tid = p.get("target_id", -1)
            res = world.gaia_resource(tid)
            if res:
                for vid in vills:
                    identify(vid)
                    task[vid] = res
            else:
                b = world.resolve(tid, p.get("x", -1), p.get("y", -1))
                if b is None:
                    out.unmatched_orders += 1
                    for vid in vills:
                        identify(vid)
                        task[vid] = None          # objetivo ajeno: atacar, huir, guarnecer en otra parte
                else:
                    out.matched_orders += 1
                    for vid in vills:
                        identify(vid)
                    if b.kind == FARM:
                        for vid in vills:
                            task[vid] = "Food"
                    elif b.kind in DROP_SITES or b.kind in TOWN_CENTERS:
                        if b.t > 0 and b.t >= t - 120_000 and b.kind in DROP_SITES and rules.drop_site_auto_gather:
                            res = world.nearby_resource(b.x, b.y, DROP_SITES[b.kind])
                            for vid in vills:
                                task[vid] = res
                        elif not rules.dropoff_keeps_task:
                            for vid in vills:
                                task[vid] = None
                    elif not rules.return_after_building:
                        for vid in vills:
                            task[vid] = None
        else:  # MOVE, STOP
            for vid in vills:
                if vid in task:
                    task[vid] = None
        snapshot(t)
    out.villagers = len(villagers)
    return out
