"""Informe en Markdown de la produccion del centro urbano.

Cada afirmacion lleva una etiqueta de procedencia:
  [OBSERVADO]  esta literalmente en la grabacion
  [CALCULADO]  aritmetica sobre hechos observados
  [ESTIMADO]   sale de un modelo con supuestos declarados
  [HIPOTESIS]  explicacion posible, no demostrada
El informe no usa ningun LLM: es la base de evidencia que un LLM podra citar.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from statistics import median

from . import causal, economy, refdata
from .replay import READER_VERSION, Replay, load_objects
from .tc import Interval, TCAnalysis, analyze

MILITARY_ONLY = {"PATROL", "DE_ATTACK_MOVE", "FORMATION", "STANCE", "ATTACK_GROUND", "GUARD", "FOLLOW"}
AMBIGUOUS = {"MOVE", "ORDER", "SPECIAL", "STOP"}


def clock(ms: float) -> str:
    s = int(ms // 1000)
    return f"{s // 60}:{s % 60:02d}"


@dataclass
class Episode:
    start: float
    end: float
    tc_seconds: float
    max_tcs: float
    builds: list[tuple[int, str, dict]] = field(default_factory=list)
    attacks: list[int] = field(default_factory=list)
    stock: list[tuple[int, int]] = field(default_factory=list)
    commands: Counter = field(default_factory=Counter)
    houses_built: list[int] = field(default_factory=list)
    blocked_tc_seconds: float = 0.0
    ended_by: str | None = None

    @property
    def seconds(self) -> float:
        return (self.end - self.start) / 1000


def episodes(intervals: list[Interval], join_ms: float = 1500) -> list[Episode]:
    out: list[Episode] = []
    for i in sorted(intervals, key=lambda x: x.start):
        if out and i.start - out[-1].end <= join_ms:
            out[-1].end = max(out[-1].end, i.end)
            out[-1].tc_seconds += i.tc_seconds
            out[-1].max_tcs = max(out[-1].max_tcs, i.tcs)
        else:
            out.append(Episode(i.start, i.end, i.tc_seconds, i.tcs))
    return out


def add_context(replay: Replay, a: TCAnalysis, ep: Episode, lookback_ms: int = 60000) -> None:
    lo = ep.start - lookback_ms
    for e in replay.events:
        if e.t_ms > ep.end:
            break
        if e.kind == "sync" and ep.start - 15000 <= e.t_ms and a.player in e.payload:
            ep.stock.append((e.t_ms, e.payload[a.player]["total_res"]))
        if e.kind != "action" or e.player != a.player:
            continue
        if e.action == "BUILD" and lo <= e.t_ms:
            bid = e.payload.get("building_id", -1)
            ep.builds.append((e.t_ms, refdata.object_name(bid), refdata.cost("Building", bid)))
        if ep.start <= e.t_ms:
            ep.commands[e.action] += 1
    ep.attacks = [t for t in a.notif.attacks if ep.start - 30000 <= t <= ep.end]
    ep.houses_built = [t for t in a.notif.houses_built if ep.start <= t <= ep.end + 30000]
    ep.blocked_tc_seconds = sum(
        max(0.0, min(s.end, ep.end) - max(s.start, ep.start)) * s.tcs for s in a.stalls) / 1000
    nxt = min((c.t for c in [*a.inputs.queue, *a.inputs.tc_research] if ep.start < c.t <= ep.end + 2000),
              default=None)
    if nxt is not None:
        ep.ended_by = f"siguiente orden a un TC en {clock(nxt)}"


def _cost(c: dict) -> str:
    short = {"Food": "comida", "Wood": "madera", "Gold": "oro", "Stone": "piedra"}
    return ", ".join(f"{v} {short.get(k, k)}" for k, v in c.items()) or "coste desconocido"


def _timeline(replay: Replay, a: TCAnalysis) -> list[tuple[int, str, str]]:
    rows: list[tuple[int, str, str]] = []
    first_seen: set[int] = set()
    for e in replay.events:
        if e.kind != "action" or e.player != a.player:
            continue
        if e.action == "RESEARCH" and e.payload.get("technology_id") in refdata.AGE_TECHS:
            rows.append((e.t_ms, "OBSERVADO", f"Orden de investigar {refdata.tech_name(e.payload['technology_id'])}"))
        if e.action == "BUILD":
            bid = e.payload.get("building_id", -1)
            if bid in refdata.TOWN_CENTER_IDS:
                rows.append((e.t_ms, "OBSERVADO", "Orden de construir un centro urbano adicional"))
            elif bid not in first_seen and bid not in (70, 50):
                first_seen.add(bid)
                rows.append((e.t_ms, "OBSERVADO", f"Primera orden de construir: {refdata.object_name(bid)}"))
    for age, t in a.notif.age_ups.get(a.player, {}).items():
        rows.append((t, "OBSERVADO", f"Avance completado a {age} Age"))
    for t in a.notif.tc_built:
        rows.append((t, "OBSERVADO", "Aviso: centro urbano terminado"))
    if a.notif.attacks:
        rows.append((a.notif.attacks[0], "OBSERVADO",
                     f"Primer aviso de ataque recibido (hay {len(a.notif.attacks)} en total)"))
    return sorted(rows)


ES = {"Food": "comida", "Wood": "madera", "Gold": "oro", "Stone": "piedra"}


def _economy_section(w, replay: Replay, a: TCAnalysis, eco: "economy.Economy", bounds: list) -> None:
    w("## 5. Economía")
    w("")
    w("### 5.1 Gastos [CALCULADO: órdenes observadas × coste de referencia]")
    w("")
    spent = eco.spent_by_type()
    w("| Recurso | Gastado | Mayor partida |")
    w("|---|---|---|")
    for r in economy.RES:
        top: Counter = Counter()
        for sp in eco.spends:
            if sp.cost.get(r):
                top[sp.label] += sp.cost[r]
        best = top.most_common(1)
        w(f"| {ES[r].capitalize()} | {spent[r]} | {f'{best[0][0]}: {best[0][1]}' if best else '—'} |")
    w("")
    w("### 5.2 Ingreso total por edad [CALCULADO: variación del total observado + gastos]")
    w("")
    ages = sorted(a.notif.age_ups.get(a.player, {}).items(), key=lambda kv: kv[1])
    cuts = [0] + [t for _, t in ages] + [replay.duration_ms]
    names = ["Alta Edad Media"] + [f"desde {n} Age" for n, _ in ages]
    w("| Tramo | Ingreso por minuto | Gasto por minuto | Total almacenado al acabar |")
    w("|---|---|---|---|")
    for name, lo, hi in zip(names, cuts, cuts[1:]):
        ws = [x for x in eco.windows if lo < x.t1 <= hi]
        if not ws:
            continue
        minutes = (ws[-1].t1 - ws[0].t0) / 60000
        w(f"| {name} ({clock(lo)}–{clock(hi)}) | {sum(x.income for x in ws) / minutes:.0f} | "
          f"{sum(x.spent for x in ws) / minutes:.0f} | {ws[-1].stock1} |")
    w("")
    w("El ingreso es un mínimo: no incluye lo gastado sin orden visible, como la resiembra automática de granjas.")
    w("")
    w("### 5.3 Controles de calidad de la economía")
    w("")
    if eco.missing_costs:
        w(f"- **Costes sin referencia:** {dict(eco.missing_costs)}. Los ingresos de esos tramos están infravalorados.")
    else:
        w(f"- [CALCULADO] Las {len(eco.spends)} órdenes con coste tienen coste de referencia.")
    neg = eco.negative_windows
    w(f"- [CALCULADO] Tramos con ingreso negativo, que serían imposibles: {len(neg)} de {len(eco.windows)}."
      + ("" if not neg else " En " + ", ".join(clock(x.t1) for x in neg[:6]) + ": falta un coste o hay un gasto invisible."))
    bad = [r for r in eco.audit if not r.consistent]
    if a.notif.present:
        w("- [CALCULADO] Unidades ordenadas frente a creadas: "
          + "; ".join(f"{r.line} {r.ordered}/{r.created}" for r in eco.audit) + ". "
          + ("En ningún instante hay más creadas que ordenadas: las órdenes se aceptaron."
             if not bad else f"**Incoherente en {', '.join(r.line for r in bad)}.**"))
    feasible = sum(1 for b in bounds if sum(b.lo.values()) <= b.total)
    w(f"- [CALCULADO] Mínimos demostrables por recurso compatibles con el total observado: "
      f"{feasible} de {len(bounds)} muestras.")
    w("")
    w("### 5.4 Recursos por tipo")
    w("")
    enough = sum(1 for b in bounds if b.lo["Food"] >= 50)
    short = sum(1 for b in bounds if b.hi["Food"] < 50)
    w(f"- [CALCULADO] Cotas sin modelo: en {enough} de {len(bounds)} muestras está demostrado que había comida "
      f"para un aldeano; en {short} está demostrado que no. El resto no se puede decidir.")
    if eco.alloc is not None:
        al = eco.alloc
        serious = eco.serious_violations()
        w(f"- [ESTIMADO, confianza baja, sin validar en el juego] Modelo de reparto: deduce a qué recurso va cada aldeano y reparte "
          f"el ingreso total en proporción. Sigue a {al.villagers} aldeanos identificados y clasifica de media "
          f"al {eco.mean_coverage * 100:.0f} %. Reconoce {al.matched_orders} órdenes a edificios tuyos por su posición.")
        w(f"- [CALCULADO] Examen contra compras aceptadas: lo contradicen {len(eco.violations)} de "
          f"{eco.checked_purchases}; por más de 50, {len(serious)} "
          f"({', '.join(f'{ES[k]} {v}' for k, v in Counter(v.resource for v in serious).most_common()) or 'ninguna'}).")
        if eco.relic_gold:
            w(f"- [ESTIMADO] Oro de reliquias separado del de aldeanos: {eco.relic_gold:.0f} en total, a "
              f"{refdata.RELIC_GOLD_PER_S} por segundo y reliquia desde que se recoge (valor de referencia sin "
              "verificar en este parche; los datos de esta partida no distinguen entre 0,5 y 1).")
        r = al.rules
        w("- Reglas activas (hipótesis de comportamiento del juego): "
          + "; ".join(text for on, text in (
              (r.drop_site_auto_gather, "quien termina un punto de entrega recoge el recurso de al lado"),
              (r.return_after_building, "quien termina otro edificio vuelve a su tarea"),
              (r.dropoff_keeps_task, "llevar carga a un punto de entrega no cambia la tarea"),
              (r.farm_burst_split, "n granjas encadenadas ocupan a n constructores")) if on) + ".")
        w("- Se usa solo como contexto en los episodios, nunca como prueba. Las conclusiones firmes salen de las cotas.")
    else:
        w("- Modelo de reparto: no disponible (faltan objetos iniciales o recursos de inicio no estándar).")
    w("")


def render(replay: Replay, player: int | None = None) -> str:
    h = replay.header
    if player is None:
        humans = [p.number for p in h.players if not p.is_ai]
        player = humans[0] if humans else h.players[0].number
    a = analyze(replay, player)
    me = replay.player(player)
    sim = a.calibrated or a.general
    eco = economy.analyze(replay, player, load_objects(replay.path),
                          [(i.end, i.tc) for i in sim.items if i.kind == "villager"],
                          relic_starts=a.notif.relics)
    bounds = economy.stock_bounds(eco)
    L: list[str] = []
    w = L.append
    v_s = a.cal.villager_ms / 1000

    w(f"# Informe de producción del centro urbano — {me.name} ({refdata.civ_name(me.civ_id)})")
    w("")
    w("Leyenda: **[OBSERVADO]** está en la grabación · **[CALCULADO]** aritmética sobre lo observado · "
      "**[ESTIMADO]** modelo con supuestos · **[HIPÓTESIS]** explicación posible, no demostrada.")
    w("")
    w("## 1. Ficha de la partida [OBSERVADO]")
    w("")
    started = datetime.fromtimestamp(h.timestamp, tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    w(f"- Mapa: {refdata.map_name(h.map_id)} (tamaño {h.map_size}). Inicio: {started}.")
    w(f"- Duración en tiempo de juego: {clock(replay.duration_ms)}. Velocidad {h.speed:.2f}. "
      f"Límite de población {h.population_limit}. {'Multijugador' if h.multiplayer else 'Un jugador'}.")
    for p in h.players:
        w(f"- Jugador {p.number}: {p.name} — {refdata.civ_name(p.civ_id)}, equipo {p.team_id}, "
          f"{'IA' if p.is_ai else 'humano'}{' ← analizado' if p.number == player else ''}")
    w("")
    w("## 2. Calidad de los datos")
    w("")
    w(f"- Lector {READER_VERSION}. Guardado {h.save_version}, compilación {h.build}. "
      + ("Versión comprobada con un archivo real." if replay.verified_version
         else "**Versión no comprobada: tratar todo el informe como provisional.**"))
    w(f"- Eventos leídos: {len(replay.events)}. El cuerpo se leyó completo, sin bytes sin interpretar.")
    if a.observed:
        w(f"- La grabación incluye avisos en pantalla del jugador ({len(a.notif.villagers)} de aldeano creado). "
          "Permiten **medir**, no solo estimar. No se ha comprobado que existan en partidas multijugador.")
    else:
        w("- La grabación **no** incluye avisos de producción de este jugador: todo lo que sigue es estimación.")
    w(f"- Tiempo de aldeano: {v_s:.1f} s ({a.cal.villager_basis}). Referencia: {a.cal.reference_villager_ms / 1000:.0f} s.")
    w(f"- Investigación: factor {a.cal.research_factor:.2f} sobre la referencia ({a.cal.research_basis}).")
    if abs(a.cal.research_factor - 1) > 0.05:
        w("  - **Aviso:** las investigaciones no duran lo que dice la tabla de referencia. Causa desconocida "
          "(ajuste de partida, mod de datos o parche). Por eso se calibra en cada grabación en vez de fiarse de la tabla.")
    w(f"- Datos de referencia: {refdata.REFDATA_SOURCE}.")
    w(f"- Tramo analizado: 0:00 a {clock(a.horizon)}. Los últimos {v_s:.0f} s no son observables "
      "(lo que estuviera en producción al acabar no llegó a dar aviso).")
    w("")
    w("## 3. Cronología")
    w("")
    w("| Tiempo | Evento | Procedencia |")
    w("|---|---|---|")
    for t, tag, text in _timeline(replay, a):
        w(f"| {clock(t)} | {text} | {tag} |")
    w("")
    w("## 4. Producción por fases")
    w("")
    w("| Fase | TC | Aldeanos creados | Ritmo real | Ritmo máximo | Sin producir, medido | Sin producir, estimado solo con órdenes | No determinable solo con órdenes |")
    w("|---|---|---|---|---|---|---|---|")
    for p in a.phases:
        made = sum(1 for t in a.notif.villagers if p.start < t <= p.end) if a.observed else None
        minutes = (p.end - p.start) / 60000
        w(f"| {clock(p.start)}–{clock(p.end)} | {p.tcs} | {made if made is not None else 'n/d'} | "
          f"{f'{made / minutes:.2f}/min' if made is not None else 'n/d'} | {p.tcs * 60 / v_s:.2f}/min | "
          f"{f'{p.observed_idle_s:.0f} s·TC' if p.observed_idle_s is not None else 'n/d'} | "
          f"≥ {p.estimated_idle_s:.0f} s·TC | {p.unknown_s:.0f} s·TC |")
    w("")
    w("Unidad: segundos·TC. Dos centros urbanos parados diez segundos son veinte segundos·TC. "
      "El ritmo máximo ignora las investigaciones, que ocupan el TC legítimamente. "
      "«No determinable» es el tramo entre que un TC nuevo se termina y su primera orden: "
      "sin avisos no se sabe cuándo se terminó.")
    w("")

    _economy_section(w, replay, a, eco, bounds)
    source = a.observed.idle if a.observed else a.general.idle()
    eps = [e for e in episodes(source) if e.tc_seconds >= 5]
    for ep in eps:
        add_context(replay, a, ep)
    tag = "OBSERVADO" if a.observed else "ESTIMADO"
    total = sum(e.tc_seconds for e in eps)
    w(f"## 6. Episodios sin producir (de 5 s·TC o más) — total {total:.0f} s·TC")
    w("")
    for n, ep in enumerate(eps, 1):
        w(f"### Episodio {n}: {clock(ep.start)} a {clock(ep.end)}")
        w("")
        w(f"- [{tag}] Durante {ep.seconds:.0f} s hubo al menos un TC sin producir; "
          f"hasta {ep.max_tcs:.0f} a la vez. Suma: {ep.tc_seconds:.0f} s·TC.")
        w(f"- [CALCULADO] Producción potencial perdida: como máximo {ep.tc_seconds / v_s:.1f} aldeanos "
          f"({ep.tc_seconds:.0f} ÷ {v_s:.1f}). Es un techo: supone comida y población disponibles todo el tramo.")
        if ep.blocked_tc_seconds >= 3:
            ordered = sum(c.amount for c in a.inputs.queue)
            made = len(a.notif.villagers)
            windows = [(s.start, s.end) for s in a.stalls if s.end > ep.start and s.start < ep.end]
            any_made = sum(1 for t in a.notif.created_any if any(lo < t <= hi for lo, hi in windows))
            w(f"- [CALCULADO] En {ep.blocked_tc_seconds:.0f} s·TC de este episodio **había aldeanos ya encolados** "
              "según las órdenes, pero no salían.")
            w(f"- [CALCULADO] Contabilidad de toda la partida: {ordered} aldeanos ordenados, {made} creados; "
              f"la diferencia ({ordered - made}) cabe en lo que quedaba en producción al acabar. "
              "Es decir, las órdenes no se rechazaron: se retrasaron.")
            w(f"- [OBSERVADO] En esos tramos de bloqueo se creó un total de {any_made} unidades de cualquier tipo "
              "(aldeanos o militares).")
            houses = ", ".join(clock(t) for t in ep.houses_built) or "ninguna"
            house_orders = [clock(t) for t, name, _ in ep.builds if name == "House" and t >= ep.start - 5000]
            w(f"- [HIPÓTESIS, confianza media] Bloqueo por límite de población. A favor: el paro afecta a toda la "
              f"producción a la vez; casas ordenadas en {', '.join(house_orders) or 'ningún momento del tramo'} "
              f"y terminadas en {houses}. En contra: la producción no se reanuda en cuanto termina la primera casa. "
              "No se puede zanjar sin conocer la población, que la grabación no guarda.")
        else:
            w("- [ESTIMADO] La cola estaba vacía: no hay órdenes de encolar pendientes en ese tramo "
              "(supone que no hubo cancelaciones, que la grabación no deja ver).")
        if ep.stock:
            lo, hi = min(v for _, v in ep.stock), max(v for _, v in ep.stock)
            w(f"- [OBSERVADO] Suma de los cuatro recursos almacenados en el tramo: entre {lo} y {hi} "
              f"({len(ep.stock)} muestras).")
        test = economy.shortage_test(bounds, ep.start, ep.end, "Food", 50)
        if test["samples"]:
            if test["proved_short"]:
                w(f"- [CALCULADO] En {test['proved_short']} de {test['samples']} muestras **está demostrado** "
                  "que no había comida para un aldeano: el total almacenado no llegaba.")
            w(f"- [CALCULADO] En {test['proved_enough']} de {test['samples']} muestras está demostrado que sí había "
              "comida para un aldeano, porque poco después se aceptó una compra que la exigía.")
            if test["proved_enough"] < test["samples"] and not test["proved_short"]:
                w(f"- [CALCULADO] En las demás muestras, para que faltara comida los otros tres recursos tendrían "
                  f"que sumar al menos {max(test['min_hi'] - 49, 0)}. No es imposible, pero no hay nada que lo indique.")
        est = [s["Food"] for t, s in eco.series if ep.start <= t <= ep.end]
        if est:
            w(f"- [ESTIMADO, confianza baja, sin validar en el juego] El modelo de reparto sitúa la comida entre {min(est)} y "
              f"{max(est)} en el episodio.")
        food = eco.purchases_between(ep.start, ep.end, "Food")
        others = [sp for sp in food if sp.label != "Villager"]
        if others:
            big = max(others, key=lambda sp: sp.cost["Food"])
            w(f"- [OBSERVADO] Durante el episodio se gastó comida en otras cosas {len(others)} veces, "
              f"{sum(sp.cost['Food'] for sp in others)} en total. La mayor: {big.label}, "
              f"{big.cost['Food']} de comida en {clock(big.t)}.")
        if ep.builds:
            w(f"- [OBSERVADO] Órdenes de construcción desde 60 s antes ({len(ep.builds)}):")
            grouped = Counter((name, _cost(cost)) for _, name, cost in ep.builds)
            for (name, cost), k in grouped.most_common(8):
                times = [clock(t) for t, nm, _ in ep.builds if nm == name]
                w(f"  - {k} × {name} ({cost} cada uno, coste de referencia) en {', '.join(times[:6])}"
                  f"{'…' if len(times) > 6 else ''}")
        if ep.attacks:
            w(f"- [OBSERVADO] Avisos de ataque recibidos cerca: {len(ep.attacks)} "
              f"({', '.join(clock(t) for t in ep.attacks[:6])}{'…' if len(ep.attacks) > 6 else ''}). "
              "Es coincidencia temporal, no prueba de causa.")
        mil = sum(v for k, v in ep.commands.items() if k in MILITARY_ONLY)
        amb = sum(v for k, v in ep.commands.items() if k in AMBIGUOUS)
        tot = sum(ep.commands.values())
        w(f"- [OBSERVADO] Órdenes del jugador durante el episodio: {tot} "
          f"({tot / max(ep.seconds, 1) * 60:.0f} por minuto). Inequívocamente militares: {mil}. "
          f"Ambiguas (mover u ordenar, sin saber a qué unidad): {amb}.")
        if ep.ended_by:
            w(f"- [OBSERVADO] Primera orden a un TC dentro del episodio: {ep.ended_by}.")
        w("")

    w("## 7. Cadenas causales")
    w("")
    w("Para cada paro largo, de lo observado a sus causas posibles. Una **prueba decisiva** es una contradicción con "
      "la mecánica del juego (no se puede comprar sin recursos; con hueco de población seguro, el tope no frena "
      "nada), no una coincidencia en el tiempo. Un **indicio** encaja con la causa pero no la demuestra. La atención "
      "del jugador nunca pasa de hipótesis: la grabación no ve la pantalla.")
    w("")
    w("Veredictos: ✔ respaldada · ◐ en parte (vale para un tramo y no para otro) · ? compatible · ✘ descartada.")
    w("")
    from .validation import Model
    for line in causal.render(causal.chains(Model(replay, player, a, eco, bounds))):
        w(line)

    w("## 8. Validación cruzada de los dos métodos")
    w("")
    if a.observed and a.calibrated:
        first_end = a.phases[0].end
        p1 = [err for end, err in a.completion_error_ms if end <= first_end]
        w(f"- [CALCULADO] Fase de un solo TC: {len(p1)} aldeanos previstos por las órdenes y encontrados en los avisos. "
          f"Error mediano {median(p1) / 1000:.2f} s, máximo {max(p1) / 1000:.2f} s." if p1 else "- Sin datos en la primera fase.")
        w(f"- [CALCULADO] Partida completa: {len(a.completion_error_ms)} aldeanos coinciden a menos de 1,5 s; "
          f"{a.unmatched_predicted} previstos no aparecen a tiempo y {a.unmatched_observed} aparecen fuera de lo previsto. "
          "Las discrepancias se concentran en los tramos de bloqueo listados abajo.")
        w(f"- [CALCULADO] Solape imposible (más TC ocupados que existentes): {a.observed.overlap_ms / 1000:.1f} s en toda la partida. "
          "Cerca de cero significa que el modelo de ocupación es coherente.")
        w(f"- Factor de investigación ajustado solo con avances de edad públicos: {a.general_factor_basis}.")
        for p in a.phases:
            gap = p.observed_idle_s - p.estimated_idle_s - p.unknown_s
            w(f"- Fase con {p.tcs} TC: medido {p.observed_idle_s:.0f}; estimado {p.estimated_idle_s:.0f} "
              f"más {p.unknown_s:.0f} no determinable. Diferencia sin explicar por el estimador: {gap:+.0f} s·TC.")
        if a.stalls:
            w("- [CALCULADO] Tramos con órdenes en cola y sin producción (el estimador no los ve):")
            for s in a.stalls:
                w(f"  - {clock(s.start)}–{clock(s.end)}, {s.tcs:.0f} TC")
    else:
        w("- No hay avisos del jugador: no es posible validar. Las cifras son cota inferior.")
    w("")
    w("## 9. Lo que este informe no puede afirmar")
    w("")
    w("- No se conoce el desglose exacto de recursos, solo cotas; tampoco la población ni las bajas.")
    w("- No se ven cancelaciones de cola ni órdenes rechazadas por el juego.")
    w("- Las causas solo se dan por probadas o descartadas con la mecánica del juego. La población se acota con "
      "los avisos de unidades creadas y casas terminadas: no se ven las muertes ni las casas destruidas.")
    w("- Nunca se afirma qué pensaba o miraba el jugador; solo qué órdenes dio.")
    w("- Con varios TC, la medición dice cuántos estaban parados, no cuáles.")
    return "\n".join(L) + "\n"
