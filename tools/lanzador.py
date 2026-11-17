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

import html
import json
import os
import sys
import warnings
import webbrowser
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
warnings.simplefilter("ignore")

from aoe2coach import refdata, replay  # noqa: E402
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


def to_html(title: str, markdown: str) -> str:
    # El informe es Markdown. Se muestra con marked (cdnjs); sin internet se ve como texto.
    return f"""<!doctype html><html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>{html.escape(title)}</title>
<style>
body {{ font: 16px/1.6 "Segoe UI", system-ui, sans-serif; max-width: 920px; margin: 32px auto; padding: 0 20px;
  color: #18202b; background: #f6f7f9; }}
h1, h2, h3 {{ line-height: 1.25; }} h2 {{ margin-top: 2em; border-bottom: 1px solid #d8dee7; padding-bottom: 4px; }}
table {{ border-collapse: collapse; width: 100%; font-size: 14px; }} th, td {{ border: 1px solid #d8dee7; padding: 4px 8px; text-align: left; }}
code {{ background: #eceff3; padding: 1px 4px; border-radius: 4px; }} pre {{ white-space: pre-wrap; }}
@media (prefers-color-scheme: dark) {{ body {{ background: #11161d; color: #e6ebf2; }} th, td, h2 {{ border-color: #2b3542; }}
  code {{ background: #222a35; }} }}
</style></head><body>
<div id="out"><pre>{html.escape(markdown)}</pre></div>
<script src="https://cdnjs.cloudflare.com/ajax/libs/marked/4.3.0/marked.min.js"></script>
<script>const md = {json.dumps(markdown)}; if (window.marked) document.getElementById("out").innerHTML = marked.parse(md);</script>
</body></html>"""


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
    page = OUT / f"{stem}.html"
    page.write_text(to_html(f"Informe — {path.stem}", text), encoding="utf-8")
    print(f"Informe guardado en {page}")
    webbrowser.open(page.as_uri())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
