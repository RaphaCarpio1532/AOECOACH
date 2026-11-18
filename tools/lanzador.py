"""Analiza tu última partida (o la que arrastres encima) y abre el informe en el navegador.

Uso:
  python tools/lanzador.py                 # busca tu grabación más reciente
  python tools/lanzador.py partida.aoe2record

Dónde busca: en Windows, la carpeta de partidas guardadas del juego
(Usuario > Games > Age of Empires 2 DE > <número> > savegame).
Recuerda tu nombre de jugador en `mi_jugador.txt`, junto a este archivo, para no
volver a preguntarlo.
"""
from __future__ import annotations

import os
import sys
import warnings
import webbrowser
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
warnings.simplefilter("ignore")

from aoe2coach import coach, page, refdata, replay  # noqa: E402
from aoe2coach.report import render  # noqa: E402

OUT = ROOT / "informes"
NAME_FILE = Path(__file__).resolve().parent / "mi_jugador.txt"


def candidate_folders() -> list[Path]:
    home = Path.home()
    bases = [home / "Games" / "Age of Empires 2 DE"]
    if os.environ.get("USERPROFILE"):
        bases.append(Path(os.environ["USERPROFILE"]) / "Games" / "Age of Empires 2 DE")
    out = []
    for b in bases:
        if b.is_dir():
            out += [p for p in b.glob("*/savegame") if p.is_dir()]
    return out


def newest_recording() -> Path | None:
    files = [f for d in candidate_folders() for f in d.glob("*.aoe2record")]
    return max(files, key=lambda f: f.stat().st_mtime) if files else None


def choose_player(rec: replay.Replay) -> int:
    humans = [p for p in rec.header.players if not p.is_ai]
    if len(humans) == 1:
        return humans[0].number
    saved = NAME_FILE.read_text(encoding="utf-8").strip() if NAME_FILE.exists() else ""
    for p in humans:
        if saved and p.name == saved:
            print(f"Analizando a {p.name} (tu nombre guardado).")
            return p.number
    print("\nJugadores en esta partida:")
    for p in rec.header.players:
        print(f"  {p.number}. {p.name} — {refdata.civ_name(p.civ_id)}{' (IA)' if p.is_ai else ''}")
    while True:
        answer = input("¿Cuál eres tú? Escribe el número: ").strip()
        if answer.isdigit() and any(p.number == int(answer) for p in rec.header.players):
            me = rec.player(int(answer))
            NAME_FILE.write_text(me.name, encoding="utf-8")
            print(f"Guardado: la próxima vez te reconoceré como {me.name}.")
            return me.number


def main() -> int:
    if len(sys.argv) > 1:
        path = Path(sys.argv[1])
    else:
        path = newest_recording()
        if path is None:
            print("No encuentro grabaciones en la carpeta del juego.")
            print("Arrastra un archivo .aoe2record encima de analizar.bat, o pásalo como argumento.")
            return 1
    print(f"Partida: {path.name} (guardada el {datetime.fromtimestamp(path.stat().st_mtime):%d/%m/%Y %H:%M})")
    try:
        rec = replay.load(str(path), with_sync=True)
    except replay.UnsupportedReplay as exc:
        print(f"No puedo leer esta grabación con garantías: {exc}")
        return 2
    if not rec.verified_version:
        print(f"Aviso: versión de guardado {rec.header.save_version}, no comprobada todavía. Toma el informe con cautela.")
    player = choose_player(rec)
    me = rec.player(player)
    print(f"Analizando a {me.name} con {refdata.civ_name(me.civ_id)}. Puede tardar unos segundos...")
    text = render(rec, player)
    OUT.mkdir(exist_ok=True)
    stem = f"{path.stem}-jugador{player}"
    (OUT / f"{stem}.md").write_text(text, encoding="utf-8")
    report = coach.analyze(rec, player, forensic=text)
    out = OUT / f"{stem}.html"
    out.write_text(page.render(report), encoding="utf-8")
    print(f"Informe guardado en {out}")
    if report.findings:
        top = report.findings[0]
        print(f"Lo que mas te costo: {top.headline} ({top.cost_label}).")
    webbrowser.open(out.as_uri())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
