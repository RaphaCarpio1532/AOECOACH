"""Pagina del informe: lo que ve el jugador.

Un solo archivo HTML, sin internet y sin dependencias: se abre con doble clic.
Arriba, las tres cosas que mas costaron. Debajo, la linea de tiempo, las
graficas, el mapa y la comparativa con el rival. Al final, plegado, el informe
forense completo para quien quiera la letra pequena.

Colores: paleta validada contra los seis controles de daltonismo y contraste en
claro y oscuro (azul = tu, naranja = el rival; los estados llevan icono y
etiqueta, nunca solo color).
"""
from __future__ import annotations

import html
import json

from . import refdata
from .coach import Report, _clock

# ------------------------------------------------------------------ estilos

CSS = """
:root {
  color-scheme: light dark;
  --plane: #f9f9f7; --surface: #fcfcfb; --ink: #0b0b0b; --ink2: #52514e; --muted: #6f6e69;
  --grid: #e1e0d9; --axis: #c3c2b7; --line: rgba(11,11,11,.12);
  --mine: #2a78d6; --theirs: #eb6834;
  --good: #0ca30c; --warning: #fab219; --serious: #ec835a; --critical: #d03b3b;
  --sel: rgba(42,120,214,.20);
  --r: 14px;
  --ease: cubic-bezier(.16,1,.3,1);
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --plane: #0d0d0d; --surface: #1a1a19; --ink: #f0efec; --ink2: #c3c2b7; --muted: #9a988f;
    --grid: #2c2c2a; --axis: #383835; --line: rgba(255,255,255,.12);
    --mine: #3987e5; --theirs: #d95926; --sel: rgba(57,135,229,.30);
  }
}
:root[data-theme="dark"] {
  --plane: #0d0d0d; --surface: #1a1a19; --ink: #f0efec; --ink2: #c3c2b7; --muted: #9a988f;
  --grid: #2c2c2a; --axis: #383835; --line: rgba(255,255,255,.12);
  --mine: #3987e5; --theirs: #d95926; --sel: rgba(57,135,229,.30);
}
* { box-sizing: border-box; }
::selection { background: var(--sel); color: var(--ink); }
html { scrollbar-color: var(--axis) transparent; }
::-webkit-scrollbar { width: 11px; height: 11px; }
::-webkit-scrollbar-thumb { background: var(--axis); border-radius: 99px;
  border: 3px solid var(--plane); }
::-webkit-scrollbar-track { background: transparent; }
:focus-visible { outline: 2px solid var(--mine); outline-offset: 3px; border-radius: 6px; }
body { margin: 0; background: var(--plane); color: var(--ink); caret-color: var(--mine);
  font: 16px/1.55 "Segoe UI", system-ui, -apple-system, sans-serif;
  font-variant-numeric: tabular-nums; -webkit-font-smoothing: antialiased; }
main { max-width: 1000px; margin: 0 auto; padding: 48px 20px 96px; }
.prose { max-width: 68ch; }
a { color: var(--mine); text-underline-offset: 3px; }
h1 { font-size: clamp(28px, 5vw, 44px); margin: 0 0 6px; letter-spacing: -.03em; line-height: 1.08;
  font-weight: 700; }
h2 .hint { color: var(--muted); font-weight: 400; margin-left: 10px; }
h2 { font-size: 13px; margin: 56px 0 18px; letter-spacing: .01em; color: var(--ink2);
  font-weight: 600; text-transform: none; }
h3 { font-size: 20px; margin: 0 0 6px; letter-spacing: -.01em; font-weight: 650; }
p { margin: 0 0 10px; }
.sub { color: var(--ink2); font-size: 15px; }
.i { width: 1em; height: 1em; flex: none; vertical-align: -.13em; }

/* --- cabecera --- */
header.hero { display: flex; flex-wrap: wrap; gap: 20px; align-items: baseline;
  justify-content: space-between; padding-bottom: 28px; border-bottom: 1px solid var(--line); }
header.hero h1 { display: flex; align-items: center; gap: 12px; }
h1 .i { width: .78em; height: .78em; }
.derrota h1 .i { color: var(--critical); } .victoria h1 .i { color: var(--good); }
.desconocido h1 .i { color: var(--muted); }
button.theme { background: none; color: var(--ink2); border: 1px solid var(--line);
  border-radius: 99px; padding: 7px 14px; font: inherit; font-size: 13px; cursor: pointer;
  transition: color .15s var(--ease), border-color .15s var(--ease); }
button.theme:hover { color: var(--ink); border-color: var(--axis); }

/* --- hallazgos --- */
.findings { display: flex; flex-direction: column; }
.finding { display: grid; grid-template-columns: 136px minmax(0, 1fr); gap: 28px; width: 100%;
  text-align: left; align-items: start; background: none; border: 0;
  border-top: 1px solid var(--line); padding: 26px 0; font: inherit; color: inherit;
  cursor: pointer; transition: opacity .2s var(--ease); }
.finding:last-of-type { border-bottom: 1px solid var(--line); }
.findings:hover .finding:not(:hover) { opacity: .62; }
.finding .cost { font-size: clamp(26px, 4vw, 34px); font-weight: 700; letter-spacing: -.035em;
  line-height: 1; }
.finding .when { color: var(--muted); font-size: 13px; margin-top: 8px; }
.finding.on .cost { color: var(--mine); }
.chips { display: flex; flex-wrap: wrap; gap: 14px; margin: 10px 0 0; font-size: 13px;
  color: var(--muted); }
.chips span { display: inline-flex; align-items: center; gap: 5px; }
.chip-demostrado { color: var(--good); } .chip-hipotesis { color: var(--warning); }
.chip-estimado { color: var(--serious); }
.after { padding: 0 0 26px 164px; margin-top: -8px; }
@media (max-width: 560px) { .after { padding-left: 0; } }
.fix { margin-top: 0; padding: 12px 14px; background: var(--surface);
  border: 1px solid var(--line); border-radius: 10px; font-size: 14px; max-width: 68ch; }
.fix strong { color: var(--ink); }
ul.why { margin: 10px 0 0; padding-left: 17px; color: var(--ink2); font-size: 14.5px;
  max-width: 68ch; }
ul.why li { margin-bottom: 5px; }
details { margin-top: 12px; }
details > summary { cursor: pointer; color: var(--mine); font-size: 13.5px; list-style: none;
  display: inline-flex; align-items: center; gap: 6px; }
details > summary::-webkit-details-marker { display: none; }
details > summary::before { content: ""; width: 5px; height: 5px; border-right: 1.5px solid currentColor;
  border-bottom: 1.5px solid currentColor; transform: rotate(-45deg); transition: transform .2s var(--ease); }
details[open] > summary::before { transform: rotate(45deg); }
details pre { white-space: pre-wrap; font-size: 12.5px; line-height: 1.55; color: var(--ink2);
  background: var(--surface); border: 1px solid var(--line); border-radius: 10px; padding: 14px;
  overflow-x: auto; max-height: 460px; }

/* --- la historia --- */
.story { list-style: none; margin: 0; padding: 0; max-width: 72ch; }
.beat { display: grid; grid-template-columns: 62px 1fr; gap: 16px; padding: 12px 0;
  border-top: 1px solid var(--line); font-size: 15px; align-items: baseline; }
.beat:first-child { border-top: 0; }
.beat-t { color: var(--muted); font-size: 13px; }
.beat.giro > span:last-child { color: var(--ink); font-weight: 600; }
.beat.final > span:last-child { color: var(--critical); font-weight: 600; }

/* --- ejercitos --- */
.army { display: flex; flex-direction: column; gap: 14px; }
.arow { display: grid; grid-template-columns: 220px minmax(0, 1fr); gap: 20px; align-items: center; }
.aname { font-size: 14px; }
.aname .note { display: block; color: var(--muted); font-size: 12.5px; }
.abars { display: flex; flex-direction: column; gap: 5px; }
.abar { display: flex; align-items: center; gap: 9px; height: 15px; }
.abar i { display: block; height: 15px; border-radius: 0 4px 4px 0; min-width: 2px; }
.abar b { font-weight: 600; font-size: 12.5px; color: var(--ink2); }
@media (max-width: 560px) { .arow { grid-template-columns: 1fr; gap: 6px; } }

/* --- niveles --- */
.grades { display: flex; flex-direction: column; gap: 22px; }
.grade-row h4 { margin: 0 0 10px; font-size: 15px; font-weight: 600; display: flex;
  align-items: baseline; gap: 12px; flex-wrap: wrap; }
.grade-row .you { color: var(--mine); font-weight: 600; font-size: 14px; }
.tiers { display: grid; grid-template-columns: repeat(6, minmax(0, 1fr)); gap: 6px; }
.tier { border: 1px solid var(--line); border-radius: 9px; padding: 9px 6px; text-align: center; }
.tier .tn { display: block; font-size: 12px; color: var(--muted); }
.tier .tv { display: block; font-size: 15px; font-weight: 600; margin-top: 3px; }
.tier.on { border-color: var(--mine); background: color-mix(in srgb, var(--mine) 12%, transparent); }
.tier.on .tn, .tier.on .tv { color: var(--mine); }

/* --- figuras --- */
figure { margin: 0; }
figure + figure { margin-top: 32px; }
figcaption { font-size: 13.5px; color: var(--ink2); margin-top: 12px; max-width: 68ch; }
svg.plot { display: block; width: 100%; height: auto; overflow: visible; }
text { fill: var(--muted); font-size: 11px; font-family: inherit; }
text.lbl { fill: var(--ink2); font-size: 12px; }
.band { cursor: pointer; transition: opacity .15s var(--ease); }
.band:hover { opacity: .8; }
.band.on { stroke: var(--ink); stroke-width: 1.5; }
.legend { display: flex; flex-wrap: wrap; gap: 8px 18px; margin-top: 14px; font-size: 13px;
  color: var(--ink2); }
.legend span { display: inline-flex; align-items: center; gap: 7px; }
.sw { width: 11px; height: 11px; border-radius: 3px; display: inline-block; }
.grid2 { display: grid; gap: 40px; grid-template-columns: 1fr; }
@media (min-width: 820px) { .grid2 { grid-template-columns: 1fr 1fr; gap: 32px; } }
table { border-collapse: collapse; width: 100%; font-size: 14px; }
th, td { text-align: left; padding: 9px 12px 9px 0; border-bottom: 1px solid var(--line); }
th { color: var(--muted); font-weight: 600; font-size: 12.5px; }
td.win { color: var(--good); } td.lose { color: var(--ink2); }
td .i { color: var(--good); margin-left: 5px; }
dialog#zoom { width: min(96vw, 1500px); max-width: none; border: 1px solid var(--line);
  border-radius: var(--r); background: var(--surface); color: var(--ink); padding: 20px;
  box-shadow: 0 24px 60px rgba(0,0,0,.3); }
dialog#zoom::backdrop { background: rgba(0,0,0,.55); }
.zoom-head { display: flex; justify-content: space-between; align-items: center; gap: 16px;
  margin-bottom: 14px; }
.zoom-title { font-weight: 650; font-size: 18px; }
.zoom-close { background: none; border: 1px solid var(--line); border-radius: 99px;
  padding: 6px 14px; font: inherit; font-size: 13px; color: var(--ink2); cursor: pointer; }
.zoom-body svg { width: 100%; height: auto; }
figure svg.plot:hover { outline: 1px solid var(--line); outline-offset: 10px; border-radius: 4px; }

#tip { position: fixed; pointer-events: none; opacity: 0; transition: opacity .12s var(--ease);
  background: var(--ink); color: var(--plane); padding: 8px 11px; border-radius: 9px;
  font-size: 13px; line-height: 1.4; max-width: 280px; z-index: 50;
  box-shadow: 0 6px 20px rgba(0,0,0,.22); }
.notes { font-size: 14px; color: var(--ink2); max-width: 68ch; margin: 0; padding-left: 17px; }
.notes li { margin-bottom: 8px; }
.empty { border: 1px solid var(--line); border-radius: var(--r); padding: 22px; max-width: 68ch; }

/* --- un unico momento de movimiento: la partida se dibuja al abrir --- */
@media (prefers-reduced-motion: no-preference) {
  .draw { transform-box: fill-box; transform-origin: left center;
    animation: grow .85s var(--ease) both; }
  @keyframes grow { from { transform: scaleX(.02); } to { transform: scaleX(1); } }
}
@media (max-width: 560px) {
  .finding { grid-template-columns: 1fr; gap: 10px; }
  main { padding: 32px 16px 72px; }
}
"""

ICONS = """
<svg width="0" height="0" style="position:absolute" aria-hidden="true"><defs>
<symbol id="i-cross" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6"
  stroke-linecap="round"><path d="M4 4l8 8M12 4l-8 8"/></symbol>
<symbol id="i-check" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6"
  stroke-linecap="round" stroke-linejoin="round"><path d="M3.2 8.6l3.2 3.2L12.8 5"/></symbol>
<symbol id="i-dash" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6"
  stroke-linecap="round"><path d="M3.5 8h9"/></symbol>
<symbol id="i-pause" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6"
  stroke-linecap="round"><path d="M6 3.5v9M10 3.5v9"/></symbol>
<symbol id="i-block" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5"
  stroke-linecap="round"><circle cx="8" cy="8" r="5.5"/><path d="M4.1 11.9l7.8-7.8"/></symbol>
<symbol id="i-age" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5"
  stroke-linecap="round" stroke-linejoin="round"><path d="M8 2.6l5 4.2V13H3V6.8z"/></symbol>
<symbol id="i-tc" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5"
  stroke-linejoin="round"><rect x="3" y="5" width="10" height="8" rx="1"/><path d="M8 5V2.5"/></symbol>
<symbol id="i-attack" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5"
  stroke-linecap="round"><path d="M3.5 12.5l9-9M12.5 12.5l-9-9"/></symbol>
<symbol id="i-flag" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5"
  stroke-linecap="round" stroke-linejoin="round"><path d="M4 14V2.8"/><path d="M4 3.4h7.6l-1.6 2.6
  1.6 2.6H4"/></symbol>
<symbol id="i-work" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5"
  stroke-linecap="round"><path d="M2.5 8h11"/></symbol>
</defs></svg>
"""

JS = """
const tip = document.getElementById('tip');
function showTip(e, text) {
  tip.innerHTML = text; tip.style.opacity = 1;
  const pad = 14, w = tip.offsetWidth, h = tip.offsetHeight;
  let x = e.clientX + pad, y = e.clientY + pad;
  if (x + w > innerWidth - 8) x = e.clientX - w - pad;
  if (y + h > innerHeight - 8) y = e.clientY - h - pad;
  tip.style.left = x + 'px'; tip.style.top = y + 'px';
}
function hideTip() { tip.style.opacity = 0; }
document.querySelectorAll('[data-tip]').forEach(el => {
  el.addEventListener('mousemove', e => showTip(e, el.dataset.tip));
  el.addEventListener('mouseleave', hideTip);
  el.addEventListener('click', () => { if (el.dataset.key) select(el.dataset.key); });
});
function select(key) {
  document.querySelectorAll('.finding, .band').forEach(el => {
    el.classList.toggle('on', el.dataset.key === key);
  });
}
document.querySelectorAll('.finding').forEach(el => {
  el.addEventListener('click', () => select(el.dataset.key));
});
const zoom = document.getElementById('zoom');
document.querySelectorAll('figure svg.plot').forEach(svg => {
  svg.style.cursor = 'zoom-in';
  svg.setAttribute('tabindex', '0');
  const open = () => {
    zoom.querySelector('.zoom-body').innerHTML = '';
    const copy = svg.cloneNode(true);
    copy.style.cursor = 'auto';
    copy.removeAttribute('tabindex');
    zoom.querySelector('.zoom-body').appendChild(copy);
    const h = svg.closest('figure').querySelector('h3');
    zoom.querySelector('.zoom-title').textContent = h ? h.textContent : '';
    zoom.showModal();
  };
  svg.addEventListener('click', open);
  svg.addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); open(); } });
});
zoom.addEventListener('click', e => { if (e.target === zoom) zoom.close(); });
zoom.querySelector('.zoom-close').addEventListener('click', () => zoom.close());

const root = document.documentElement, btn = document.getElementById('theme');
if (btn) btn.addEventListener('click', () => {
  const dark = getComputedStyle(root).getPropertyValue('--plane').trim() === '#0d0d0d';
  root.setAttribute('data-theme', dark ? 'light' : 'dark');
});
"""


def _e(s) -> str:
    return html.escape(str(s))


# ------------------------------------------------------------------ piezas

RES_SHAPE = {"Food": ("circle", "comida"), "Wood": ("square", "madera"),
             "Gold": ("triangle", "oro"), "Stone": ("diamond", "piedra")}


def _clock_s_page(seconds: float) -> str:
    s = int(seconds)
    return f"{s // 60}:{s % 60:02d}"


def _icon(name: str, cls: str = "i") -> str:
    return f'<svg class="{cls}" aria-hidden="true"><use href="#i-{name}"/></svg>'


CONF_ICON = {"demostrado": "check", "demostrado en parte": "check", "hipotesis": "block",
             "estimado": "dash", "medido": "check", "calculado": "dash"}


def _findings_html(r: Report) -> str:
    if not r.findings:
        return ('<div class="empty"><h3>No hay nada gordo que reprocharte</h3><p class="sub">'
                'Ningún paro ni retraso llega a costar un aldeano. Mira la línea de tiempo y la '
                'comparativa para los detalles finos.</p></div>')
    out = []
    for f in r.findings[:3]:
        why = "".join(f"<li>{_e(w)}</li>" for w in f.why)
        detail = "\n".join(f.detail)
        conf = f.confidence
        cls = conf.split()[0]
        out.append(f"""
<button class="finding" data-key="{_e(f.key)}" type="button">
  <span>
    <span class="cost">{_e(f.cost_label)}</span>
    <span class="when">{_e(f.when_label)}</span>
  </span>
  <span>
    <h3>{_e(f.headline)}</h3>
    <p class="sub">{_e(f.cause)}</p>
    <span class="chips"><span class="chip-{_e(cls)}">{_icon(CONF_ICON.get(conf, "dash"))}{_e(conf)}</span>
      <span>{f.impact:.1f} aldeanos de coste</span></span>
    <ul class="why">{why}</ul>
  </span>
</button>""")
        tail = []
        if f.fix:
            tail.append(f'<div class="fix"><strong>La próxima vez.</strong> {_e(f.fix)}</div>')
        if detail:
            tail.append(f'<details><summary>Ver la prueba completa</summary>'
                        f'<pre>{_e(detail)}</pre></details>')
        if tail:
            out.append('<div class="after">' + "".join(tail) + "</div>")
    rest = r.findings[3:]
    if rest:
        rows = "".join(
            f"<tr><td>{_e(f.headline)}</td><td>{_e(f.when_label)}</td>"
            f"<td>{_e(f.cost_label)}</td></tr>" for f in rest)
        out.append(f"""
<details><summary>Y {len(rest)} cosa{'s' if len(rest) > 1 else ''} más, de menos coste</summary>
<table><thead><tr><th>Qué pasó</th><th>Cuándo</th><th>Coste</th></tr></thead><tbody>{rows}</tbody>
</table></details>""")
    return '<div class="findings">' + "".join(out) + "</div>"


MARK_STYLE = {"edad": ("var(--mine)", "age"), "tc": ("var(--good)", "tc"),
              "ataque": ("var(--critical)", "attack"), "rendicion": ("var(--ink2)", "flag")}


def _timeline(r: Report) -> str:
    W, H = 1000, 150
    x0, x1 = 44, W - 12
    dur = max(r.duration_ms, 1)
    top, bot = 54, 96

    def X(t):
        return x0 + (x1 - x0) * min(max(t / dur, 0), 1)

    keys = {f.key for f in r.findings[:3]}
    parts = [f'<g class="draw">', f'<rect x="{x0}" y="{top}" width="{x1 - x0}" height="{bot - top}" rx="6" '
             f'fill="var(--mine)" opacity=".28" '
             f'data-tip="El centro urbano estaba produciendo" />']
    for t0, t1, tc_s, kind in r.idle_bands:
        w = max(X(t1) - X(t0), 1.5)
        color = "var(--critical)" if kind == "bloqueo" else "var(--serious)"
        key = f"{kind}-{int(t0)}"
        label = "cola pagada sin salir" if kind == "bloqueo" else "centro urbano parado"
        strong = " on" if key in keys else ""
        parts.append(
            f'<rect class="band{strong}" data-key="{key}" x="{X(t0):.1f}" y="{top}" width="{w:.1f}" '
            f'height="{bot - top}" fill="{color}" rx="2" '
            f'data-tip="<b>{label}</b><br>{_clock(t0)} → {_clock(t1)}<br>'
            f'{tc_s:.0f} s·TC ≈ {tc_s / r.villager_s:.1f} aldeanos" />')
    parts.append("</g>")
    # marcas
    for t, kind, text in r.marks:
        color, glyph = MARK_STYLE.get(kind, ("var(--ink2)", "•"))
        x = X(t)
        parts.append(f'<line x1="{x:.1f}" y1="{top - 8}" x2="{x:.1f}" y2="{bot + 8}" '
                     f'stroke="{color}" stroke-width="1" stroke-dasharray="2 2" opacity=".65" />')
        parts.append(f'<use href="#i-{glyph}" x="{x - 7:.1f}" y="{top - 26}" width="14" height="14" '
                     f'color="{color}" data-tip="<b>{_e(text)}</b><br>{_clock(t)}" />')
    # eje de minutos
    step = 5 * 60000 if dur <= 50 * 60000 else 10 * 60000
    t = 0
    while t <= dur:
        x = X(t)
        parts.append(f'<line class="axis" x1="{x:.1f}" y1="{bot}" x2="{x:.1f}" y2="{bot + 4}" />')
        parts.append(f'<text x="{x:.1f}" y="{bot + 18}" text-anchor="middle">{_clock(t)}</text>')
        t += step
    legend = (
        '<div class="legend">'
        '<span><i class="sw" style="background:var(--mine);opacity:.4"></i>produciendo</span>'
        '<span><i class="sw" style="background:var(--serious)"></i>parado</span>'
        '<span><i class="sw" style="background:var(--critical)"></i>cola pagada que no salía</span>'
        '<span style="color:var(--mine)">' + _icon("age") + '<span style="color:var(--ink2)">edad nueva</span></span>'
        '<span style="color:var(--good)">' + _icon("tc") + '<span style="color:var(--ink2)">centro urbano nuevo</span></span>'
        '<span style="color:var(--critical)">' + _icon("attack") + '<span style="color:var(--ink2)">te atacan</span></span>'
        '</div>')
    rows = "".join(
        f"<tr><td class='num'>{_clock(a)} → {_clock(b)}</td><td>"
        f"{'cola pagada sin salir' if k == 'bloqueo' else 'parado'}</td>"
        f"<td class='num'>{s:.0f} s·TC</td><td class='num'>{s / r.villager_s:.1f}</td></tr>"
        for a, b, s, k in r.idle_bands)
    table = (f"<details><summary>Ver los números</summary><table><thead><tr><th>Tramo</th><th>Tipo</th>"
             f"<th>Coste</th><th>Aldeanos</th></tr></thead><tbody>{rows}</tbody></table></details>"
             if rows else "")
    return (f'<figure><svg class="plot" viewBox="0 0 {W} {H}" role="img" aria-label="Línea de tiempo de la partida">'
            + "".join(parts) + f'</svg>{legend}<figcaption>Cada bloque es un tramo en que el centro urbano '
            f'no producía. La altura no significa nada; el ancho es el tiempo real. '
            f'{"Medido con los avisos de la grabación." if r.measured else "Estimado con las órdenes: es una cota inferior."}'
            f' Toca un bloque para resaltarlo arriba.</figcaption>{table}</figure>')


def _line_chart(title: str, note: str, series: list[tuple[float, float]], unit: str,
                dur: float, bands: list, color: str = "var(--mine)") -> str:
    if len(series) < 2:
        return (f'<figure><h3>{_e(title)}</h3><p class="sub">Sin datos suficientes en esta grabación.</p>'
                f'</figure>')
    W, H = 1000, 300
    x0, x1, y0, y1 = 56, W - 14, 24, H - 34
    vmax = max(v for _, v in series) or 1

    def X(t):
        return x0 + (x1 - x0) * min(max(t / max(dur, 1), 0), 1)

    def Y(v):
        return y1 - (y1 - y0) * (v / vmax)

    parts = []
    for i in range(5):
        v = vmax * i / 4
        y = Y(v)
        parts.append(f'<line class="grid" x1="{x0}" y1="{y:.1f}" x2="{x1}" y2="{y:.1f}" '
                     f'stroke="var(--grid)" />')
        parts.append(f'<text x="{x0 - 8}" y="{y + 4:.1f}" text-anchor="end">{v:.0f}</text>')
    for t0, t1, tc_s, kind in bands:
        parts.append(f'<rect x="{X(t0):.1f}" y="{y0}" width="{max(X(t1) - X(t0), 1.2):.1f}" '
                     f'height="{y1 - y0}" fill="var(--serious)" opacity=".11" />')
    pts = " ".join(f"{X(t):.1f},{Y(v):.1f}" for t, v in series)
    parts.append(f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="2" '
                 f'stroke-linejoin="round" stroke-linecap="round" />')
    last_t, last_v = series[-1]
    parts.append(f'<circle cx="{X(last_t):.1f}" cy="{Y(last_v):.1f}" r="4.5" fill="{color}" '
                 f'stroke="var(--surface)" stroke-width="2" />')
    parts.append(f'<text class="lbl" x="{X(last_t) - 6:.1f}" y="{Y(last_v) - 12:.1f}" '
                 f'text-anchor="end" fill="var(--ink2)">{last_v:.0f} {_e(unit)}</text>')
    step = 5 * 60000 if dur <= 50 * 60000 else 10 * 60000
    t = 0
    while t <= dur:
        parts.append(f'<text x="{X(t):.1f}" y="{y1 + 20:.1f}" text-anchor="middle">{_clock(t)}</text>')
        t += step
    parts.append(f'<line class="axis" x1="{x0}" y1="{y1}" x2="{x1}" y2="{y1}" stroke="var(--axis)" />')
    # capa de puntos invisibles para el tooltip
    for t, v in series[:: max(1, len(series) // 120)]:
        parts.append(f'<circle cx="{X(t):.1f}" cy="{Y(v):.1f}" r="9" fill="transparent" '
                     f'data-tip="{_clock(t)}<br><b>{v:.0f}</b> {_e(unit)}" />')
    rows = "".join(f"<tr><td class='num'>{_clock(t)}</td><td class='num'>{v:.0f}</td></tr>"
                   for t, v in series[:: max(1, len(series) // 40)])
    return (f'<figure><h3>{_e(title)}</h3>'
            f'<svg class="plot" viewBox="0 0 {W} {H}" role="img" aria-label="{_e(title)}">' + "".join(parts) +
            f'</svg><figcaption>{_e(note)} Las franjas verticales son los tramos sin producir.</figcaption>'
            f'<details><summary>Ver los números</summary><table><thead><tr><th>Minuto</th>'
            f'<th>{_e(unit).capitalize()}</th></tr></thead><tbody>{rows}</tbody></table></details></figure>')


def _minimap(r: Report) -> str:
    pts = [(x, y) for x, y, _ in r.terrain] + [(x, y) for _, _, x, y in r.buildings if x >= 0] + \
          [(x, y) for x, y, _ in r.enemy_starts]
    if r.my_start:
        pts.append(r.my_start)
    if len(pts) < 4:
        return ""
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    lo, hi = min(min(xs), min(ys)), max(max(xs), max(ys))
    span = max(hi - lo, 1)
    S = 440

    def P(x, y):
        return (14 + (S - 28) * (x - lo) / span, 14 + (S - 28) * (y - lo) / span)

    parts = [f'<rect x="0" y="0" width="{S}" height="{S}" rx="10" fill="var(--plane)" '
             f'stroke="var(--line)" />']
    for x, y, res in r.terrain:
        cx, cy = P(x, y)
        shape, name = RES_SHAPE.get(res, ("circle", res))
        if shape == "square":          # madera: hay cientos de arboles, van mas tenues
            parts.append(f'<rect x="{cx - 1.3:.1f}" y="{cy - 1.3:.1f}" width="2.6" height="2.6" '
                         f'fill="var(--muted)" opacity=".28" />')
        elif shape == "triangle":
            parts.append(f'<path d="M{cx:.1f},{cy - 2.6:.1f} L{cx + 2.4:.1f},{cy + 2:.1f} '
                         f'L{cx - 2.4:.1f},{cy + 2:.1f} Z" fill="var(--muted)" opacity=".55" />')
        elif shape == "diamond":
            parts.append(f'<path d="M{cx:.1f},{cy - 2.8:.1f} L{cx + 2.8:.1f},{cy:.1f} '
                         f'L{cx:.1f},{cy + 2.8:.1f} L{cx - 2.8:.1f},{cy:.1f} Z" '
                         f'fill="var(--muted)" opacity=".55" />')
        else:
            parts.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="2" fill="var(--muted)" opacity=".5" />')
    for t, kind, x, y in r.buildings:
        if x < 0:
            continue
        cx, cy = P(x, y)
        name = refdata.object_name(kind)
        parts.append(f'<rect x="{cx - 3:.1f}" y="{cy - 3:.1f}" width="6" height="6" rx="1.5" '
                     f'fill="var(--mine)" opacity=".9" data-tip="{_e(name)}<br>orden en {_clock(t)}" />')
    for x, y, _c in r.enemy_starts:
        cx, cy = P(x, y)
        parts.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="7" fill="none" stroke="var(--theirs)" '
                     f'stroke-width="2.5" data-tip="Centro urbano del rival" />')
        parts.append(f'<text x="{cx:.1f}" y="{cy + 20:.1f}" text-anchor="middle" '
                     f'fill="var(--theirs)" font-size="11">rival</text>')
    if r.my_start:
        cx, cy = P(*r.my_start)
        parts.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="7" fill="none" stroke="var(--mine)" '
                     f'stroke-width="2.5" data-tip="Tu centro urbano de inicio" />')
        parts.append(f'<text x="{cx:.1f}" y="{cy + 20:.1f}" text-anchor="middle" fill="var(--mine)" '
                     f'font-size="11">tú</text>')
    legend = ('<div class="legend">'
              '<span><i class="sw" style="background:var(--mine)"></i>tus edificios</span>'
              '<span><i class="sw" style="background:var(--theirs);border-radius:50%"></i>inicio del rival</span>'
              '<span><svg class="i" viewBox="0 0 10 10"><circle cx="5" cy="5" r="2.6" fill="currentColor"/></svg>comida</span>'
              '<span><svg class="i" viewBox="0 0 10 10"><rect x="2.6" y="2.6" width="4.8" height="4.8" fill="currentColor"/></svg>madera</span>'
              '<span><svg class="i" viewBox="0 0 10 10"><path d="M5 2.2l3 5.4H2z" fill="currentColor"/></svg>oro</span>'
              '<span><svg class="i" viewBox="0 0 10 10"><path d="M5 2l3 3-3 3-3-3z" fill="currentColor"/></svg>piedra</span>'
              '</div>')
    return (f'<figure><h3>Dónde construiste</h3>'
            f'<svg class="plot" viewBox="0 0 {S} {S}" role="img" aria-label="Mapa de la partida">' + "".join(parts) +
            f'</svg>{legend}<figcaption>Posición de cada orden de construcción tuya y de los recursos '
            f'del mapa al empezar. Pasa el ratón por un edificio para ver cuál es y cuándo lo pusiste.'
            f'</figcaption></figure>')



BEAT_ICON = {"hecho": "work", "giro": "attack", "final": "flag"}


def _story(r: Report) -> str:
    if not r.beats:
        return ""
    items = []
    for b in r.beats:
        when = f'<span class="beat-t">{_clock(b.t)}</span>' if b.t is not None else '<span class="beat-t"></span>'
        items.append(f'<li class="beat {_e(b.kind)}">{when}<span>{_e(b.text)}</span></li>')
    return f'<ol class="story">{"".join(items)}</ol>'


def _army_chart(r: Report) -> str:
    if not r.army:
        return ""
    rival = _e(r.opponent or "el rival")
    top = max(max(a.mine, a.theirs) for a in r.army) or 1
    rows = []
    for a in r.army:
        wm, wt = 100 * a.mine / top, 100 * a.theirs / top
        note = f'<span class="note">{_e(a.counter_note)}</span>' if a.counter_note else ""
        rows.append(f"""
<div class="arow">
  <div class="aname">{_e(a.unit)}{note}</div>
  <div class="abars">
    <div class="abar"><i style="width:{wm:.1f}%;background:var(--mine)"
      data-tip="Tú: {a.mine}"></i><b>{a.mine}</b></div>
    <div class="abar"><i style="width:{wt:.1f}%;background:var(--theirs)"
      data-tip="{rival}: {a.theirs}"></i><b>{a.theirs}</b></div>
  </div>
</div>""")
    legend = (f'<div class="legend"><span><i class="sw" style="background:var(--mine)"></i>'
              f'{_e(r.name)}</span><span><i class="sw" style="background:var(--theirs)"></i>'
              f'{rival}</span></div>')
    return (f'<figure><h3>Qué pidió cada uno</h3><div class="army">{"".join(rows)}</div>{legend}'
            f'<figcaption>Unidades militares que cada jugador mandó producir. Son órdenes, no '
            f'unidades vivas: lo que murió por el camino no se descuenta. Las órdenes de los dos '
            f'jugadores están en la grabación.</figcaption></figure>')


def _strength_chart(r: Report) -> str:
    if len(r.my_strength) < 3 or len(r.their_strength) < 3:
        return ""
    W, H = 1000, 320
    x0, x1, y0, y1 = 56, W - 14, 24, H - 34
    dur = max(r.duration_ms, 1)
    vmax = max([v for _, v in r.my_strength] + [v for _, v in r.their_strength]) or 1

    def X(t):
        return x0 + (x1 - x0) * min(max(t / dur, 0), 1)

    def Y(v):
        return y1 - (y1 - y0) * (v / vmax)

    parts = []
    for i in range(5):
        v = vmax * i / 4
        parts.append(f'<line x1="{x0}" y1="{Y(v):.1f}" x2="{x1}" y2="{Y(v):.1f}" stroke="var(--grid)" />')
        parts.append(f'<text x="{x0 - 8}" y="{Y(v) + 4:.1f}" text-anchor="end">{v:.0f}</text>')
    for series, color, who in ((r.their_strength, "var(--theirs)", r.opponent or "rival"),
                               (r.my_strength, "var(--mine)", r.name)):
        pts = " ".join(f"{X(t):.1f},{Y(v):.1f}" for t, v in series)
        parts.append(f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="2" '
                     f'stroke-linejoin="round" />')
        t, v = series[-1]
        parts.append(f'<text class="lbl" x="{X(t) + 8:.1f}" y="{Y(v) + 4:.1f}" fill="{color}">'
                     f'{_e(who)}</text>')
        for t, v in series[:: max(1, len(series) // 90)]:
            parts.append(f'<circle cx="{X(t):.1f}" cy="{Y(v):.1f}" r="8" fill="transparent" '
                         f'data-tip="{_clock(t)}<br><b>{_e(who)}</b>: {v} objetos" />')
    for t, label, color in ((r.push_t, "empieza la última tanda de ataques", "var(--critical)"),
                            (r.resign_t, "rendición", "var(--ink2)")):
        if t is None:
            continue
        parts.append(f'<line x1="{X(t):.1f}" y1="{y0}" x2="{X(t):.1f}" y2="{y1}" stroke="{color}" '
                     f'stroke-width="1" stroke-dasharray="3 3" data-tip="{_e(label)}<br>{_clock(t)}" />')
    step = 5 * 60000 if dur <= 50 * 60000 else 10 * 60000
    t = 0
    while t <= dur:
        parts.append(f'<text x="{X(t):.1f}" y="{y1 + 20:.1f}" text-anchor="middle">{_clock(t)}</text>')
        t += step
    parts.append(f'<line x1="{x0}" y1="{y1}" x2="{x1}" y2="{y1}" stroke="var(--axis)" />')
    return (f'<figure><h3>Cuánto tenía cada uno en el mapa</h3>'
            f'<svg class="plot" viewBox="0 0 {W} {H}" role="img" aria-label="Objetos de cada jugador">'
            + "".join(parts) + '</svg>'
            f'<figcaption>[ESTIMADO] Objetos de cada jugador según las sincronizaciones de la '
            f'grabación: incluye unidades, edificios y cimientos, así que no es «ejército». El '
            f'significado de ese contador está documentado por el lector <code>mgz</code> como una '
            f'conjetura, no por el juego. Sirve para ver quién crecía y cuándo se hundió.'
            f'</figcaption></figure>')


def _grade_table(r: Report) -> str:
    g = r.grade
    if not g or not g.rows:
        return ""
    blocks = []
    for row in g.rows:
        cells = []
        for name, secs in row.table:
            on = " on" if name == row.tier else ""
            cells.append(f'<div class="tier{on}"><span class="tn">{_e(name)}</span>'
                         f'<span class="tv">{_clock_s_page(secs)}</span></div>')
        mark = (f'<span class="you">tú: {_clock_s_page(row.seconds)} · nivel '
                f'{_e(row.tier)}</span>')
        blocks.append(f'<div class="grade-row"><h4>{_e(row.age)} {mark}</h4>'
                      f'<div class="tiers">{"".join(cells)}</div></div>')
    if g.villagers_at_feudal and g.measured_villagers:
        vills = f" Al subir a Feudal tenías {g.villagers_at_feudal} aldeanos."
    elif g.villagers_at_feudal:
        vills = (f" Al subir a Feudal habías pedido {g.villagers_at_feudal} aldeanos; esta "
                 "grabación no trae los avisos de creación, así que es un tope, no un recuento.")
    else:
        vills = ""
    return (f'<figure><h3>En qué nivel quedan tus tiempos</h3>'
            f'<p class="sub prose">Comparado con «{_e(g.build)}», que es el plan al que más se '
            f'parece lo que hiciste.{_e(vills)} {_e(g.note)}</p>'
            f'<div class="grades">{"".join(blocks)}</div>'
            f'<figcaption>Baremo de {_e(g.source)}. Son referencias de 1v1 en mapa abierto tipo '
            f'Arabia: en Arena, en agua o en partidas por equipos no valen igual. La página no dice '
            f'a qué parche corresponden.</figcaption></figure>')


def _compare_table(r: Report) -> str:
    if not r.compares:
        return ""
    rival = _e(r.opponent or "rival")
    rows = []
    for c in r.compares:
        mine_cls = "win" if c.better == "mine" else ("lose" if c.better == "theirs" else "num")
        their_cls = "win" if c.better == "theirs" else ("lose" if c.better == "mine" else "num")
        mark_mine = _icon("check") if c.better == "mine" else ""
        mark_their = _icon("check") if c.better == "theirs" else ""
        rows.append(f"<tr><td>{_e(c.label)}</td><td class='num {mine_cls}'>{_e(c.mine)}{mark_mine}</td>"
                    f"<td class='num {their_cls}'>{_e(c.theirs)}{mark_their}</td></tr>")
    return (f'<figure><h3>Tú contra {rival}</h3><table><thead><tr><th></th>'
            f'<th>{_e(r.name)}</th><th>{rival}</th></tr></thead><tbody>' + "".join(rows) +
            '</tbody></table><figcaption>Todo esto lo escribe el juego en la tabla final de la partida: '
            'son datos, no estimaciones. La marca señala quién va mejor en cada fila.</figcaption></figure>')


# ------------------------------------------------------------------ pagina

RESULT_TEXT = {
    "derrota": ("Perdiste esta partida", "cross"),
    "victoria": ("Ganaste esta partida", "check"),
    "desconocido": ("Resultado no guardado", "dash"),
}


def render(r: Report) -> str:
    title, glyph = RESULT_TEXT[r.result]
    icon = _icon(glyph)
    if not r.findings:
        lead = "No encuentro ningún error que pase de un aldeano de coste."
    elif r.result == "victoria":
        lead = "Ganaste. Aun así, esto es lo que te frenó:"
    else:
        lead = "Lo que más te costó, por orden de coste:"
    quality = "".join(f"<li>{_e(q)}</li>" for q in r.quality)
    vs = f" · contra {_e(r.opponent)}" if r.opponent else ""
    charts = (
        _line_chart("Tus aldeanos, uno a uno",
                    ("Cada escalón es un aldeano que salió del centro urbano."
                     if r.villagers_measured else
                     "[ESTIMADO] Esta grabación no trae los avisos de creación: la curva sale de "
                     "simular tus órdenes de encolar, así que puede adelantarse a la realidad."),
                    r.villager_series, "aldeanos", r.duration_ms, r.idle_bands)
        + _line_chart("Recursos guardados sin gastar",
                      "Suma de los cuatro recursos en tu almacén. Mucho guardado y centro urbano parado "
                      "a la vez es la señal más clara de que sobraba con qué.",
                      list(r.stock_series), "recursos", r.duration_ms, r.idle_bands))
    forensic = (f'<details><summary>Informe completo con todas las pruebas, línea a línea</summary>'
                f'<pre>{_e(r.forensic)}</pre></details>' if r.forensic else "")
    return f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_e(r.name)} — {_e(r.map_name)}</title>
<style>{CSS}</style></head>
<body>{ICONS}<main>
<header class="hero {_e(r.result)}">
  <div>
    <h1>{icon}{title}</h1>
    <p class="sub">{_e(r.name)} con {_e(r.civ)} · {_e(r.map_name)} · {_clock(r.duration_ms)} de juego{vs}</p>
  </div>
  <button id="theme" class="theme">Cambiar claro / oscuro</button>
</header>

<h2>{lead}</h2>
{_findings_html(r)}

<h2>Cómo se decidió la partida</h2>
{_story(r)}
{_strength_chart(r)}
{_army_chart(r)}

{f'<h2>Tus tiempos contra el baremo</h2>{_grade_table(r)}' if r.grade else ''}

<h2>La partida de un vistazo</h2>
{_timeline(r)}

<h2>Cómo fue creciendo <span class="hint">toca una gráfica para ampliarla</span></h2>
{charts}

<h2>El mapa</h2>
{_minimap(r)}

{f'<h2>La comparación</h2>{_compare_table(r)}' if r.compares else ''}

<h2>Qué tan fiable es esto</h2>
<ul class="notes">{quality}</ul>
<p class="sub prose" style="margin-top:14px">El consejo de «la próxima vez» es un consejo de juego, no una deducción del archivo. Todo lo
demás sale de la grabación: lo medido viene de los avisos que el juego escribió, lo calculado es aritmética
sobre esos datos y lo estimado lleva su etiqueta.</p>

{forensic}
</main>
<dialog id="zoom"><div class="zoom-head"><span class="zoom-title"></span>
<button class="zoom-close" type="button">Cerrar</button></div><div class="zoom-body"></div></dialog>
<div id="tip"></div><script>{JS}</script></body></html>
"""
