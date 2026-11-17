"""Pruebas del prototipo. Las de `rec` usan una grabacion real (guardado 68.9)."""
from pathlib import Path
from statistics import median

import pytest

from aoe2coach import refdata, replay, tc
from aoe2coach.report import render

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "rec.aoe2record"


@pytest.fixture(scope="module")
def rec():
    if not FIXTURE.exists():
        pytest.skip("falta la grabacion de prueba")
    return replay.load(str(FIXTURE), with_sync=True)


@pytest.fixture(scope="module")
def analysis(rec):
    return tc.analyze(rec, 1)


# ---- lectura ----------------------------------------------------------------

def test_header_facts(rec):
    h = rec.header
    assert (h.save_major, h.save_minor) == (68, 9)
    assert rec.verified_version
    assert refdata.map_name(h.map_id) == "Arabia"
    assert [p.is_ai for p in h.players] == [False, True, True, True]
    assert refdata.civ_name(rec.player(1).civ_id) == "Georgians"


def test_body_is_read_to_the_end(rec):
    assert rec.duration_ms == 1_704_362
    assert sum(1 for e in rec.events if e.kind == "action") == 114_906
    assert not any((e.action or "").startswith("UNKNOWN_") for e in rec.events)


def test_every_event_is_traceable(rec):
    offsets = [e.offset for e in rec.events]
    assert offsets == sorted(offsets) and len(set(offsets)) == len(offsets)


@pytest.mark.parametrize("blob", [b"", b"\x00" * 64, b"\xff" * 4096])
def test_garbage_is_rejected_not_guessed(tmp_path, blob):
    bad = tmp_path / "bad.aoe2record"
    bad.write_bytes(blob)
    with pytest.raises(replay.UnsupportedReplay):
        replay.load(str(bad))


def test_truncated_header_is_rejected(tmp_path):
    if not FIXTURE.exists():
        pytest.skip("falta la grabacion de prueba")
    bad = tmp_path / "cut.aoe2record"
    bad.write_bytes(FIXTURE.read_bytes()[:5000])
    with pytest.raises(replay.UnsupportedReplay):
        replay.load(str(bad))


# ---- simulacion por ordenes (sin grabacion) ---------------------------------

def _inputs(queue, research=()):
    tcs = sorted({t for c in queue for t in c.tcs} | {c.building for c in research})
    return tc.Inputs(1, tcs, {t: 0 for t in tcs}, list(queue), list(research), list(research))


def test_single_tc_gap_is_idle():
    q = [tc.QueueCmd(0, 2, (10,), 83, 0), tc.QueueCmd(60_000, 1, (10,), 83, 1)]
    sim = tc.simulate(_inputs(q), 25_000, 1.0, {10: 0}, 100_000)
    idle = sim.idle()
    assert [(i.start, i.end) for i in idle] == [(50_000, 60_000), (85_000, 100_000)]


def test_research_occupies_the_tc_and_is_not_idle():
    q = [tc.QueueCmd(0, 1, (10,), 83, 0)]
    r = [tc.ResearchCmd(1_000, 101, 10, 1)]          # Feudal: 130 s de referencia
    sim = tc.simulate(_inputs(q, r), 25_000, 1.0, {10: 0}, 200_000)
    feudal = next(i for i in sim.items if i.kind == "research")
    assert (feudal.start, feudal.end) == (25_000, 155_000)   # espera a que acabe el aldeano
    assert [(i.start, i.end) for i in sim.idle()] == [(155_000, 200_000)]


def test_multi_tc_order_is_shared_not_multiplied():
    q = [tc.QueueCmd(0, 5, (10, 11, 12), 83, 0)]
    sim = tc.simulate(_inputs(q), 25_000, 1.0, {10: 0, 11: 0, 12: 0}, 100_000)
    assert len(sim.items) == 5
    assert sorted(sum(1 for i in sim.items if i.tc == t) for t in (10, 11, 12)) == [1, 2, 2]


# ---- contra la grabacion real ------------------------------------------------

def test_calibration_matches_the_recording(analysis):
    assert analysis.cal.villager_ms == pytest.approx(24_800, abs=50)
    assert analysis.cal.research_factor == pytest.approx(0.40, abs=0.01)


def test_orders_predict_observed_villagers_with_one_tc(analysis):
    end = analysis.phases[0].end
    errs = [err for t, err in analysis.completion_error_ms if t <= end]
    assert len(errs) >= 25
    assert median(errs) < 200 and max(errs) < 1000


def test_estimate_agrees_with_measurement_with_one_tc(analysis):
    p = analysis.phases[0]
    assert abs(p.observed_idle_s - p.estimated_idle_s) < 5


def test_estimate_is_a_lower_bound_in_every_phase(analysis):
    for p in analysis.phases:
        assert p.estimated_idle_s <= p.observed_idle_s + 5


def test_occupancy_model_is_consistent(analysis):
    assert analysis.observed.overlap_ms < 2_000      # nunca mas TC ocupados que existentes


def test_orders_are_all_accounted_for(analysis):
    ordered = sum(c.amount for c in analysis.inputs.queue)
    made = len(analysis.notif.villagers)
    assert 0 <= ordered - made <= len(analysis.inputs.tcs)


def test_without_notifications_everything_is_estimate(rec):
    a = tc.analyze(rec, 2)                           # una IA: no hay avisos suyos
    assert a.observed is None and a.calibrated is None
    assert all(p.observed_idle_s is None for p in a.phases)


def test_report_labels_provenance(rec):
    text = render(rec, 1)
    for tag in ("[OBSERVADO]", "[CALCULADO]", "[ESTIMADO]", "[HIPÓTESIS"):
        assert tag in text
    assert "se distrajo" not in text


# ---- economia ----------------------------------------------------------------

from aoe2coach import economy  # noqa: E402


@pytest.fixture(scope="module")
def eco(rec, analysis):
    objects = replay.load_objects(str(FIXTURE))
    creations = [(i.end, i.tc) for i in analysis.calibrated.items if i.kind == "villager"]
    return economy.analyze(rec, 1, objects, creations)


def test_header_objects_confirm_the_tc_inferred_from_orders(analysis):
    objects = replay.load_objects(str(FIXTURE))
    tc0 = objects[analysis.inputs.tcs[0]]
    assert (tc0.owner, tc0.object_id) == (1, 109)


def test_every_order_has_a_reference_cost(eco):
    assert not eco.missing_costs
    assert eco.spent_by_type() == {"Food": 16820, "Wood": 9860, "Gold": 8045, "Stone": 800}


def test_starting_stock_is_recovered_from_the_first_sample(eco):
    assert eco.start_total == 700


def test_derived_income_is_never_negative(eco):
    assert eco.negative_windows == []


def test_units_created_never_exceed_units_ordered(eco):
    assert eco.audit and all(row.consistent for row in eco.audit)
    assert all(0 <= row.ordered - row.created for row in eco.audit)


def test_bounds_are_feasible_at_every_sample(eco):
    bounds = economy.stock_bounds(eco)
    assert len(bounds) == len(eco.windows)
    for b in bounds:
        assert sum(b.lo.values()) <= b.total
        assert all(0 <= b.lo[r] <= b.hi[r] <= b.total for r in economy.RES)


def test_bound_arithmetic_on_a_tiny_case():
    spends = [economy.Spend(15_000, "Unit", "Villager", 1, {"Food": 50}, 0)]
    windows = [economy.Window(0, 10_000, 100, 100, 0), economy.Window(10_000, 20_000, 100, 60, 50)]
    tiny = economy.Economy(1, spends, {}, [], windows, 100, None, None, [], [], 0, 0.0)
    first, last = economy.stock_bounds(tiny)
    assert windows[1].income == 10
    assert first.lo["Food"] == 40          # 50 exigidos menos 10 de ingreso posible
    assert first.hi["Wood"] == 60          # 100 de total menos 40 que eran comida seguro
    assert last.lo["Food"] == 0
    verdict = economy.shortage_test([first, last], 0, 20_000, "Food", 50)
    assert verdict["samples"] == 2 and verdict["proved_enough"] == 0 and verdict["proved_short"] == 0


def test_soft_model_is_examined_and_labelled(rec, eco):
    assert eco.checked_purchases > 200
    text = render(rec, 1)
    assert "Examen contra compras aceptadas" in text
    assert "nunca como prueba" in text
    assert "## 5. Economía" in text


# ---- modelo de aldeanos --------------------------------------------------------

from aoe2coach import villagers  # noqa: E402


@pytest.fixture(scope="module")
def eco_full(rec, analysis):
    objects = replay.load_objects(str(FIXTURE))
    creations = [(i.end, i.tc) for i in analysis.calibrated.items if i.kind == "villager"]
    return objects, creations


def test_mule_cart_builders_go_to_the_gold_next_to_it(rec, eco_full):
    objects, creations = eco_full
    alloc = villagers.allocate(rec, 1, objects, creations)
    before, after = alloc.at(8 * 60_000 + 12_000), alloc.at(8 * 60_000 + 14_000)
    assert before.get("Gold", 0) == 0 and after.get("Gold", 0) == 6


def test_own_buildings_are_recognised_by_position(rec, eco_full):
    objects, creations = eco_full
    alloc = villagers.allocate(rec, 1, objects, creations)
    assert alloc.matched_orders >= 30


def test_army_is_not_counted_as_villagers(rec, eco_full):
    objects, _ = eco_full
    world = villagers._World(objects, 1)
    ids = villagers._villager_ids(rec, 1, world)
    patrol = {i for e in rec.events if e.kind == "action" and e.player == 1 and e.action == "PATROL"
              for i in e.payload.get("object_ids", [])}
    assert patrol and not (patrol & ids)
    assert 50 <= len(ids) <= 75                         # 69 creados + 3 iniciales, menos los nunca vistos


def test_rules_improve_agreement_with_purchases(rec, analysis, eco_full):
    objects, creations = eco_full
    relics = analysis.notif.relics
    naive = economy.analyze(rec, 1, objects, creations,
                            villagers.Rules(False, False, False, False), relic_starts=relics)
    best = economy.analyze(rec, 1, objects, creations, relic_starts=relics)
    # Con el recuento de aldeanos corregido el acuerdo empeoro (de 10 a 20 graves):
    # parte del acuerdo anterior venia de errores que se compensaban. Ver docs/03.
    assert len(best.serious_violations()) <= 22
    assert 2 * len(best.serious_violations()) < len(naive.serious_violations())


def test_model_never_has_more_villagers_than_created_before_8_min(rec, analysis, eco_full):
    from bisect import bisect_right
    objects, creations = eco_full
    alloc = villagers.allocate(rec, 1, objects, creations)
    made = sorted(analysis.notif.villagers)
    for t, counts in zip(alloc.times, alloc.counts):
        if t < 8 * 60_000:
            assert sum(counts.values()) <= 3 + bisect_right(made, t)


def test_relic_gold_is_counted_from_pickup(analysis, rec, eco_full):
    objects, creations = eco_full
    e = economy.analyze(rec, 1, objects, creations, relic_starts=analysis.notif.relics)
    assert len(analysis.notif.relics) == 2
    expected = sum(rec.duration_ms - 25_000 - t for t in analysis.notif.relics) / 1000 * 0.5
    assert e.relic_gold == pytest.approx(expected, rel=0.05)


# ---- validacion contra la repeticion ------------------------------------------

from aoe2coach import validation  # noqa: E402


@pytest.fixture(scope="module")
def model(rec):
    return validation.build(rec, 1)


def test_sheet_is_blind_and_uses_recording_samples(model, tmp_path):
    path = tmp_path / "hoja.csv"
    instants = validation.sheet(model, str(path))
    rows = path.read_text(encoding="utf-8").splitlines()
    assert rows[0].startswith("reloj,comida,madera,oro,piedra")
    assert len(rows) == len(instants) + 1 >= 6
    assert all(set(r.split(",")[1:]) == {""} for r in rows[1:])        # sin predicciones
    for t in instants:                                                  # cada instante cae junto a una muestra
        assert min(abs(s - t) for s in model.sync_times) < 1000


def test_correct_reading_passes_and_wrong_sum_fails(model):
    t = validation.parse_clock("16:05")
    p = validation.predict(model, t)
    good = validation.Observation(t, dict(p.estimate))
    assert sum(good.stock.values()) == pytest.approx(p.total, abs=2)
    r = validation.compare(model, [good])
    assert not [c for c in r.hard_failures() if "suma" in c.what]
    bad = validation.Observation(t, {**p.estimate, "Food": p.estimate["Food"] + 500})
    r = validation.compare(model, [bad])
    assert any("suma" in c.what for c in r.hard_failures())


def test_dead_villagers_are_allowed_but_extra_ones_are_not(model):
    t = validation.parse_clock("16:05")
    cap = validation.predict(model, t).villagers_max
    ok = validation.compare(model, [validation.Observation(t, villagers=cap - 2)])
    bad = validation.compare(model, [validation.Observation(t, villagers=cap + 1)])
    assert not ok.hard_failures() and bad.hard_failures()


def test_filled_sheet_is_read_with_partial_rows(model, tmp_path):
    path = tmp_path / "hoja.csv"
    path.write_text("reloj,comida,madera,oro,piedra,ald_comida,ald_madera,ald_oro,ald_piedra,aldeanos,tc_produciendo\n"
                    "16:05,2.400,300,350,100,14,12,7,0,35,1\n"
                    "18:27,,,,,,,,,,\n", encoding="utf-8")
    obs = validation.read_sheet(str(path))
    assert obs[0].stock["Food"] == 2400 and obs[0].workers["Gold"] == 7
    r = validation.compare(model, obs)
    assert r.unfilled == 1
    assert "Validación contra la repetición" in validation.render(model, r)


# ---- cadenas causales ----------------------------------------------------------

from aoe2coach import causal  # noqa: E402


def _ev(weight, direction, partial=False, tag="CALCULADO"):
    return causal.Evidence("x", tag, weight, direction, None, partial)


def test_verdict_rules():
    C = causal.Cause
    assert C("a", "a", [_ev("decisiva", 1)]).verdict == "respaldada"
    assert C("a", "a", [_ev("decisiva", -1)]).verdict == "descartada"
    assert C("a", "a", [_ev("decisiva", 1), _ev("decisiva", -1)]).verdict == "en parte"
    assert C("a", "a", [_ev("decisiva", -1, partial=True), _ev("indicio", 1)]).verdict == "en parte"
    assert C("a", "a", [_ev("decisiva", -1), _ev("indicio", 1)]).verdict == "descartada"
    assert C("a", "a", [_ev("indicio", 1)]).verdict == "compatible"
    assert C("a", "a", []).verdict == "sin datos"
    # una hipótesis sobre la atención nunca se da por probada
    assert C("a", "a", [_ev("decisiva", 1), _ev("indicio", 1)], hypothesis_only=True).verdict == "compatible"


def test_population_room_is_only_certain_below_the_upper_bound():
    pop = causal.Population(starts=[10_000, 20_000], houses=[15_000], tcs=[], limit=200)
    assert pop.upper(5_000) == 4 and pop.cap(5_000) == 5 and pop.room_certain(5_000)
    assert pop.upper(10_000) == 5 and not pop.room_certain(10_000)       # 5 de 5: puede estar lleno
    assert pop.cap(15_000) == 10 and pop.room_certain(25_000)


@pytest.fixture(scope="module")
def chains(model):
    return causal.chains(model)


def test_long_idle_chain_on_the_recording(chains):
    ch = next(c for c in chains if c.kind == "paro" and causal.fmt_clock(c.start) == "14:53")
    assert ch.cause("tc_nuevo").verdict == "respaldada"
    assert ch.cause("comida").verdict == "descartada"
    assert ch.cause("atencion").verdict in ("compatible", "sin datos")
    assert ch.cause("reservar_tc") is not None


def test_decisive_evidence_never_comes_from_the_soft_model(chains):
    for ch in chains:
        for c in ch.causes:
            for e in c.evidence + [x for u in c.upstream for x in u.evidence]:
                if e.weight == "decisiva":
                    assert e.tag in ("OBSERVADO", "CALCULADO"), e.text


def test_report_has_causal_section_without_mind_reading(rec):
    text = render(rec, 1)
    assert "## 7. Cadenas causales" in text and "prueba decisiva" in text
    assert "se distrajo" not in text and "distraído" not in text


# ---- partida multijugador de referencia (Hera, partida 516341955) ---------------
# La grabación se descarga de los servidores oficiales y no se sube al repositorio.
# La hoja con lo leído en el vídeo de Hera sí está en validacion/.

PRO = Path(__file__).resolve().parents[1] / "fixtures" / "pro" / "516341955" / "AgeIIDE_Replay_516341955.aoe2record"
HERA_SHEET = Path(__file__).resolve().parents[1] / "validacion" / "hera-516341955.csv"


@pytest.fixture(scope="module")
def hera():
    if not PRO.exists():
        pytest.skip("falta la grabación de la partida de Hera")
    return validation.build(replay.load(str(PRO), with_sync=True), 2)


def test_multiplayer_recording_is_read_whole(hera):
    r = hera.replay
    assert (r.header.save_major, r.header.save_minor) == (68, 9) and r.header.multiplayer
    assert not any((e.action or "").startswith("UNKNOWN_") for e in r.events)
    assert not hera.tc.notif.present                 # las partidas multijugador no traen avisos


def test_screen_numbers_from_the_video_pass_every_hard_check(hera):
    result = validation.compare(hera, validation.read_sheet(str(HERA_SHEET)))
    hard = [c for c in result.checks if c.kind == "duro"]
    assert len(hard) >= 50 and not result.hard_failures()


def test_without_notifications_nothing_is_decided_about_population(hera):
    assert not hera.eco.model_reliable               # el modelo de reparto suspende su examen aquí
    for ch in causal.chains(hera):
        assert ch.cause("poblacion").verdict == "sin datos"
        assert not any(e.tag == "ESTIMADO" for c in ch.causes for e in c.evidence)
