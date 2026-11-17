"""Cadenas causales: de un efecto medido a sus causas posibles, con pruebas a favor y en contra.

Cómo se decide, sin confundir correlación con causalidad
- Una prueba DECISIVA es una contradicción lógica con la mecánica del juego, no
  una coincidencia en el tiempo. Ejemplos: el juego no acepta una compra sin
  recursos, así que una compra aceptada de 60 de comida demuestra que había al
  menos 60; si la población máxima posible es menor que el tope de casas, había
  hueco seguro.
- Un INDICIO es algo que encaja con la causa pero no la demuestra: que se
  construyan casas justo cuando se reanuda la producción, o que haya muchas
  órdenes militares durante un paro.
- Veredicto de cada causa:
    respaldada  hay prueba decisiva a favor y ninguna en contra
    en parte    hay pruebas decisivas a favor y en contra (vale para un tramo y no para otro)
    descartada  hay prueba decisiva en contra y ninguna a favor
    compatible  solo hay indicios a favor
    sin datos   nada a favor ni en contra
- La atención del jugador nunca pasa de «compatible»: la grabación no ve la
  pantalla ni la intención. Se describe lo que hizo, no lo que pensaba.
"""
from __future__ import annotations

import re
from bisect import bisect_right
from collections import Counter
from dataclasses import dataclass, field

from . import economy, refdata, villagers
from .tc import Interval
from .validation import Model, fmt_clock

CREATED_RE = re.compile(r"^--(.+) Created--$")
INITIAL_POP = 4                 # 3 aldeanos y el explorador
POP_PER_TC = 5
POP_PER_HOUSE = 5
UNKNOWN_TRAIN_S = 60.0          # si no se conoce el tiempo, se supone largo: es la opción prudente
MIN_EPISODE_TC_S = 30.0
MILITARY_ACTIONS = {"PATROL", "DE_ATTACK_MOVE", "FORMATION", "STANCE", "ATTACK_GROUND", "GUARD", "FOLLOW"}


# ------------------------------------------------------------------ estructuras

@dataclass
class Evidence:
    text: str
    tag: str                    # OBSERVADO | CALCULADO | ESTIMADO
    weight: str                 # decisiva | indicio | contexto
    direction: int              # +1 a favor de la causa, -1 en contra, 0 contexto
    t: float | None = None
    partial: bool = False       # la prueba vale solo para una parte del tramo


@dataclass
class Cause:
    key: str
    title: str
    evidence: list[Evidence] = field(default_factory=list)
    upstream: list["Cause"] = field(default_factory=list)
    hypothesis_only: bool = False    # nunca puede pasar de compatible

    def _has(self, weight, direction):
        return any(e.weight == weight and e.direction == direction for e in self.evidence)

    @property
    def verdict(self) -> str:
        pro, con = self._has("decisiva", 1), self._has("decisiva", -1)
        hint = self._has("indicio", 1)
        if self.hypothesis_only:
            return "compatible" if hint else "sin datos"
        if pro and con:
            return "en parte"
        if pro:
            return "respaldada"
        if con:
            full = any(e.weight == "decisiva" and e.direction == -1 and not e.partial for e in self.evidence)
            # Descartada en unos momentos y posible en otros: no se puede dar por descartada.
            return "en parte" if (hint and not full) else "descartada"
        return "compatible" if hint else "sin datos"


@dataclass
class Chain:
    kind: str                   # "paro" (cola vacía) | "bloqueo" (cola pagada sin producir)
    start: float
    end: float
    tc_seconds: float
    effect: Evidence
    proximate: list[Evidence]
    causes: list[Cause]
    impact: list[Evidence]

    def cause(self, key: str) -> Cause | None:
        return next((c for c in self.causes if c.key == key), None)


# ------------------------------------------------------------------ población

@dataclass
class Population:
    """Cotas de población a partir de avisos. No ve muertes ni casas destruidas."""
    starts: list[float]          # instante en que cada unidad empieza a ocupar población
    houses: list[float]
    tcs: list[float]
    limit: int

    def upper(self, t: float) -> int:
        """Máximo posible de población ocupada en t: todas las unidades que ya
        habían empezado a entrenarse, como si ninguna hubiera muerto."""
        return INITIAL_POP + bisect_right(self.starts, t)

    def cap(self, t: float) -> int:
        """Tope de casas y centros urbanos terminados en t."""
        return min(self.limit, POP_PER_TC * (1 + bisect_right(self.tcs, t)) + POP_PER_HOUSE * bisect_right(self.houses, t))

    def room_certain(self, t: float) -> bool:
        return self.upper(t) < self.cap(t)


def population(model: Model) -> Population:
    starts = []
    for e in model.replay.events:
        if e.kind == "chat" and (m := CREATED_RE.match(e.payload["text"])):
            starts.append(e.t_ms - 1000 * (refdata.train_time_by_name(m.group(1)) or UNKNOWN_TRAIN_S))
    n = model.tc.notif
    return Population(sorted(starts), sorted(n.houses_built), sorted(n.tc_built), model.replay.header.population_limit)


# ------------------------------------------------------------------ episodios

def _merge(intervals: list[Interval], join_ms: float = 1500) -> list[tuple[float, float, float]]:
    out: list[list[float]] = []
    for i in sorted(intervals, key=lambda x: x.start):
        s = (i.end - i.start) / 1000 * i.tcs
        if out and i.start - out[-1][1] <= join_ms:
            out[-1][1] = max(out[-1][1], i.end)
            out[-1][2] += s
        else:
            out.append([i.start, i.end, s])
    return [tuple(x) for x in out]


def episodes(model: Model) -> list[tuple[str, float, float, float, bool]]:
    """(tipo, inicio, fin, s·TC, medido) de cada paro y bloqueo relevante."""
    a = model.tc
    measured = a.observed is not None
    idle = a.observed.idle if measured else (a.calibrated or a.general).idle()
    out = [("paro", s, e, ts, measured) for s, e, ts in _merge(idle) if ts >= MIN_EPISODE_TC_S]
    stalls = [Interval(s.start, s.end, s.tcs) for s in a.stalls]
    out += [("bloqueo", s, e, ts, True) for s, e, ts in _merge(stalls, 15_000) if ts >= MIN_EPISODE_TC_S / 2]
    return sorted(out, key=lambda x: x[1])


# ------------------------------------------------------------------ causas

def _food(model: Model, a: float, b: float, price: int) -> Cause:
    c = Cause("comida", "Falta de comida")
    eco = model.eco
    buys = [s for s in eco.purchases_between(a, b, "Food") if s.cost.get("Food", 0) >= price]
    for s in buys[:3]:
        c.evidence.append(Evidence(
            f"A las {fmt_clock(s.t)} el juego aceptó {s.label} por {s.cost['Food']} de comida: en ese momento había al "
            f"menos esa cantidad, y un aldeano cuesta {price}.", "OBSERVADO", "decisiva", -1, s.t, True))
    if len(buys) > 3:
        c.evidence.append(Evidence(f"Y {len(buys) - 3} compras más con comida durante el tramo.", "OBSERVADO", "decisiva", -1,
                                   None, True))
    v = economy.shortage_test(model.bounds, a, b, "Food", price)
    if v["proved_short"]:
        c.evidence.append(Evidence(f"En {v['proved_short']} de {v['samples']} muestras el total almacenado era menor "
                                   f"que {price}: faltaba comida seguro.", "CALCULADO", "decisiva", 1))
    if v["proved_enough"]:
        c.evidence.append(Evidence(f"En {v['proved_enough']} de {v['samples']} muestras las cotas demuestran que había "
                                   f"al menos {price} de comida.", "CALCULADO", "decisiva", -1,
                                   None, v["proved_enough"] < v["samples"]))
    est = [s[1]["Food"] for s in eco.series if a <= s[0] <= b]
    if est:
        lo, hi = min(est), max(est)
        c.evidence.append(Evidence(f"El modelo de reparto sitúa la comida entre {lo} y {hi} (confianza baja).",
                                   "ESTIMADO", "indicio", 1 if hi < price else (-1 if lo >= price else 0)))
    if c.verdict in ("respaldada", "en parte", "compatible"):
        c.upstream.append(_food_spending(model, a))
    return c


def _food_spending(model: Model, a: float, window_ms: int = 90_000) -> Cause:
    c = Cause("gasto_comida", "La comida se gastó antes en otras cosas")
    spent = Counter()
    for s in model.eco.spends:
        if a - window_ms <= s.t <= a and s.cost.get("Food"):
            spent[s.label] += s.cost["Food"]
    if spent:
        top = ", ".join(f"{k} {v}" for k, v in spent.most_common(4))
        c.evidence.append(Evidence(f"En los {window_ms // 1000} s anteriores se gastaron {sum(spent.values())} de comida: "
                                   f"{top}.", "CALCULADO", "indicio", 1))
    return c


def _housing(model: Model, pop: Population, a: float, b: float, kind: str) -> Cause:
    c = Cause("poblacion", "Tope de población (faltaban casas)")
    step = 5_000
    ts = [a + i * step for i in range(int((b - a) // step) + 1)]
    room = [t for t in ts if pop.room_certain(t)]
    full = [t for t in ts if not pop.room_certain(t)]
    if room:
        t0 = room[0]
        c.evidence.append(Evidence(
            f"En {len(room)} de {len(ts)} instantes revisados había hueco seguro: por ejemplo a las {fmt_clock(t0)}, como "
            f"mucho {pop.upper(t0)} de población con tope {pop.cap(t0)}. Supone que no se destruyeron casas.",
            "CALCULADO", "decisiva", -1, t0, bool(full)))
    if full:
        t0 = full[0]
        c.evidence.append(Evidence(
            f"En {len(full)} de {len(ts)} instantes la población posible alcanzaba el tope (a las {fmt_clock(t0)}: hasta "
            f"{pop.upper(t0)} con tope {pop.cap(t0)}). No es prueba: no se ven las muertes.", "CALCULADO", "indicio", 1, t0))
    houses = [h for h in pop.houses if a <= h <= b + 5_000]
    if kind == "bloqueo" and houses:
        gap = (b - houses[-1]) / 1000
        if abs(gap) <= 30:
            c.evidence.append(Evidence(
                f"Se terminaron {len(houses)} casas durante el bloqueo y la producción se reanudó {abs(gap):.0f} s "
                f"{'después' if gap >= 0 else 'antes'} de la última.", "OBSERVADO", "indicio", 1, houses[-1]))
    if c.verdict in ("respaldada", "en parte", "compatible"):
        c.upstream.append(_houses_late(model, pop, a))
    return c


def _houses_late(model: Model, pop: Population, a: float) -> Cause:
    c = Cause("casas_tarde", "Casas construidas tarde")
    prev = [h for h in pop.houses if h <= a]
    if prev:
        c.evidence.append(Evidence(f"La casa anterior se terminó a las {fmt_clock(prev[-1])}, "
                                   f"{(a - prev[-1]) / 1000:.0f} s antes.", "OBSERVADO", "contexto", 0, prev[-1]))
    k = max((i for i, x in enumerate(model.bounds) if x.t <= a), default=None)
    if k is not None:
        lo = model.bounds[k].lo["Wood"]
        if lo >= 25:
            c.evidence.append(Evidence(f"Las cotas demuestran al menos {lo} de madera a las {fmt_clock(model.bounds[k].t)}: "
                                       f"daba para una casa.", "CALCULADO", "decisiva", 1, model.bounds[k].t))
        elif model.bounds[k].hi["Wood"] < 25:
            c.evidence.append(Evidence("No había madera para una casa: el máximo posible era menor que 25.",
                                       "CALCULADO", "decisiva", -1, model.bounds[k].t))
    return c


def _new_tc(model: Model, a: float, b: float, tc_s: float) -> Cause | None:
    av = model.tc.calibrated.available if model.tc.calibrated else {}
    for tc_id, since in av.items():
        if since <= 0 or not (a - 5_000 <= since <= b):
            continue
        first = min((q.t for q in model.tc.inputs.queue if tc_id in q.tcs and q.t >= since), default=None)
        c = Cause("tc_nuevo", "Un centro urbano nuevo se quedó sin órdenes")
        if first is None:
            c.evidence.append(Evidence(f"El centro urbano terminado a las {fmt_clock(since)} no recibió ninguna orden de "
                                       f"aldeano en el resto de la partida.", "OBSERVADO", "decisiva", 1, since))
        else:
            c.evidence.append(Evidence(f"El centro urbano terminado a las {fmt_clock(since)} recibió su primera orden a "
                                       f"las {fmt_clock(first)}: {(first - since) / 1000:.0f} s sin nada en cola. "
                                       f"Explica {min(first, b) / 1000 - since / 1000:.0f} de los {tc_s:.0f} s·TC del tramo.",
                                       "OBSERVADO", "decisiva", 1, since))
        return c
    return None


def _attention(model: Model, a: float, b: float, vills: set[int]) -> Cause:
    c = Cause("atencion", "Atención puesta en otra parte", hypothesis_only=True)
    n = Counter()
    for e in model.replay.events:
        if e.t_ms < a or e.kind != "action" or e.player != model.player:
            continue
        if e.t_ms > b:
            break
        sel = set(e.payload.get("object_ids") or [])
        if e.action in MILITARY_ACTIONS or (e.action in ("ORDER", "MOVE") and sel and not sel & vills):
            n["ejército"] += 1
        elif e.action == "DE_QUEUE" and e.payload.get("unit_id") not in refdata.VILLAGER_IDS:
            n["unidades militares encargadas"] += 1
        elif e.action in ("BUILD", "ORDER", "MOVE", "GATHER_POINT", "RESEARCH", "DE_QUEUE"):
            n["economía"] += 1
        else:
            n["otras"] += 1
    total = sum(n.values())
    secs = (b - a) / 1000
    attacks = [t for t in model.tc.notif.attacks if a - 30_000 <= t <= b]
    if total:
        parts = ", ".join(f"{v} de {k}" for k, v in n.most_common())
        mil = n["ejército"] + n["unidades militares encargadas"]
        c.evidence.append(Evidence(f"Diste {total} órdenes en {secs:.0f} s: {parts}.", "OBSERVADO",
                                   "indicio" if mil >= total / 2 else "contexto", 1 if mil >= total / 2 else 0))
    else:
        c.evidence.append(Evidence(f"No diste ninguna orden en {secs:.0f} s.", "OBSERVADO", "contexto", 0))
    if attacks:
        txt = (f"Hubo un aviso de ataque a las {fmt_clock(attacks[0])}." if len(attacks) == 1 else
               f"Hubo {len(attacks)} avisos de ataque, el primero a las {fmt_clock(attacks[0])}.")
        c.evidence.append(Evidence(txt, "OBSERVADO", "indicio", 1, attacks[0]))
    return c


def _per_tc(model: Model, a: float, b: float) -> list[tuple[int, float, float]]:
    """Tramos parados de cada TC dentro del episodio, según órdenes y calibración [ESTIMADO]."""
    sim = model.tc.calibrated or model.tc.general
    return [(i.tc, max(i.start, a), min(i.end, b)) for i in sim.idle()
            if i.end > a and i.start < b and min(i.end, b) - max(i.start, a) >= 5_000]


def _tc_names(model: Model) -> dict[int, str]:
    av = (model.tc.calibrated or model.tc.general).available
    order = sorted(model.tc.inputs.tcs, key=lambda t: av.get(t, 0))
    return {t: ("el centro urbano inicial" if i == 0 else f"el centro urbano {i + 1}.º (terminado a las {fmt_clock(av[t])})")
            for i, t in enumerate(order)}


def _waiting_age(model: Model, a: float, b: float) -> Cause | None:
    names = _tc_names(model)
    for tc_id, s, e in _per_tc(model, a, b):
        nxt = min((r for r in model.tc.inputs.tc_research if r.building == tc_id and e - 2_000 <= r.t <= e + 5_000),
                  key=lambda r: r.t, default=None)
        if not nxt or nxt.tech_id not in refdata.AGE_TECHS:
            continue
        age = refdata.AGE_TECHS[nxt.tech_id]
        cost = refdata.cost("Tech", nxt.tech_id)
        c = Cause("reservar_tc", f"Guardar el centro urbano para avanzar a {age}", hypothesis_only=True)
        c.evidence.append(Evidence(f"{names[tc_id].capitalize()} estuvo parado de {fmt_clock(s)} a {fmt_clock(e)} y lo "
                                   f"siguiente que hizo fue investigar la edad {age}, a las {fmt_clock(nxt.t)}.",
                                   "OBSERVADO", "indicio", 1, nxt.t))
        est = model.eco.estimate_at(s)
        if est and cost:
            need = ", ".join(f"{v} de {RES_ES[k]}" for k, v in cost.items())
            have = ", ".join(f"{est[k]} de {RES_ES[k]}" for k in cost)
            c.evidence.append(Evidence(f"Avanzar costaba {need}; al empezar el paro el modelo estima {have} "
                                       f"(confianza baja). Si había de sobra, hacer aldeanos mientras tanto no retrasaba "
                                       f"el avance.", "ESTIMADO", "contexto", 0, s))
        k = max((i for i, x in enumerate(model.bounds) if x.t <= s), default=None)
        if k is not None and cost:
            bd = model.bounds[k]
            short = [r for r, v in cost.items() if bd.hi[r] < v]
            if short:
                c.evidence.append(Evidence(
                    "Las cotas demuestran que al empezar el paro todavía no se podía avanzar: faltaba "
                    + ", ".join(f"{RES_ES[r]} (como mucho {bd.hi[r]} de {cost[r]})" for r in short) + ".",
                    "CALCULADO", "contexto", 0, bd.t))
        return c
    return None


RES_ES = {"Food": "comida", "Wood": "madera", "Gold": "oro", "Stone": "piedra"}


def _stopped_for_good(model: Model, b: float) -> Cause | None:
    later = [q for q in model.tc.inputs.queue if q.t > b and q.unit_id in refdata.VILLAGER_IDS]
    if later or model.replay.duration_ms - b > 60_000:
        return None
    c = Cause("fin_aldeanos", "Decisión de dejar de hacer aldeanos", hypothesis_only=True)
    made = 3 + sum(1 for t in model.tc.notif.villagers if t <= b)
    c.evidence.append(Evidence(f"No volviste a encargar aldeanos hasta el final. Para entonces se habían creado {made} "
                               f"en total (3 iniciales incluidos; no se ven las muertes).", "OBSERVADO", "indicio", 1))
    return c


# ------------------------------------------------------------------ coste

def _impact(model: Model, a: float, b: float, tc_s: float) -> list[Evidence]:
    v_s = model.tc.cal.villager_ms / 1000
    lost = tc_s / v_s
    out = [Evidence(f"Equivale a unos {lost:.1f} aldeanos sin hacer ({tc_s:.0f} s·TC entre {v_s:.1f} s por aldeano).",
                    "CALCULADO", "contexto", 0)]
    made = sorted(model.tc.notif.villagers)
    if made and model.eco.windows:
        end = model.replay.duration_ms
        vill_s = sum(min(end, t1) - max(0, t0) for t0, t1 in [(0, end)] * 3) / 1000
        vill_s += sum(end - t for t in made) / 1000
        rate = model.eco.total_income() / vill_s if vill_s else 0
        remaining = max(0.0, (end - b) / 1000)
        if rate and remaining:
            out.append(Evidence(
                f"Si esos aldeanos hubieran trabajado hasta el final, al ritmo medio de esta partida "
                f"({rate * 60:.0f} recursos por minuto y aldeano), habrían recogido unos {lost * rate * remaining:.0f} "
                f"recursos más. Supone que nadie muere y que el ritmo no cambia.", "ESTIMADO", "contexto", 0))
    return out


# ------------------------------------------------------------------ cadenas

def chains(model: Model) -> list[Chain]:
    pop = population(model)
    world = villagers._World(load_objects_cached(model), model.player)
    vills = villagers._villager_ids(model.replay, model.player, world)
    out = []
    for kind, a, b, tc_s, measured in episodes(model):
        tag = "OBSERVADO" if measured else "ESTIMADO"
        if kind == "paro":
            effect = Evidence(f"El centro urbano estuvo sin producir de {fmt_clock(a)} a {fmt_clock(b)}: {tc_s:.0f} s·TC.",
                              "CALCULADO" if measured else "ESTIMADO", "contexto", 0, a)
            names = _tc_names(model)
            parts = [f"{names[t]} de {fmt_clock(s)} a {fmt_clock(e)}" for t, s, e in _per_tc(model, a, b)]
            proximate = [Evidence("No había órdenes de aldeano ni investigaciones pendientes. Por centro urbano: "
                                  + "; ".join(parts) + "." if parts else
                                  "No había órdenes de aldeano ni investigaciones pendientes.", "ESTIMADO", "contexto", 0)]
        else:
            effect = Evidence(f"El centro urbano tenía unidades pagadas en cola pero no producía, de {fmt_clock(a)} a "
                              f"{fmt_clock(b)}: {tc_s:.0f} s·TC.", "CALCULADO", "contexto", 0, a)
            proximate = [Evidence("Las órdenes dicen que había cola y los avisos dicen que no salía nada. En el juego, "
                                  "una cola pagada solo se detiene por tope de población, por cancelarla o si el edificio "
                                  "deja de funcionar.", "CALCULADO", "contexto", 0)]
        causes: list[Cause] = []
        if kind == "paro":
            if (c := _new_tc(model, a, b, tc_s)):
                causes.append(c)
            causes.append(_food(model, a, b, 50))
        causes.append(_housing(model, pop, a, b, kind))
        stopped = _stopped_for_good(model, b) if kind == "paro" else None
        if kind == "paro":
            if (c := _waiting_age(model, a, b)):
                causes.append(c)
            if stopped:
                causes.append(stopped)
        causes.append(_attention(model, a, b, vills))
        impact = _impact(model, a, b, tc_s) if kind == "paro" else []
        if stopped and impact:
            impact.append(Evidence("Si dejar de hacer aldeanos fue una decisión, por ejemplo por haber llegado a los que "
                                   "querías, este coste no aplica.", "CALCULADO", "contexto", 0))
        out.append(Chain(kind, a, b, tc_s, effect, proximate, causes, impact))
    return out


_OBJECTS: dict = {}


def load_objects_cached(model: Model):
    from .replay import load_objects
    key = model.replay.path
    if key not in _OBJECTS:
        _OBJECTS[key] = load_objects(key)
    return _OBJECTS[key]


# ------------------------------------------------------------------ texto

SYMBOL = {"respaldada": "✔", "en parte": "◐", "descartada": "✘", "compatible": "?", "sin datos": "·"}
WEIGHT = {"decisiva": "prueba decisiva", "indicio": "indicio", "contexto": "contexto"}
DIRECTION = {1: "a favor", -1: "en contra", 0: ""}


def _ev(e: Evidence) -> str:
    w = WEIGHT[e.weight] + (f" {DIRECTION[e.direction]}" if e.direction else "")
    return f"[{e.tag}] *{w}.* {e.text}"


def _cause_lines(c: Cause, depth: int = 0) -> list[str]:
    pad = "  " * depth
    tag = " [HIPÓTESIS]" if c.hypothesis_only else ""
    out = [f"{pad}- {SYMBOL[c.verdict]} **{c.title}: {c.verdict}.**{tag}"]
    for e in c.evidence:
        out.append(f"{pad}  - {_ev(e)}")
    for u in c.upstream:
        if u.evidence:
            out.append(f"{pad}  - ¿Y por qué? ")
            out += _cause_lines(u, depth + 2)
    return out


def render(chs: list[Chain]) -> list[str]:
    L = []
    for ch in chs:
        title = "Paro del centro urbano" if ch.kind == "paro" else "Producción bloqueada"
        L.append(f"### {title}, {fmt_clock(ch.start)} a {fmt_clock(ch.end)}")
        L.append("")
        L.append(f"**Efecto.** [{ch.effect.tag}] {ch.effect.text}")
        L.append("")
        for e in ch.proximate:
            L.append(f"**Causa inmediata.** [{e.tag}] {e.text}")
        L.append("")
        L.append("**Causas posibles**")
        L.append("")
        order = {"respaldada": 0, "en parte": 1, "compatible": 2, "descartada": 3, "sin datos": 4}
        for c in sorted(ch.causes, key=lambda c: order[c.verdict]):
            L += _cause_lines(c)
        if ch.impact:
            L.append("")
            L.append("**Coste**")
            L.append("")
            for e in ch.impact:
                L.append(f"- [{e.tag}] {e.text}")
        L.append("")
    return L
