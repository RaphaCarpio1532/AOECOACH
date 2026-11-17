"""Produccion e inactividad del centro urbano (TC).

Capa 2: metricas deterministas. Aqui no hay LLM ni interpretacion libre.

Dos metodos independientes, que se comparan entre si:

A) ESTIMACION por ordenes (general). Simula la cola de cada TC con las ordenes
   de encolar e investigar. Funciona con cualquier grabacion, pero no ve
   bloqueos por limite de poblacion, ordenes rechazadas ni cancelaciones.
   Resultado: cota inferior del tiempo sin producir.

B) MEDICION por notificaciones (solo si la grabacion las trae). Usa los avisos
   "Villager Created" y "... Research Complete" del jugador que grabo. Cada
   aviso implica que un TC estuvo ocupado justo antes. Es agregada: dice
   cuantos TC estaban parados en cada instante, no cuales.

Terminologia: "sin producir" = el TC no entrena ni investiga. Incluye tanto la
cola vacia como la cola bloqueada. Solo se llama "cola vacia" cuando las
ordenes lo respaldan.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from statistics import median

from . import refdata
from .replay import Replay

MIN_INTERVAL_MS = 1000        # por debajo de esto no se informa (ruido de calibracion)
NOTIF_RE = re.compile(r"^(?:<[A-Z]+>)?--(.+?)--$")
AGE_RE = re.compile(r"<player_id,(\d+),[^>]*> advanced to the (\w+) Age")


# ---------------------------------------------------------------- entradas

@dataclass
class Notifications:
    present: bool = False
    villagers: list[int] = field(default_factory=list)
    research_done: dict[str, int] = field(default_factory=dict)
    tc_built: list[int] = field(default_factory=list)
    houses_built: list[int] = field(default_factory=list)
    created_any: list[int] = field(default_factory=list)   # cualquier unidad creada
    relics: list[int] = field(default_factory=list)        # reliquias recogidas
    attacks: list[int] = field(default_factory=list)
    age_ups: dict[int, dict[str, int]] = field(default_factory=dict)


def read_notifications(replay: Replay) -> Notifications:
    n = Notifications()
    for e in replay.events:
        if e.kind != "chat":
            continue
        text = e.payload["text"]
        age = AGE_RE.search(text)
        if age:
            n.age_ups.setdefault(int(age.group(1)), {})[age.group(2)] = e.t_ms
            continue
        m = NOTIF_RE.match(text)
        if not m:
            continue
        body = m.group(1)
        if body.endswith(" Created"):
            n.created_any.append(e.t_ms)
        if body == "Villager Created":
            n.villagers.append(e.t_ms)
        elif body == "Town Center Built":
            n.tc_built.append(e.t_ms)
        elif body == "Relic Picked Up":
            n.relics.append(e.t_ms)
        elif body == "House Built":
            n.houses_built.append(e.t_ms)
        elif body.startswith("Warning: You are being attacked"):
            n.attacks.append(e.t_ms)
        elif body.endswith(" Research Complete"):
            n.research_done[body[: -len(" Research Complete")].lower()] = e.t_ms
    n.present = bool(n.villagers)
    return n


@dataclass(frozen=True)
class QueueCmd:
    t: int
    amount: int
    tcs: tuple[int, ...]
    unit_id: int
    offset: int


@dataclass(frozen=True)
class ResearchCmd:
    t: int
    tech_id: int
    building: int
    offset: int


@dataclass
class Inputs:
    player: int
    tcs: list[int]                      # ids de objeto, por orden de primera aparicion
    first_use: dict[int, int]
    queue: list[QueueCmd]
    tc_research: list[ResearchCmd]
    all_research: list[ResearchCmd]


def read_inputs(replay: Replay, player: int) -> Inputs:
    tcs: list[int] = []
    first_use: dict[int, int] = {}
    queue: list[QueueCmd] = []
    research: list[ResearchCmd] = []

    def seen(tc: int, t: int):
        if tc not in first_use:
            first_use[tc] = t
            tcs.append(tc)

    for e in replay.events:
        if e.kind != "action" or e.player != player:
            continue
        p = e.payload
        if e.action == "DE_QUEUE" and p.get("building_type") in refdata.TOWN_CENTER_IDS:
            ids = tuple(p.get("object_ids", ()))
            for tc in ids:
                seen(tc, e.t_ms)
            queue.append(QueueCmd(e.t_ms, p["amount"], ids, p["unit_id"], e.offset))
        elif e.action == "RESEARCH" and p.get("object_ids"):
            cmd = ResearchCmd(e.t_ms, p["technology_id"], p["object_ids"][0], e.offset)
            research.append(cmd)
            if cmd.tech_id in refdata.TC_TECH_IDS:
                seen(cmd.building, e.t_ms)
    tc_research = [c for c in research if c.building in first_use]
    return Inputs(player, tcs, first_use, queue, tc_research, research)


# ------------------------------------------------------------- calibracion

@dataclass
class Calibration:
    villager_ms: float
    villager_basis: str
    research_factor: float
    research_basis: str
    reference_villager_ms: float


def calibrate(inputs: Inputs, notif: Notifications) -> Calibration:
    ref = refdata.train_time_s(83) * 1000
    gaps = [b - a for a, b in zip(notif.villagers, notif.villagers[1:])]
    near = [g for g in gaps if 0.9 * ref <= g <= 1.05 * ref]
    if len(near) >= 5:
        v_ms, v_basis = float(median(near)), f"calibrado: mediana de {len(near)} huecos entre avisos consecutivos"
    else:
        v_ms, v_basis = ref, "referencia sin verificar (no hay avisos suficientes)"

    ratios = []
    for cmd in inputs.all_research:
        done = notif.research_done.get(refdata.tech_name(cmd.tech_id).lower())
        ref_s = refdata.research_time_s(cmd.tech_id)
        if done and ref_s and done > cmd.t:
            ratios.append((done - cmd.t) / (ref_s * 1000))
    # Una investigacion que espera en cola da un cociente mayor que el real, asi
    # que el factor es el valor MAS REPETIDO, no la media. Se exige mayoria clara.
    bins: dict[int, list[float]] = {}
    for r in ratios:
        bins.setdefault(round(r * 100), []).append(r)
    top = max(bins.values(), key=len) if bins else []
    if len(top) >= 3 and len(top) >= len(ratios) / 3:
        factor = round(median(top), 2)
        basis = (f"calibrado: {len(top)} de {len(ratios)} investigaciones tardaron "
                 f"{factor:.2f} veces el tiempo de referencia (el resto esperaron en cola "
                 f"o su referencia no coincide)")
    else:
        factor, basis = fit_factor_from_ages(inputs, notif, v_ms)
    return Calibration(v_ms, v_basis, factor, basis, ref)


def fit_factor_from_ages(inputs: Inputs, notif: Notifications, villager_ms: float) -> tuple[float, str]:
    """Sin avisos de investigacion: ajusta el factor para que las subidas de edad
    simuladas coincidan con los mensajes de avance de edad, que son publicos."""
    observed = notif.age_ups.get(inputs.player, {})
    if not observed:
        return 1.0, "referencia sin verificar (no hay mensajes de avance de edad)"
    best = (float("inf"), 1.0)
    for step in range(40, 261):
        f = step / 200
        sim = simulate(inputs, villager_ms, f, dict.fromkeys(inputs.tcs, 0), 10 ** 9)
        err = 0.0
        for item in sim.items:
            age = refdata.AGE_TECHS.get(item.ref_id) if item.kind == "research" else None
            if age in observed:
                err += abs(item.end - observed[age])
        best = min(best, (err, f))
    n = len(observed)
    return best[1], (f"ajustado a {n} avances de edad (error medio {best[0] / n / 1000:.1f} s)")


# -------------------------------------------------- A) simulacion por ordenes

@dataclass(frozen=True)
class Item:
    tc: int
    kind: str            # "villager" | "research"
    ref_id: int
    start: float
    end: float
    cmd_t: int
    offset: int


@dataclass(frozen=True)
class Interval:
    start: float
    end: float
    tcs: float           # numero de TC parados en el tramo (o 1 si es un TC concreto)
    tc: int | None = None

    @property
    def seconds(self) -> float:
        return (self.end - self.start) / 1000

    @property
    def tc_seconds(self) -> float:
        return self.seconds * self.tcs


@dataclass
class Simulation:
    items: list[Item]
    available: dict[int, int]
    horizon: float

    def idle(self) -> list[Interval]:
        out = []
        for tc, since in self.available.items():
            cursor = float(since)
            for it in sorted((i for i in self.items if i.tc == tc), key=lambda i: i.start):
                if it.start - cursor >= MIN_INTERVAL_MS and cursor < self.horizon:
                    out.append(Interval(cursor, min(it.start, self.horizon), 1, tc))
                cursor = max(cursor, it.end)
            if self.horizon - cursor >= MIN_INTERVAL_MS:
                out.append(Interval(cursor, self.horizon, 1, tc))
        return sorted(out, key=lambda i: i.start)

    def busy_spans(self) -> list[tuple[float, float]]:
        return [(i.start, min(i.end, self.horizon)) for i in self.items if i.start < self.horizon]


def simulate(inputs: Inputs, villager_ms: float, research_factor: float,
             available: dict[int, int], horizon: float) -> Simulation:
    """Cola FIFO por TC. Supuestos (todos declarados en el informe):
    S1 toda orden se acepta; S2 nada se cancela; S3 la produccion nunca se
    bloquea; S4 una orden sobre varios TC reparte sus unidades de una en una
    al TC que antes queda libre."""
    free: dict[int, float] = {tc: float(t) for tc, t in available.items()}
    items: list[Item] = []
    cmds = sorted([*inputs.queue, *inputs.tc_research], key=lambda c: (c.t, c.offset))
    for c in cmds:
        if isinstance(c, QueueCmd):
            targets = [tc for tc in c.tcs if tc in free]
            for _ in range(max(c.amount, 0)):
                if not targets:
                    break
                tc = min(targets, key=lambda x: max(free[x], c.t))
                start = max(free[tc], c.t)
                free[tc] = start + villager_ms
                items.append(Item(tc, "villager", c.unit_id, start, free[tc], c.t, c.offset))
        else:
            ref_s = refdata.research_time_s(c.tech_id)
            if c.building not in free or ref_s is None:
                continue
            start = max(free[c.building], c.t)
            free[c.building] = start + ref_s * 1000 * research_factor
            items.append(Item(c.building, "research", c.tech_id, start, free[c.building], c.t, c.offset))
    return Simulation(items, dict(available), horizon)


# ---------------------------------------------- B) medicion por notificaciones

@dataclass
class Observed:
    idle: list[Interval]
    overlap_ms: float             # ocupacion por encima de la capacidad: mide el error del modelo
    capacity_steps: list[tuple[int, int]]
    spans: list[tuple[float, float]]


def _sweep(spans: list[tuple[float, float]], capacity_steps: list[tuple[int, int]], horizon: float):
    """Devuelve tramos (inicio, fin, capacidad, ocupados)."""
    points: list[tuple[float, int, int]] = []
    for s, e in spans:
        points.append((max(s, 0.0), 0, 1))
        points.append((max(e, 0.0), 0, -1))
    for t, delta in capacity_steps:
        points.append((float(t), delta, 0))
    points.sort()
    out, cap, busy, prev = [], 0, 0, 0.0
    for t, dcap, dbusy in points:
        t = min(t, horizon)
        if t > prev and cap > 0:
            out.append((prev, t, cap, busy))
        prev = max(prev, t)
        cap += dcap
        busy += dbusy
    if horizon > prev and cap > 0:
        out.append((prev, horizon, cap, busy))
    return out


def _merge(pieces: list[tuple[float, float, float]]) -> list[Interval]:
    merged: list[list[float]] = []
    for s, e, n in pieces:
        if merged and merged[-1][2] == n and abs(merged[-1][1] - s) < 1:
            merged[-1][1] = e
        else:
            merged.append([s, e, n])
    return [Interval(s, e, n) for s, e, n in merged if e - s >= MIN_INTERVAL_MS]


def observe(inputs: Inputs, notif: Notifications, cal: Calibration, horizon: float) -> Observed:
    spans = [(c - cal.villager_ms, float(c)) for c in notif.villagers]
    for cmd in inputs.tc_research:
        done = notif.research_done.get(refdata.tech_name(cmd.tech_id).lower())
        ref_s = refdata.research_time_s(cmd.tech_id)
        if done and ref_s:
            spans.append((done - ref_s * 1000 * cal.research_factor, float(done)))
    steps = [(0, 1)] + [(t, 1) for t in notif.tc_built]
    pieces, overlap = [], 0.0
    for s, e, cap, busy in _sweep(spans, steps, horizon):
        if busy > cap:
            overlap += (e - s) * (busy - cap)
        elif busy < cap:
            pieces.append((s, e, cap - busy))
    return Observed(_merge(pieces), overlap, steps, spans)


# ------------------------------------------------------------- resultado

@dataclass
class Phase:
    start: float
    end: float
    tcs: int
    observed_idle_s: float | None
    estimated_idle_s: float
    unknown_s: float


@dataclass
class Stall:
    """Tramo en que las ordenes dicen 'ocupado' y las notificaciones dicen 'parado'."""
    start: float
    end: float
    tcs: float


@dataclass
class TCAnalysis:
    player: int
    inputs: Inputs
    notif: Notifications
    cal: Calibration
    horizon: float
    general: Simulation            # solo ordenes, parametros de referencia
    general_factor_basis: str
    calibrated: Simulation | None  # ordenes + calibracion + disponibilidad observada
    observed: Observed | None
    phases: list[Phase]
    stalls: list[Stall]
    completion_error_ms: list[tuple[float, float]]   # (fin previsto, error absoluto)
    unmatched_predicted: int
    unmatched_observed: int


def _idle_between(intervals: list[Interval], a: float, b: float) -> float:
    return sum(max(0.0, min(i.end, b) - max(i.start, a)) * i.tcs for i in intervals) / 1000


def analyze(replay: Replay, player: int) -> TCAnalysis:
    inputs = read_inputs(replay, player)
    notif = read_notifications(replay)
    is_recorder = notif.present and bool(inputs.queue)
    cal = calibrate(inputs, notif if is_recorder else Notifications(age_ups=notif.age_ups))
    ref_ms = cal.reference_villager_ms
    horizon = replay.duration_ms - cal.villager_ms   # el ultimo tramo no es observable

    # A) estimador general: no usa ninguna notificacion privada.
    g_factor, g_basis = fit_factor_from_ages(inputs, notif, ref_ms)
    first_use = {tc: (0 if i == 0 else inputs.first_use[tc]) for i, tc in enumerate(inputs.tcs)}
    general = simulate(inputs, ref_ms, g_factor, first_use, horizon)

    calibrated = observed = None
    stalls: list[Stall] = []
    errors: list[tuple[float, float]] = []
    miss_pred = miss_obs = 0
    if is_recorder:
        avail = {tc: 0 for tc in inputs.tcs[:1]}
        for tc, t in zip(inputs.tcs[1:], notif.tc_built):
            avail[tc] = t
        for tc in inputs.tcs[1 + len(notif.tc_built):]:
            avail[tc] = inputs.first_use[tc]
        calibrated = simulate(inputs, cal.villager_ms, cal.research_factor, avail, horizon)
        observed = observe(inputs, notif, cal, horizon)

        # Validacion cruzada 1: cada aldeano previsto contra el aviso mas cercano.
        pending = sorted(notif.villagers)
        for it in sorted((i for i in calibrated.items if i.kind == "villager" and i.end <= horizon),
                         key=lambda i: i.end):
            match = next((c for c in pending if abs(c - it.end) <= 1500), None)
            if match is None:
                miss_pred += 1
            else:
                pending.remove(match)
                errors.append((it.end, abs(match - it.end)))
        miss_obs = sum(1 for c in pending if c <= horizon)

        # Validacion cruzada 2: ocupacion prevista contra ocupacion observada.
        sim_busy = _sweep(calibrated.busy_spans(), observed.capacity_steps, horizon)
        obs_busy = _sweep(observed.spans, observed.capacity_steps, horizon)
        cuts = sorted({p for seg in (*sim_busy, *obs_busy) for p in seg[:2]})

        def level(segs, t):
            return next((b for s, e, _, b in segs if s <= t < e), 0)

        pieces = []
        for a, b in zip(cuts, cuts[1:]):
            mid = (a + b) / 2
            diff = level(sim_busy, mid) - level(obs_busy, mid)
            if diff > 0:
                pieces.append((a, b, diff))
        stalls = [Stall(i.start, i.end, i.tcs) for i in _merge(pieces) if i.end - i.start >= 3000]

    bounds = [0.0] + [float(t) for t in (notif.tc_built if is_recorder else
                                          sorted(first_use.values())[1:])] + [horizon]
    g_idle = general.idle()
    phases = []
    for n, (a, b) in enumerate(zip(bounds, bounds[1:]), start=1):
        known = sum(max(0.0, b - max(a, t)) for t in first_use.values()) / 1000
        phases.append(Phase(a, b, n,
                            _idle_between(observed.idle, a, b) if observed else None,
                            _idle_between(g_idle, a, b),
                            max(0.0, (b - a) * n / 1000 - known)))
    return TCAnalysis(player, inputs, notif, cal, horizon, general, g_basis, calibrated,
                      observed, phases, stalls, errors, miss_pred, miss_obs)
