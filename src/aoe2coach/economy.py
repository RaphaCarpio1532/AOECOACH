"""Economia: gastos, ingresos y recursos por tipo.

Tres niveles de certeza, de mas a menos:

1. LIBRO DE GASTOS [CALCULADO]. Cada orden de entrenar, investigar o construir
   por su coste de referencia. Se audita de dos formas: la contabilidad de
   unidades (ordenadas frente a creadas) y el signo del ingreso derivado.

2. INGRESO TOTAL [CALCULADO]. La grabacion da la suma de los cuatro recursos
   cada pocos segundos. Ingreso = variacion de esa suma + gastos del tramo.
   No ve gastos sin orden (resiembra automatica de granjas) ni devoluciones.

3. RECURSOS POR TIPO [ESTIMADO, confianza baja]. Reparte el ingreso total segun
   a que recurso esta asignado cada aldeano, deducido de puntos de reunion y
   ordenes. Se valida contra un hecho duro: una compra aceptada prueba que
   habia al menos ese recurso en ese instante.
"""
from __future__ import annotations

import re
from bisect import bisect_right
from collections import Counter
from dataclasses import dataclass, field

from . import refdata
from .replay import MapObject, Replay
from .villagers import Allocation, Rules, allocate

RES = ("Food", "Wood", "Gold", "Stone")
STANDARD_START = {"Food": 200, "Wood": 200, "Gold": 100, "Stone": 200}
CREATED_RE = re.compile(r"^--(.+) Created--$")
# Nombre con que se crea una unidad mejorada -> unidad que se ordena.
UNIT_LINE = {"Light Cavalry": "Scout Cavalry", "Hussar": "Scout Cavalry",
             "Heavy Cavalry Archer": "Cavalry Archer", "Crossbowman": "Archer",
             "Arbalester": "Archer", "Pikeman": "Spearman", "Halberdier": "Spearman",
             "Man-at-Arms": "Militia", "Long Swordsman": "Militia", "Elite Skirmisher": "Skirmisher"}


# ------------------------------------------------------------------ gastos

@dataclass(frozen=True)
class Spend:
    t: int
    kind: str            # "Unit" | "Tech" | "Building"
    label: str
    qty: int
    cost: dict           # total de la orden, por recurso
    offset: int

    @property
    def total(self) -> int:
        return sum(self.cost.values())


def ledger(replay: Replay, player: int) -> tuple[list[Spend], Counter]:
    out: list[Spend] = []
    missing: Counter = Counter()
    for e in replay.events:
        if e.kind != "action" or e.player != player:
            continue
        p = e.payload
        if e.action == "DE_QUEUE":
            kind, oid, qty, label = "Unit", p["unit_id"], p["amount"], refdata.object_name(p["unit_id"])
        elif e.action == "RESEARCH":
            kind, oid, qty, label = "Tech", p["technology_id"], 1, refdata.tech_name(p["technology_id"])
        elif e.action == "BUILD":
            kind, oid, qty, label = "Building", p.get("building_id", -1), 1, refdata.object_name(p.get("building_id", -1))
        else:
            continue
        unit_cost = refdata.cost(kind, oid)
        if not unit_cost:
            missing[label] += 1
        out.append(Spend(e.t_ms, kind, label, qty, {k: v * qty for k, v in unit_cost.items()}, e.offset))
    return out, missing


@dataclass
class AuditRow:
    line: str
    ordered: int
    created: int
    worst_excess: int     # maximo de (creadas - ordenadas) en cualquier instante; > 0 es imposible

    @property
    def consistent(self) -> bool:
        return self.worst_excess <= 0


def acceptance_audit(replay: Replay, player: int) -> list[AuditRow]:
    """Si en ningun instante hay mas unidades creadas que ordenadas, y al final
    faltan solo las que estaban en cola, las ordenes se aceptaron."""
    ordered: Counter = Counter()
    created: Counter = Counter()
    worst: Counter = Counter()
    for e in replay.events:
        if e.kind == "action" and e.player == player and e.action == "DE_QUEUE":
            ordered[refdata.object_name(e.payload["unit_id"])] += e.payload["amount"]
        elif e.kind == "chat":
            m = CREATED_RE.match(e.payload["text"])
            if m:
                line = UNIT_LINE.get(m.group(1), m.group(1))
                created[line] += 1
                worst[line] = max(worst[line], created[line] - ordered[line])
    return [AuditRow(k, ordered[k], created[k], worst[k]) for k in sorted(set(ordered) | set(created))]


# ----------------------------------------------------------------- ingresos

@dataclass(frozen=True)
class Window:
    t0: int
    t1: int
    stock0: int
    stock1: int
    spent: int

    @property
    def income(self) -> int:
        return self.stock1 - self.stock0 + self.spent


def income_windows(replay: Replay, player: int, spends: list[Spend]) -> list[Window]:
    samples = [(e.t_ms, e.payload[player]["total_res"]) for e in replay.events
               if e.kind == "sync" and player in e.payload]
    if not samples:
        return []
    before_first = sum(s.total for s in spends if s.t <= samples[0][0])
    prev_t, prev_v = 0, samples[0][1] + before_first    # supone ingreso ~0 hasta la primera muestra
    out, i = [], 0
    spends = sorted(spends, key=lambda s: s.t)
    for t, v in samples:
        spent = 0
        while i < len(spends) and spends[i].t <= t:
            spent += spends[i].total
            i += 1
        out.append(Window(prev_t, t, prev_v, v, spent))
        prev_t, prev_v = t, v
    return out


# ------------------------------------------------------- recursos por tipo

@dataclass
class Violation:
    t: int
    label: str
    resource: str
    needed: int
    estimated: float

    @property
    def deficit(self) -> float:
        return self.needed - self.estimated


@dataclass
class Economy:
    player: int
    spends: list[Spend]
    missing_costs: Counter
    audit: list[AuditRow]
    windows: list[Window]
    start_total: int
    start_by_type: dict | None
    alloc: Allocation | None
    series: list[tuple[int, dict]]        # (instante, recursos estimados por tipo) en cada muestra
    violations: list[Violation]
    checked_purchases: int
    mean_coverage: float
    relic_gold: float = 0.0

    MAX_VIOLATION_RATE = 0.10

    @property
    def model_reliable(self) -> bool:
        """El modelo de reparto solo se usa si contradice como mucho al 10 % de las
        compras aceptadas. Si no, sus cifras no se muestran como estimación."""
        return bool(self.alloc and self.checked_purchases
                    and len(self.violations) / self.checked_purchases <= self.MAX_VIOLATION_RATE)

    def serious_violations(self, tolerance: int = 50) -> list[Violation]:
        """Compras que el modelo declara imposibles por mas de `tolerance`."""
        return [v for v in self.violations if v.deficit > tolerance]

    @property
    def negative_windows(self) -> list[Window]:
        return [w for w in self.windows if w.income < -1]

    def spent_by_type(self) -> dict:
        c: Counter = Counter()
        for s in self.spends:
            c.update(s.cost)
        return {r: c.get(r, 0) for r in RES}

    def total_income(self) -> int:
        return sum(w.income for w in self.windows)

    def estimate_at(self, t: float) -> dict | None:
        if not self.series:
            return None
        times = [s[0] for s in self.series]
        i = bisect_right(times, t) - 1
        return self.series[i][1] if i >= 0 else self.start_by_type

    def purchases_between(self, a: float, b: float, resource: str) -> list[Spend]:
        return [s for s in self.spends if a <= s.t <= b and s.cost.get(resource)]


def analyze(replay: Replay, player: int, objects: dict[int, MapObject] | None = None,
            creations: list[tuple[float, int]] | None = None, rules: Rules = Rules(),
            relic_starts: list[int] | None = None) -> Economy:
    spends, missing = ledger(replay, player)
    windows = income_windows(replay, player, spends)
    start_total = windows[0].stock0 if windows else 0
    start = dict(STANDARD_START) if start_total == sum(STANDARD_START.values()) else None

    alloc = None
    series: list[tuple[int, dict]] = []
    violations: list[Violation] = []
    checked = 0
    coverage: list[float] = []
    if objects and creations is not None and start and windows:
        alloc = allocate(replay, player, objects, creations, rules)
        stock = {r: float(v) for r, v in start.items()}
        by_time = sorted(spends, key=lambda s: s.t)
        i = 0
        relic_starts = sorted(relic_starts or [])

        def relic_gold(a: float, b: float) -> float:
            return sum(max(0.0, b - max(a, r0)) for r0 in relic_starts) / 1000 * refdata.RELIC_GOLD_PER_S

        for w in windows:
            shares, cov = alloc.shares((w.t0 + w.t1) / 2)
            coverage.append(cov)
            span = max(w.t1 - w.t0, 1)
            cursor = w.t0
            while i < len(by_time) and by_time[i].t <= w.t1:
                s = by_time[i]
                i += 1
                frac = (s.t - cursor) / span          # ingreso lineal dentro del tramo
                relic = relic_gold(cursor, s.t)
                stock["Gold"] += relic
                for r in RES:
                    stock[r] += (w.income * frac - relic) * shares.get(r, 0.25)
                cursor = s.t
                for r, need in s.cost.items():
                    if r not in stock:
                        continue
                    checked += 1
                    if stock[r] < need - 1:
                        violations.append(Violation(s.t, s.label, r, need, stock[r]))
                    stock[r] -= need
            frac = (w.t1 - cursor) / span
            relic = relic_gold(cursor, w.t1)
            stock["Gold"] += relic
            for r in RES:
                stock[r] += (w.income * frac - relic) * shares.get(r, 0.25)
            series.append((w.t1, {r: round(v) for r, v in stock.items()}))
    relic_total = relic_gold(0, windows[-1].t1) if alloc is not None else 0.0
    return Economy(player, spends, missing, acceptance_audit(replay, player), windows, start_total,
                   start, alloc, series, violations, checked,
                   sum(coverage) / len(coverage) if coverage else 0.0, relic_total)


# ------------------------------------------------------------ cotas rigurosas

@dataclass(frozen=True)
class Bound:
    t: int
    total: int           # suma observada de los cuatro recursos
    lo: dict             # minimo demostrable por recurso
    hi: dict             # maximo demostrable por recurso


def stock_bounds(eco: Economy) -> list[Bound]:
    """Cotas por recurso en cada muestra de la grabacion. No usan ningun modelo.

    Minimo: si mas adelante se acepta una compra de X, y entre medias el ingreso
    total fue como mucho Y, ahora habia al menos X - Y de ese recurso. Las
    compras se acumulan: tres compras seguidas exigen la suma.
    Maximo: el total observado menos los minimos de los otros tres recursos.

    Validez: depende de que los costes de referencia sean los de la partida y de
    que las ordenes se aceptaran. Ambas cosas se auditan aparte.
    """
    spends = sorted(eco.spends, key=lambda s: s.t)
    out: list[Bound] = []
    j = 0
    for k, w in enumerate(eco.windows):
        t = w.t1
        while j < len(spends) and spends[j].t <= t:
            j += 1
        lo = dict.fromkeys(RES, 0)
        need = dict.fromkeys(RES, 0)
        income_cap = 0
        widx = k + 1
        for s in spends[j:]:
            while widx < len(eco.windows) and eco.windows[widx].t0 < s.t:
                income_cap += max(eco.windows[widx].income, 0)
                widx += 1
            if income_cap > 4000 and widx - k > 12:
                break                      # a esa distancia la cota ya no dice nada
            for r, c in s.cost.items():
                if r in need:
                    need[r] += c
                    lo[r] = max(lo[r], need[r] - income_cap)
        hi = {r: max(w.stock1 - sum(v for q, v in lo.items() if q != r), 0) for r in RES}
        out.append(Bound(t, w.stock1, lo, hi))
    return out


def shortage_test(bounds: list[Bound], a: float, b: float, resource: str, price: int) -> dict:
    """¿Pudo faltar `price` de `resource` entre a y b? Devuelve el veredicto por muestra."""
    inside = [x for x in bounds if a <= x.t <= b]
    return {
        "samples": len(inside),
        "proved_enough": sum(1 for x in inside if x.lo[resource] >= price),
        "proved_short": sum(1 for x in inside if x.hi[resource] < price),
        "min_lo": min((x.lo[resource] for x in inside), default=None),
        "min_hi": min((x.hi[resource] for x in inside), default=None),
    }
