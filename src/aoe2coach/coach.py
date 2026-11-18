"""Capa de entrenador: de la evidencia al consejo.

Las capas de abajo (tc, economy, causal) producen pruebas con procedencia. Aqui
se eligen las POCAS cosas que merece la pena contarle al jugador, se ordenan por
lo que costaron y se dicen en una frase.

Regla de oro: nada se inventa. Cada hallazgo guarda las lineas de prueba de las
que sale, y declara si esta medido, calculado o estimado.

Moneda de comparacion: "aldeanos equivalentes". Un hallazgo vale lo que cuesta
en aldeanos, sea porque el centro urbano no los hizo (segundos parado entre los
segundos que tarda un aldeano) o porque el rival tuvo mas.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from . import causal, economy, postgame as pg_mod, refdata, replay as replay_mod
from .replay import Replay
from .validation import Model, build as build_model

MIN_IMPACT = 1.0          # por debajo de un aldeano no se cuenta como error
AGE_GAP_S = 45            # diferencia de edad que ya se nota
TOP = 3

AGES_ES = {"Feudal": "Feudal", "Castle": "Castillos", "Imperial": "Imperial"}

# Que hacer la proxima vez, por causa. Son consejos de juego, no deducciones del
# archivo: van marcados como consejo en el informe.
FIXES = {
    "poblacion": "Adelanta las casas: constrúyelas cuando te queden 4 o 5 huecos, no cuando el juego te avise.",
    "comida": "Pon más aldeanos en comida antes de encolar: con un solo centro urbano necesitas unos 10 en comida para no parar.",
    "atencion": "Vuelve al centro urbano cada vez que acabes una pelea o un edificio. Un toque cada 30 segundos basta.",
    "tc_nuevo": "Encola aldeanos en el centro urbano nuevo en cuanto termine: no se pone a trabajar solo.",
    "esperando_edad": "Mientras avanzas de edad el centro urbano sigue libre: sigue encolando aldeanos.",
    "parada_final": "Si dejaste de hacer aldeanos a propósito, bien. Si no, revisa ese tramo.",
    "edad_tarde": "Ensaya el inicio hasta llegar a la edad siguiente sin paradas: es lo que más cambia la partida.",
    "aldeanos": "Sigue haciendo aldeanos más allá del minuto 20. El rival no paró.",
}


@dataclass
class Finding:
    key: str
    headline: str               # la frase que se lee primero
    cost_label: str             # "−7 aldeanos", "2:10 más tarde"
    impact: float               # aldeanos equivalentes, para ordenar
    when_label: str             # "12:40 → 14:14" o "18:22"
    t0: float | None
    t1: float | None
    cause: str                  # titulo de la causa, en llano
    confidence: str             # medido | calculado | estimado | hipotesis
    why: list[str] = field(default_factory=list)      # pruebas, en llano
    fix: str = ""
    detail: list[str] = field(default_factory=list)   # lineas forenses, para el pliegue


@dataclass
class Compare:
    label: str
    mine: str
    theirs: str
    better: str                 # "mine" | "theirs" | "tie"


@dataclass
class Report:
    name: str
    civ: str
    map_name: str
    duration_ms: int
    player: int
    result: str                 # "victoria" | "derrota" | "desconocido"
    opponent: str | None
    findings: list[Finding]
    compares: list[Compare]
    marks: list[tuple[float, str, str]]          # (t, tipo, texto)
    idle_bands: list[tuple[float, float, float, str]]   # (t0, t1, tcs, tipo)
    villager_series: list[tuple[float, int]]
    stock_series: list[tuple[float, int]]
    buildings: list[tuple[float, int, float, float]]    # (t, tipo, x, y)
    terrain: list[tuple[float, float, str]]            # (x, y, recurso)
    enemy_starts: list[tuple[float, float, int]]        # (x, y, color)
    my_start: tuple[float, float] | None
    quality: list[str]
    measured: bool
    villager_s: float
    stats: pg_mod.Postgame | None
    forensic: str = ""


def _clock(ms: float) -> str:
    s = int(ms // 1000)
    return f"{s // 60}:{s % 60:02d}"


def _clock_s(s: float) -> str:
    s = int(s)
    return f"{s // 60}:{s % 60:02d}"


# --------------------------------------------------------------- hallazgos

_VERDICT_RANK = {"respaldada": 0, "en parte": 1, "compatible": 2, "sin datos": 3, "descartada": 4}


def _best_cause(chain: causal.Chain) -> causal.Cause | None:
    """La causa mejor respaldada. Empate: la que no es 'atencion', que nunca pasa de hipotesis."""
    usable = [c for c in chain.causes if c.verdict != "descartada"]
    if not usable:
        return None
    return min(usable, key=lambda c: (_VERDICT_RANK[c.verdict], c.key == "atencion", c.title))


def _why(cause: causal.Cause, limit: int = 2) -> list[str]:
    pro = [e for e in cause.evidence if e.direction == 1]
    pro.sort(key=lambda e: 0 if e.weight == "decisiva" else 1)
    return [e.text for e in pro[:limit]] or [e.text for e in cause.evidence[:1]]


def _confidence(cause: causal.Cause | None, measured: bool) -> str:
    if cause is None:
        return "medido" if measured else "estimado"
    if cause.hypothesis_only:
        return "hipotesis"
    return {"respaldada": "demostrado", "en parte": "demostrado en parte"}.get(
        cause.verdict, "medido" if measured else "estimado")


def _idle_findings(model: Model, chains: list[causal.Chain]) -> list[Finding]:
    v_s = model.tc.cal.villager_ms / 1000
    end = model.replay.duration_ms
    out = []
    for ch in chains:
        # Un tramo que muere con la partida incluye la fase en que parar es una decision.
        if ch.kind == "paro" and end - ch.end <= 60_000 and ch.end - ch.start > 10 * 60_000:
            continue
        impact = ch.tc_seconds / v_s
        if impact < MIN_IMPACT:
            continue
        cause = _best_cause(ch)
        head = ("Tu centro urbano estuvo parado" if ch.kind == "paro"
                else "Tenías aldeanos pagados en cola que no salían")
        out.append(Finding(
            key=f"{ch.kind}-{int(ch.start)}",
            headline=f"{head} {_clock_s(ch.tc_seconds)}",
            cost_label=f"−{impact:.0f} aldeanos" if impact >= 1.5 else "−1 aldeano",
            impact=impact,
            when_label=f"{_clock(ch.start)} → {_clock(ch.end)}",
            t0=ch.start, t1=ch.end,
            cause=cause.title if cause else "Sin causa identificada",
            confidence=_confidence(cause, model.tc.observed is not None),
            why=_why(cause) if cause else [ch.proximate[0].text] if ch.proximate else [],
            fix=FIXES.get(cause.key if cause else "", ""),
            detail=causal.render([ch]),
        ))
    return out


def _age_findings(model: Model, stats: pg_mod.Postgame | None, me: pg_mod.Stats | None) -> list[Finding]:
    if not stats or me is None:
        return []
    rivals = [p for p in stats.players if p.team != me.team and p.collected]
    if not rivals:
        return []
    v_s = model.tc.cal.villager_ms / 1000
    out = []
    for age in ("Feudal", "Castle", "Imperial"):
        mine = me.age_s(age)
        theirs = [p.age_s(age) for p in rivals if p.age_s(age) is not None]
        if mine is None or not theirs:
            continue
        best = min(theirs)
        gap = mine - best
        if gap < AGE_GAP_S:
            continue
        who = min(rivals, key=lambda p: p.age_s(age) if p.age_s(age) is not None else 10 ** 9)
        out.append(Finding(
            key=f"edad-{age}",
            headline=f"Llegaste a {AGES_ES[age]} {_clock_s(gap)} después que {who.name}",
            cost_label=f"{_clock_s(gap)} de retraso",
            impact=gap / v_s,
            when_label=_clock_s(mine),
            t0=mine * 1000, t1=None,
            cause=f"Tú en {_clock_s(mine)}, {who.name} en {_clock_s(best)}",
            confidence="demostrado",
            why=[f"Los dos tiempos los escribe el juego en la tabla final de la partida, no se estiman.",
                 f"Un retraso de {_clock_s(gap)} son unos {gap / v_s:.0f} aldeanos de tiempo "
                 f"({gap:.0f} s entre {v_s:.1f} s por aldeano)."],
            fix=FIXES["edad_tarde"],
            detail=[f"- Tiempos de edad en la tabla final: "
                    + "; ".join(f"{p.name} {_clock_s(p.age_s(age))}" for p in [me, *rivals]
                                if p.age_s(age) is not None)],
        ))
    return out


def _villager_finding(stats: pg_mod.Postgame | None, me: pg_mod.Stats | None) -> list[Finding]:
    if not stats or me is None:
        return []
    rivals = [p for p in stats.players if p.team != me.team and p.villager_high]
    if not rivals:
        return []
    top = max(rivals, key=lambda p: p.villager_high)
    gap = top.villager_high - me.villager_high
    if gap < 5:
        return []
    return [Finding(
        key="aldeanos",
        headline=f"{top.name} llegó a {top.villager_high} aldeanos y tú a {me.villager_high}",
        cost_label=f"−{gap} aldeanos",
        impact=float(gap),
        when_label="toda la partida",
        t0=None, t1=None,
        cause="Menos aldeanos que el rival en el punto más alto",
        confidence="demostrado",
        why=["El máximo de aldeanos de cada jugador lo escribe el juego en la tabla final.",
             f"Con {gap} aldeanos menos trabajando, todo lo demás llega más tarde."],
        fix=FIXES["aldeanos"],
        detail=[f"- Aldeanos máximos en la tabla final: "
                + "; ".join(f"{p.name} {p.villager_high}" for p in [me, *rivals])],
    )]


# --------------------------------------------------------------- comparativa

def _compares(stats: pg_mod.Postgame | None, me: pg_mod.Stats | None) -> list[Compare]:
    if not stats or me is None:
        return []
    rivals = [p for p in stats.players if p.team != me.team and p.collected]
    if not rivals:
        return []
    r = max(rivals, key=lambda p: p.collected)

    def row(label, a, b, fmt=str, more_is_better=True):
        better = "tie" if a == b else ("mine" if (a > b) == more_is_better else "theirs")
        return Compare(label, fmt(a), fmt(b), better)

    def miles(n):
        return f"{n:,}".replace(",", ".")

    out = [
        row("Recursos recogidos", me.collected, r.collected, miles),
        row("Aldeanos (máximo)", me.villager_high, r.villager_high),
        row("Unidades matadas", me.units_killed, r.units_killed),
        row("Unidades perdidas", me.units_lost, r.units_lost, more_is_better=False),
        row("Edificios arrasados", me.buildings_razed, r.buildings_razed),
        row("Tecnologías investigadas", me.research_count, r.research_count),
        row("Mapa explorado", me.explored_pct, r.explored_pct, lambda v: f"{v} %"),
        row("Puntuación", me.score, r.score),
    ]
    for age in ("Feudal", "Castle", "Imperial"):
        if me.age_s(age) or r.age_s(age):
            out.append(Compare(
                AGES_ES[age],
                _clock_s(me.age_s(age)) if me.age_s(age) else "—",
                _clock_s(r.age_s(age)) if r.age_s(age) else "—",
                "tie" if me.age_s(age) == r.age_s(age) else
                ("mine" if (me.age_s(age) or 10 ** 9) < (r.age_s(age) or 10 ** 9) else "theirs")))
    return out


# --------------------------------------------------------------- visuales

def _marks(model: Model) -> list[tuple[float, str, str]]:
    a = model.tc
    out: list[tuple[float, str, str]] = []
    for age, t in a.notif.age_ups.get(model.player, {}).items():
        out.append((float(t), "edad", AGES_ES.get(age, age)))
    for t in a.notif.tc_built:
        out.append((float(t), "tc", "Centro urbano nuevo"))
    for t in a.notif.attacks:
        out.append((float(t), "ataque", "Te atacan"))
    for e in model.replay.events:
        if e.kind == "action" and e.action == "RESIGN":
            who = e.payload.get("player_id")
            name = next((p.name for p in model.replay.header.players if p.number == who), f"jugador {who}")
            out.append((float(e.t_ms), "rendicion", f"{name} se rinde"))
    return sorted(out)


def _series(model: Model) -> tuple[list, list]:
    vills = sorted(model.tc.notif.villagers)
    villager_series = [(float(t), i + 1) for i, t in enumerate(vills)]
    stock = [(float(w.t1), int(w.stock1)) for w in model.eco.windows]
    return villager_series, stock


def _map_data(model: Model):
    objects = causal.load_objects_cached(model)
    me = model.player
    terrain: list[tuple[float, float, str]] = []
    enemy: list[tuple[float, float, int]] = []
    my_start = None
    colors = {p.number: p.color_id for p in model.replay.header.players}
    for o in objects.values():
        if o.owner == 0:
            from .villagers import resource_of
            r = resource_of(o.object_id, o.class_id)
            if r:
                terrain.append((o.x, o.y, r))
        elif o.object_id in refdata.TOWN_CENTER_IDS:
            if o.owner == me:
                my_start = (o.x, o.y)
            else:
                enemy.append((o.x, o.y, colors.get(o.owner, o.owner)))
    builds = [(float(e.t_ms), int(e.payload.get("building_id", -1)),
               float(e.payload.get("x", -1)), float(e.payload.get("y", -1)))
              for e in model.replay.events
              if e.kind == "action" and e.action == "BUILD" and e.player == me
              and e.payload.get("x") is not None]
    return terrain, enemy, my_start, builds


def _idle_bands(model: Model) -> list[tuple[float, float, float, str]]:
    return [(a, b, tc_s, kind) for kind, a, b, tc_s, _m in causal.episodes(model)]


def _quality(model: Model, stats: pg_mod.Postgame | None) -> list[str]:
    out = []
    r = model.replay
    if not r.verified_version:
        out.append(f"Versión de guardado {r.header.save_version} sin comprobar: toma las cifras con cautela.")
    if model.tc.observed is None:
        out.append("Esta grabación no trae los avisos de pantalla de este jugador: los paros son una cota "
                   "inferior estimada con las órdenes, no una medición.")
    else:
        out.append(f"Paros medidos con los {len(model.tc.notif.villagers)} avisos de «aldeano creado» de la "
                   "grabación, no estimados.")
    if stats is None:
        out.append("La grabación no trae la tabla final de la partida: no hay resultado ni comparación con el "
                   "rival. Ocurre si la partida no llegó a terminar con la grabación abierta.")
    if abs(model.tc.cal.research_factor - 1) > 0.05:
        out.append(f"Las investigaciones de esta partida no duran lo que dice la tabla de referencia "
                   f"(factor {model.tc.cal.research_factor:.2f}); se calibró con la propia grabación.")
    return out


# --------------------------------------------------------------- entrada

def analyze(replay: Replay, player: int | None = None, forensic: str = "") -> Report:
    h = replay.header
    if player is None:
        humans = [p.number for p in h.players if not p.is_ai]
        player = humans[0] if humans else h.players[0].number
    model = build_model(replay, player)
    me_p = replay.player(player)
    stats = pg_mod.read(replay)
    me_s = None
    if stats:
        me_s = stats.by_color(me_p.color_id) or stats.by_name(me_p.name)
    chains = causal.chains(model)

    findings = _idle_findings(model, chains) + _age_findings(model, stats, me_s) + \
        _villager_finding(stats, me_s)
    findings.sort(key=lambda f: -f.impact)

    result = "desconocido"
    opponent = None
    if me_s is not None:
        result = "victoria" if me_s.victory else "derrota"
    if stats:
        rivals = [p for p in stats.players if me_s is None or p.team != me_s.team]
        rivals = [p for p in rivals if p.collected]
        if rivals:
            opponent = max(rivals, key=lambda p: p.collected).name

    terrain, enemy, my_start, builds = _map_data(model)
    villager_series, stock_series = _series(model)
    return Report(
        name=me_p.name, civ=refdata.civ_name(me_p.civ_id), map_name=refdata.map_name(h.map_id),
        duration_ms=replay.duration_ms, player=player, result=result, opponent=opponent,
        findings=findings, compares=_compares(stats, me_s), marks=_marks(model),
        idle_bands=_idle_bands(model), villager_series=villager_series, stock_series=stock_series,
        buildings=builds, terrain=terrain, enemy_starts=enemy, my_start=my_start,
        quality=_quality(model, stats), measured=model.tc.observed is not None,
        villager_s=model.tc.cal.villager_ms / 1000, stats=stats, forensic=forensic)
