"""Validacion contra la repeticion dentro del juego.

La repeticion del juego, vista desde el jugador analizado, muestra en cada
instante cuatro almacenes exactos y cuantos aldeanos trabajan cada recurso.
Eso es verdad de campo para lo que aqui solo se estima.

Flujo
1. `sheet()` escribe una hoja en blanco con instantes elegidos. Es ciega a
   proposito: no muestra lo que predice el modelo, para no sesgar la lectura.
2. La persona pausa la repeticion en cada instante y apunta lo que ve, con la
   hora exacta del reloj a la que pauso.
3. `compare()` lee la hoja rellena y separa dos clases de control:
   - CONTROLES DUROS. Deben cumplirse siempre; si fallan hay un error en el
     lector, en los costes o en las cotas, no una imprecision del modelo.
   - CONTROLES DEL MODELO. Miden cuanto se equivoca la estimacion.
"""
from __future__ import annotations

import csv
from bisect import bisect_left, bisect_right
from dataclasses import dataclass, field

from . import economy, tc
from .replay import Replay, load_objects

RES = economy.RES
RES_ES = {"Food": "comida", "Wood": "madera", "Gold": "oro", "Stone": "piedra"}
INITIAL_VILLAGERS = 3
# Instantes objetivo: cubren las cuatro edades y los tramos donde el modelo falla
# (madera 11-14, oro 15-22, comida al final) y el paro largo del TC (14:53-18:59).
DEFAULT_TARGETS = ("2:00", "5:00", "8:30", "12:00", "16:00", "18:30", "21:00", "25:00")
COLUMNS = (["reloj"] + [RES_ES[r] for r in RES] + [f"ald_{RES_ES[r]}" for r in RES]
           + ["aldeanos", "tc_produciendo"])


def parse_clock(text: str) -> int:
    parts = [int(p) for p in text.strip().split(":")]
    s = 0
    for p in parts:
        s = s * 60 + p
    return s * 1000


def fmt_clock(ms: float) -> str:
    s = int(ms // 1000)
    return f"{s // 60}:{s % 60:02d}"


@dataclass
class Model:
    """Todo lo que el sistema sabe o estima de una partida, listo para consultar."""
    replay: Replay
    player: int
    tc: tc.TCAnalysis
    eco: economy.Economy
    bounds: list[economy.Bound]

    @property
    def sync_times(self) -> list[int]:
        return [w.t1 for w in self.eco.windows]


def build(replay: Replay, player: int) -> Model:
    a = tc.analyze(replay, player)
    sim = a.calibrated or a.general
    eco = economy.analyze(replay, player, load_objects(replay.path),
                          [(i.end, i.tc) for i in sim.items if i.kind == "villager"],
                          relic_starts=a.notif.relics)
    return Model(replay, player, a, eco, economy.stock_bounds(eco))


def choose_instants(model: Model, targets=DEFAULT_TARGETS) -> list[int]:
    """Para cada objetivo, la muestra de la grabacion mas cercana, redondeada al
    segundo. Asi el total observado se conoce sin interpolar."""
    times = model.sync_times
    out = []
    for target in targets:
        t = parse_clock(target)
        if not times or t > model.replay.duration_ms:
            continue
        i = bisect_left(times, t)
        best = min((j for j in (i - 1, i) if 0 <= j < len(times)), key=lambda j: abs(times[j] - t))
        sec = (times[best] // 1000) * 1000            # el reloj muestra el segundo ya cumplido
        if not out or sec != out[-1]:
            out.append(sec)
    return out


def sheet(model: Model, path: str, instants: list[int] | None = None) -> list[int]:
    instants = instants or choose_instants(model)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        wr = csv.writer(fh)
        wr.writerow(COLUMNS)
        for t in instants:
            wr.writerow([fmt_clock(t)] + [""] * (len(COLUMNS) - 1))
    return instants


# ---------------------------------------------------------------- prediccion

@dataclass
class Prediction:
    t: int
    sync_t: int
    total: int                      # [OBSERVADO] suma de los cuatro en la muestra mas cercana
    tolerance: int                  # [CALCULADO] cuanto puede cambiar el total entre t y la muestra
    lo: dict                        # [CALCULADO] cota inferior por recurso
    hi: dict                        # [CALCULADO] cota superior por recurso
    estimate: dict                  # [ESTIMADO] almacen por recurso
    workers: dict                   # [ESTIMADO] aldeanos por recurso; None = sin clasificar
    villagers_max: int              # [OBSERVADO] 3 iniciales + avisos de aldeano creado
    tcs: int | None                 # [OBSERVADO] TC terminados, por avisos
    tcs_producing: int | None       # [CALCULADO] TC ocupados, por avisos y calibracion


def predict(model: Model, t: int) -> Prediction:
    eco, times = model.eco, model.sync_times
    i = bisect_left(times, t)
    k = min((j for j in (i - 1, i) if 0 <= j < len(times)), key=lambda j: abs(times[j] - t))
    w = eco.windows[k]
    a, b = sorted((t, w.t1))
    spent = sum(s.total for s in eco.spends if a < s.t <= b)
    nxt = eco.windows[min(k + 1, len(eco.windows) - 1)]
    rate = max(w.income / max(w.t1 - w.t0, 1), nxt.income / max(nxt.t1 - nxt.t0, 1), 0)
    tol = round(rate * (b - a + 1000)) + spent + 5       # +1 s: el reloj no da milisegundos
    workers = eco.alloc.at(t) if eco.alloc else {}
    notif = model.tc.notif
    tcs = producing = None
    if model.tc.observed:
        obs = model.tc.observed
        tcs = sum(d for s, d in obs.capacity_steps if s <= t)
        producing = min(tcs, sum(1 for s, e in obs.spans if s <= t < e))
    return Prediction(t, w.t1, w.stock1, tol, model.bounds[k].lo, model.bounds[k].hi,
                      eco.series[k][1] if eco.series else {}, workers,
                      INITIAL_VILLAGERS + bisect_right(sorted(notif.villagers), t), tcs, producing)


# ---------------------------------------------------------------- comparacion

@dataclass
class Observation:
    t: int
    stock: dict = field(default_factory=dict)      # recurso -> valor leido
    workers: dict = field(default_factory=dict)    # recurso -> aldeanos leidos
    villagers: int | None = None
    tcs_producing: int | None = None


def read_sheet(path: str) -> list[Observation]:
    out = []
    with open(path, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            if not (row.get("reloj") or "").strip():
                continue

            def num(col):
                v = (row.get(col) or "").strip().replace(".", "")
                return int(v) if v else None
            o = Observation(parse_clock(row["reloj"]))
            for r in RES:
                if (v := num(RES_ES[r])) is not None:
                    o.stock[r] = v
                if (v := num(f"ald_{RES_ES[r]}")) is not None:
                    o.workers[r] = v
            o.villagers = num("aldeanos")
            o.tcs_producing = num("tc_produciendo")
            out.append(o)
    return out


@dataclass
class Check:
    t: int
    kind: str          # "duro" | "modelo"
    what: str
    ok: bool
    detail: str


@dataclass
class Result:
    checks: list[Check]
    stock_error: dict          # recurso -> lista de (observado - estimado)
    worker_error: dict         # recurso -> lista de (observado - estimado)
    unfilled: int

    def hard_failures(self) -> list[Check]:
        return [c for c in self.checks if c.kind == "duro" and not c.ok]

    def mean_abs(self, errors: dict) -> dict:
        return {r: sum(abs(x) for x in v) / len(v) for r, v in errors.items() if v}


def compare(model: Model, observations: list[Observation]) -> Result:
    checks: list[Check] = []
    stock_err = {r: [] for r in RES}
    work_err = {r: [] for r in RES}
    unfilled = 0
    for o in observations:
        p = predict(model, o.t)
        if not o.stock and not o.workers and o.villagers is None and o.tcs_producing is None:
            unfilled += 1
            continue
        clk = fmt_clock(o.t)
        if len(o.stock) == 4:
            seen = sum(o.stock.values())
            checks.append(Check(o.t, "duro", "suma de almacenes = total de la grabación",
                                abs(seen - p.total) <= p.tolerance,
                                f"{clk}: en pantalla {seen}, grabación {p.total} a las {fmt_clock(p.sync_t)}, "
                                f"margen ±{p.tolerance}"))
        for r, v in o.stock.items():
            lo, hi = p.lo[r] - p.tolerance, p.hi[r] + p.tolerance
            checks.append(Check(o.t, "duro", f"{RES_ES[r]} dentro de las cotas", lo <= v <= hi,
                                f"{clk}: {v} en [{max(lo, 0)}, {hi}]"))
            if r in p.estimate:
                stock_err[r].append(v - p.estimate[r])
        if o.villagers is not None:
            checks.append(Check(o.t, "duro", "aldeanos ≤ iniciales + creados", o.villagers <= p.villagers_max,
                                f"{clk}: {o.villagers} vivos, {p.villagers_max} como máximo; "
                                f"{p.villagers_max - o.villagers} muertos o sin contar"))
        for r, v in o.workers.items():
            est = p.workers.get(r, 0)
            work_err[r].append(v - est)
            checks.append(Check(o.t, "modelo", f"aldeanos en {RES_ES[r]}", abs(v - est) <= 2,
                                f"{clk}: {v} en pantalla, {est} estimados"))
        if o.tcs_producing is not None and p.tcs_producing is not None:
            checks.append(Check(o.t, "modelo", "TC produciendo", o.tcs_producing == p.tcs_producing,
                                f"{clk}: {o.tcs_producing} de {p.tcs} en pantalla, {p.tcs_producing} según avisos"))
    return Result(checks, stock_err, work_err, unfilled)


def render(model: Model, result: Result) -> str:
    L: list[str] = []
    w = L.append
    w("# Validación contra la repetición")
    w("")
    w("Los **controles duros** deben cumplirse siempre: un fallo indica un error del lector, "
      "de los costes o de las cotas. Los **controles del modelo** miden su precisión.")
    w("")
    hard = [c for c in result.checks if c.kind == "duro"]
    soft = [c for c in result.checks if c.kind == "modelo"]
    w(f"- Controles duros: {sum(c.ok for c in hard)} de {len(hard)} cumplidos.")
    w(f"- Controles del modelo: {sum(c.ok for c in soft)} de {len(soft)} dentro del margen.")
    if result.unfilled:
        w(f"- Filas sin rellenar: {result.unfilled}.")
    w("")
    if result.hard_failures():
        w("## Fallos duros")
        w("")
        for c in result.hard_failures():
            w(f"- {c.what}. {c.detail}")
        w("")
    ms = result.mean_abs(result.stock_error)
    mw = result.mean_abs(result.worker_error)
    if ms or mw:
        w("## Error medio del modelo [CALCULADO]")
        w("")
        w("| Recurso | Almacén (observado − estimado, media absoluta) | Aldeanos |")
        w("|---|---|---|")
        for r in RES:
            a = f"{ms[r]:.0f}" if r in ms else "—"
            b = f"{mw[r]:.1f}" if r in mw else "—"
            w(f"| {RES_ES[r].capitalize()} | {a} | {b} |")
        w("")
    w("## Detalle")
    w("")
    for c in result.checks:
        w(f"- {'✔' if c.ok else '✘'} [{c.kind}] {c.what}. {c.detail}")
    w("")
    return "\n".join(L)
