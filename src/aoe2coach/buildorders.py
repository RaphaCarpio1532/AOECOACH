"""Ordenes de construccion de referencia, con niveles.

Sirven para una sola cosa: decirle al jugador en que nivel queda su tiempo de
edad, en vez de soltarle un numero sin escala.

Fuente: Joh's Build Order Reference (johsaoe2debuildorderreference.site44.com),
builds creados por Cicero, descargados el 2026-11-18. La pagina no dice a que
parche corresponden. Son referencias de 1v1 en mapa abierto tipo Arabia: en
Arena, en agua o en partidas por equipos no valen igual, y el informe lo dice.

El baremo depende del plan: un Fast Castle llega tarde a Feudal A PROPOSITO.
Por eso primero se deduce que build se jugo, con los aldeanos que habia al
subir de edad y con lo que se produjo despues.
"""
from __future__ import annotations

from dataclasses import dataclass

TIERS = ("A+", "A", "B", "C", "D", "E")
SOURCE = ("Joh's Build Order Reference (builds de Cicero), "
          "johsaoe2debuildorderreference.site44.com, leído el 2026-11-18")


def _s(clock: str) -> int:
    m, s = clock.split(":")
    return int(m) * 60 + int(s)


@dataclass(frozen=True)
class BuildOrder:
    key: str
    name: str
    pop_at_feudal: int
    feudal: tuple[int, ...]          # segundos por nivel, de A+ a E
    castle: tuple[int, ...]
    marker_units: tuple[str, ...]    # lo que delata este plan, por nombre de unidad
    note: str

    def tier(self, age: str, seconds: float) -> str | None:
        """Nivel del jugador en esa edad, o None si no hay tabla."""
        table = self.feudal if age == "Feudal" else self.castle if age == "Castle" else None
        if not table:
            return None
        for name, limit in zip(TIERS, table):
            if seconds <= limit:
                return name
        return "por debajo de E"

    def target(self, age: str) -> int | None:
        table = self.feudal if age == "Feudal" else self.castle if age == "Castle" else None
        return table[-1] if table else None


BUILDS = (
    BuildOrder("22-scouts", "22 de población, exploradores", 22,
               tuple(_s(t) for t in ("8:00", "8:10", "8:20", "8:35", "9:00", "9:30")),
               tuple(_s(t) for t in ("16:30", "16:55", "17:20", "17:50", "18:20", "19:00")),
               ("Scout Cavalry", "Explorador a caballo"),
               "Presión temprana con exploradores. Se sube a Feudal pronto y a Castillos tarde."),
    BuildOrder("22-archers", "22 de población, arqueros", 22,
               tuple(_s(t) for t in ("8:00", "8:10", "8:20", "8:35", "9:00", "9:30")),
               tuple(_s(t) for t in ("19:00", "19:30", "20:00", "20:30", "21:10", "22:00")),
               ("Archer", "Arquero", "Crossbowman", "Ballestero"),
               "Dos galerías de tiro en Feudal. Castillos llega tarde a propósito."),
    BuildOrder("28-fc-knights", "28 de población, Fast Castle con caballeros", 28,
               tuple(_s(t) for t in ("10:30", "10:40", "10:55", "11:15", "11:40", "12:15")),
               tuple(_s(t) for t in ("13:35", "13:50", "14:05", "14:25", "14:55", "15:35")),
               ("Knight", "Caballero"),
               "Se salta la presión en Feudal para llegar antes a Castillos."),
    BuildOrder("27-fc-boom", "27 de población, Fast Castle a crecer", 27,
               tuple(_s(t) for t in ("10:05", "10:15", "10:30", "10:50", "11:15", "11:50")),
               tuple(_s(t) for t in ("13:10", "13:25", "13:40", "14:00", "14:30", "15:05")),
               (),
               "Fast Castle para poner más centros urbanos y crecer."),
)


def guess(villagers_at_feudal: int | None, units_ordered: dict[str, int] | None = None) -> BuildOrder:
    """Que plan se parece mas al que se jugo.

    Primero manda el numero de aldeanos al subir a Feudal, porque es lo que
    define el plan. Entre builds del mismo tamano decide lo que se produjo.
    """
    pop = villagers_at_feudal if villagers_at_feudal else 22
    best = min(abs(b.pop_at_feudal - pop) for b in BUILDS)
    candidates = [b for b in BUILDS if abs(b.pop_at_feudal - pop) == best]
    if len(candidates) > 1 and units_ordered:
        scored = [(sum(units_ordered.get(u, 0) for u in b.marker_units), b) for b in candidates]
        scored.sort(key=lambda x: -x[0])
        if scored[0][0] > 0:
            return scored[0][1]
    return candidates[0]
