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
# Unidades de respuesta que casi toda civilizacion puede hacer, baratas y de
# contraataque claro: linea de lancero, de escaramuzador, camello y monje. Se
# buscan por el nombre que se muestra, porque el nombre interno de los datos no
# coincide con el del juego (el id 93 se llama PKEMN dentro y Spearman fuera).
# Cada linea va de la unidad base a su ultima mejora. Se cuenta la linea entera,
# porque un piquero y un alabardero son el mismo plan del jugador.
COUNTER_LINES = {
    "lancero": ("Spearman", "Pikeman", "Halberdier"),
    "guerrillero": ("Skirmisher", "Elite Skirmisher", "Imperial Skirmisher"),
    "camello": ("Camel Rider", "Heavy Camel Rider", "Imperial Camel Rider"),
    "monje": ("Monk",),
}
COUNTER_UNIT_NAMES = tuple(n for line in COUNTER_LINES.values() for n in line)

# Tecnologias que se investigan en el centro urbano.
TC_TECH_IDS = {22, 101, 102, 103, 213, 249, 8, 280}


@lru_cache(maxsize=1)
def _names() -> dict:
    path = resources.files("aocref") / "data" / "datasets" / "100.json"
    return json.loads(path.read_text())


@lru_cache(maxsize=1)
def _tree() -> dict:
    return json.loads(_TECHTREE.read_text())["data"]


# El paquete de nombres solo trae ingles. Aqui solo van las traducciones de las
# que no hay duda; lo que no este en la tabla se queda en ingles antes que
# inventarse un nombre que el jugador no reconozca en su pantalla.
ES_NAMES = {
    "Villager": "Aldeano", "Militia": "Milicia", "Man-at-Arms": "Hombre de armas",
    "Long Swordsman": "Espadachín", "Two-Handed Swordsman": "Espadachín a dos manos",
    "Champion": "Campeón", "Spearman": "Lancero", "Pikeman": "Piquero",
    "Halberdier": "Alabardero", "Archer": "Arquero", "Crossbowman": "Ballestero",
    "Arbalester": "Arbalestero", "Cavalry Archer": "Arquero a caballo",
    "Heavy Cavalry Archer": "Arquero a caballo pesado", "Hand Cannoneer": "Arcabucero",
    "Scout Cavalry": "Explorador a caballo", "Light Cavalry": "Caballería ligera",
    "Hussar": "Húsar", "Knight": "Caballero", "Cavalier": "Caballero montado",
    "Paladin": "Paladín", "Camel Rider": "Jinete de camello",
    "Heavy Camel Rider": "Jinete de camello pesado", "Monk": "Monje",
    "Battering Ram": "Ariete", "Capped Ram": "Ariete reforzado", "Siege Ram": "Ariete de asedio",
    "Mangonel": "Mangonel", "Onager": "Onagro", "Siege Onager": "Onagro de asedio",
    "Scorpion": "Escorpión", "Heavy Scorpion": "Escorpión pesado",
    "Bombard Cannon": "Cañón de asedio", "Trebuchet": "Trabuquete",
    "Teutonic Knight": "Caballero teutónico", "Skirmisher": "Guerrillero",
    "Elite Skirmisher": "Guerrillero de élite", "Imperial Skirmisher": "Guerrillero imperial",
    "Steppe Lancer": "Lancero de las estepas",
    "Elite Steppe Lancer": "Lancero de las estepas de élite",
    "Centurion": "Centurión", "Elite Centurion": "Centurión de élite",
    "Legionary": "Legionario", "Mangudai": "Mangudai", "Elite Mangudai": "Mangudai de élite", "Fishing Ship": "Barco pesquero",
    "Transport Ship": "Barco de transporte", "Trade Cart": "Carro de comercio",
    # edificios
    "House": "Casa", "Mill": "Molino", "Lumber Camp": "Campamento maderero",
    "Mining Camp": "Campamento minero", "Farm": "Granja", "Barracks": "Cuartel",
    "Archery Range": "Galería de tiro", "Stable": "Establo", "Blacksmith": "Herrería",
    "Market": "Mercado", "Monastery": "Monasterio", "University": "Universidad",
    "Castle": "Castillo", "Town Center": "Centro urbano", "Watch Tower": "Torre de vigilancia",
    "Guard Tower": "Torre de guardia", "Keep": "Torre del homenaje",
    "Bombard Tower": "Torre de bombardas", "Siege Workshop": "Taller de asedio",
    "Dock": "Puerto", "Outpost": "Puesto de avanzada", "Palisade Wall": "Empalizada",
    "Stone Wall": "Muralla de piedra", "Gate": "Puerta", "Wonder": "Maravilla",
}


def object_name(object_id: int) -> str:
    name = _names()["objects"].get(str(object_id))
    if not name:
        return f"objeto#{object_id}"
    return ES_NAMES.get(name, name)


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


@lru_cache(maxsize=1)
def _ids_by_name() -> dict[str, tuple[int, ...]]:
    out: dict[str, list[int]] = {}
    for oid in _tree()["Unit"]:
        name = _names()["objects"].get(oid)
        if name:
            out.setdefault(name.lower(), []).append(int(oid))
    return {k: tuple(sorted(v)) for k, v in out.items()}


@lru_cache(maxsize=1)
def counter_lines() -> dict[str, tuple[int, ...]]:
    """Por linea: los ids de todas sus unidades, de la base a la ultima mejora."""
    by_name = _ids_by_name()
    return {line: tuple(i for n in names for i in by_name.get(n.lower(), ()))
            for line, names in COUNTER_LINES.items()}


def base_of_line(line: str) -> int | None:
    """La unidad con la que empieza la linea: la que se puede hacer antes."""
    ids = counter_lines().get(line, ())
    return min(ids) if ids else None


def line_of(unit_id: int) -> str | None:
    for line, ids in counter_lines().items():
        if unit_id in ids:
            return line
    return None


@lru_cache(maxsize=1)
def counter_candidates() -> tuple[int, ...]:
    """Ids de las unidades de respuesta genericas, segun los datos del juego."""
    wanted = {n.lower() for n in COUNTER_UNIT_NAMES}
    out = []
    for oid in _tree()["Unit"]:
        name = _names()["objects"].get(oid)
        if name and name.lower() in wanted:
            out.append(int(oid))
    return tuple(sorted(out))
