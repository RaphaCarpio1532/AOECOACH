"""Pruebas de la capa de entrenador y de la pagina, sin necesidad de grabacion."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from aoe2coach import causal, coach, page, postgame


def _cause(key, title, *evidence):
    return causal.Cause(key, title, list(evidence))


def _ev(weight, direction, partial=False):
    return causal.Evidence("prueba", "CALCULADO", weight, direction, partial=partial)


def test_verdicts_ordenan_las_causas():
    """La causa demostrada gana a la que solo es compatible, y la hipotesis va ultima."""
    respaldada = _cause("comida", "Falta de comida", _ev("decisiva", 1))
    compatible = _cause("tc_nuevo", "Centro urbano recien hecho", _ev("indicio", 1))
    atencion = causal.Cause("atencion", "Atención", [_ev("indicio", 1)], hypothesis_only=True)
    chain = causal.Chain("paro", 0, 1000, 10, _ev("contexto", 0), [], [atencion, compatible, respaldada], [])
    assert coach._best_cause(chain) is respaldada
    chain.causes = [atencion, compatible]
    assert coach._best_cause(chain) is compatible


def test_la_causa_descartada_nunca_se_elige():
    descartada = _cause("comida", "Falta de comida", _ev("decisiva", -1))
    chain = causal.Chain("paro", 0, 1000, 10, _ev("contexto", 0), [], [descartada], [])
    assert coach._best_cause(chain) is None


def _model(duration_ms=30 * 60000, villager_ms=30000, observed=True):
    return SimpleNamespace(
        replay=SimpleNamespace(duration_ms=duration_ms),
        tc=SimpleNamespace(cal=SimpleNamespace(villager_ms=villager_ms),
                           observed=object() if observed else None))


def _chain(start, end, tc_seconds, kind="paro"):
    return causal.Chain(kind, start, end, tc_seconds, _ev("contexto", 0), [],
                        [_cause("comida", "Falta de comida", _ev("decisiva", 1))], [])


def test_un_paro_corto_no_es_un_hallazgo():
    """Por debajo de un aldeano de coste no se le cuenta nada al jugador."""
    corto = _chain(60000, 80000, 20)          # 20 s·TC entre 30 s = 0,67 aldeanos
    largo = _chain(60000, 180000, 90)         # 3 aldeanos
    assert coach._idle_findings(_model(), [corto]) == []
    assert len(coach._idle_findings(_model(), [largo])) == 1


def test_el_tramo_final_largo_no_cuenta_como_error():
    """Dejar de hacer aldeanos al final de la partida suele ser una decision, no un fallo."""
    fin = 30 * 60000
    chain = _chain(fin - 15 * 60000, fin - 10000, 600)
    assert coach._idle_findings(_model(duration_ms=fin), [chain]) == []


def test_el_coste_se_mide_en_aldeanos():
    f = coach._idle_findings(_model(villager_ms=30000), [_chain(60000, 180000, 120)])[0]
    assert f.impact == pytest.approx(4.0)
    assert "4" in f.cost_label


def test_los_tiempos_de_edad_imposibles_se_descartan():
    assert postgame._age(-1) is None
    assert postgame._age(10 ** 7) is None
    assert postgame._age(680) == 680


def _report(**kw):
    base = dict(name="Jugador", civ="Teutons", map_name="Arabia", duration_ms=600000, player=1,
                result="derrota", opponent="Rival", findings=[], compares=[], marks=[],
                idle_bands=[], villager_series=[], stock_series=[], buildings=[], terrain=[],
                enemy_starts=[], my_start=None, quality=["sin avisos"], measured=False,
                villager_s=30.0, stats=None, forensic="")
    base.update(kw)
    return coach.Report(**base)


def test_la_pagina_se_dibuja_sin_hallazgos():
    html = page.render(_report())
    assert "Perdiste esta partida" in html
    assert "No hay nada gordo que reprocharte" in html


def test_el_nombre_del_jugador_se_escapa():
    """El alias viene de la grabacion: nunca puede inyectar HTML en la pagina."""
    html = page.render(_report(name="<script>alert(1)</script>"))
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html


def test_la_pagina_no_depende_de_internet():
    html = page.render(_report())
    for remoto in ("http://", "https://", "//cdn", "<link"):
        assert remoto not in html
