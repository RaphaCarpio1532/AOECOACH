"""Uso:
  python -m aoe2coach <grabación> [--player N] [--out informe.md]
  python -m aoe2coach <grabación> --hoja hoja.csv            # hoja en blanco para la repetición
  python -m aoe2coach <grabación> --validar hoja.csv [--out validación.md]
"""
from __future__ import annotations

import argparse
import sys

from . import coach, page, replay, validation
from .report import render


def _default_player(rec: replay.Replay) -> int:
    humans = [p.number for p in rec.header.players if not p.is_ai]
    return humans[0] if humans else rec.header.players[0].number


def _emit(text: str, out: str | None, what: str) -> None:
    if out:
        with open(out, "w", encoding="utf-8") as fh:
            fh.write(text)
        print(f"{what} escrito en {out}")
    else:
        sys.stdout.write(text)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="aoe2coach", description="Informe de producción y validación")
    ap.add_argument("recording")
    ap.add_argument("--player", type=int, default=None, help="número de jugador (por defecto, el primer humano)")
    ap.add_argument("--out", default=None, help="archivo Markdown de salida (por defecto, pantalla)")
    ap.add_argument("--html", default=None, help="informe visual en HTML (lo que ve el jugador)")
    ap.add_argument("--hoja", default=None, help="escribe una hoja CSV en blanco para rellenar viendo la repetición")
    ap.add_argument("--validar", default=None, help="compara una hoja CSV rellena con el modelo")
    args = ap.parse_args(argv)
    try:
        rec = replay.load(args.recording, with_sync=True)
    except replay.UnsupportedReplay as exc:
        print(f"Grabación no soportada: {exc}", file=sys.stderr)
        return 2
    player = args.player or _default_player(rec)
    if args.hoja or args.validar:
        model = validation.build(rec, player)
        if args.hoja:
            instants = validation.sheet(model, args.hoja)
            print(f"Hoja escrita en {args.hoja}. Instantes: "
                  + ", ".join(validation.fmt_clock(t) for t in instants))
        if args.validar:
            result = validation.compare(model, validation.read_sheet(args.validar))
            _emit(validation.render(model, result), args.out, "Validación")
            return 1 if result.hard_failures() else 0
        return 0
    text = render(rec, player)
    if args.html:
        report = coach.analyze(rec, player, forensic=text)
        with open(args.html, "w", encoding="utf-8") as fh:
            fh.write(page.render(report))
        print(f"Informe visual escrito en {args.html}")
        if not args.out:
            return 0
    _emit(text, args.out, "Informe")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
