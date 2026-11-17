"""Datos de referencia del juego (nombres, tiempos y costes).

Son DATOS DE REFERENCIA, no hechos de la partida. Describen el parche vigente
cuando se descargo el archivo, que puede no coincidir con el de la grabacion.
Por eso el analisis calibra las duraciones contra cada partida y avisa si la
referencia no encaja.

Fuentes
- Nombres de objetos, tecnologias, civilizaciones y mapas: paquete `aocref`
  (dependencia de `mgz`), dataset 100.
- Tiempos y costes: data/aoe2techtree_data.json, de SiegeEngineers/aoe2techtree
  (MIT), commit e56728e76b del 2026-10-27.
"""
from __future__ import annotations

import json
from functools import lru_cache
from importlib import resources
from pathlib import Path

REFDATA_SOURCE = "SiegeEngineers/aoe2techtree@e56728e76b (2026-10-27)"
_TECHTREE = Path(__file__).resolve().parents[2] / "data" / "aoe2techtree_data.json"

TOWN_CENTER_IDS = {109, 71, 141, 142, 621}   # 621 es el id de colocacion
VILLAGER_IDS = {83, 293}
AGE_TECHS = {101: "Feudal", 102: "Castle", 103: "Imperial"}
# Oro por segundo de cada reliquia guardada en un monasterio. Fuentes: tabla de
# forgottenempires.net (Gold & Relics) y gamerjournalist.com; ninguna dice a que
# parche corresponde. Aztecas +33 %, no modelado.
RELIC_GOLD_PER_S = 0.5
# Tecnologias que se investigan en el centro urbano.
TC_TECH_IDS = {22, 101, 102, 103, 213, 249, 8, 280}


@lru_cache(maxsize=1)
def _names() -> dict:
    path = resources.files("aocref") / "data" / "datasets" / "100.json"
    return json.loads(path.read_text())


@lru_cache(maxsize=1)
def _tree() -> dict:
    return json.loads(_TECHTREE.read_text())["data"]


def object_name(object_id: int) -> str:
    return _names()["objects"].get(str(object_id)) or f"objeto#{object_id}"


def tech_name(tech_id: int) -> str:
    return _names()["technologies"].get(str(tech_id)) or f"tecnologia#{tech_id}"


def civ_name(civ_id: int) -> str:
    return (_names()["civilizations"].get(str(civ_id)) or {}).get("name") or f"civ#{civ_id}"


def map_name(map_id: int) -> str:
    return _names()["maps"].get(str(map_id)) or f"mapa#{map_id}"


def train_time_s(unit_id: int) -> float | None:
    unit = _tree()["Unit"].get(str(unit_id))
    return float(unit["TrainTime"]) if unit else None


@lru_cache(maxsize=None)
def train_time_by_name(name: str) -> float | None:
    """Tiempo de entrenamiento de referencia a partir del nombre que sale en los avisos."""
    for oid, n in _names()["objects"].items():
        if n == name and (t := train_time_s(int(oid))):
            return t
    return None


@lru_cache(maxsize=1)
def _upgrades() -> dict:
    """Mejoras de unidad (p. ej. Husar): en la fuente van aparte, por id de tecnologia."""
    return {str(v["ID"]): v for v in _tree().get("unit_upgrades", {}).values()}


def _tech(tech_id: int) -> dict | None:
    return _tree()["Tech"].get(str(tech_id)) or _upgrades().get(str(tech_id))


def research_time_s(tech_id: int) -> float | None:
    tech = _tech(tech_id)
    return float(tech["ResearchTime"]) if tech else None


def cost(kind: str, object_id: int) -> dict[str, int]:
    """Coste de referencia. kind: 'Unit' | 'Building' | 'Tech'. Vacio si no se conoce."""
    if kind == "Building" and object_id == 621:
        object_id = 109
    entry = _tech(object_id) if kind == "Tech" else _tree().get(kind, {}).get(str(object_id))
    return dict(entry.get("Cost", {})) if entry else {}
