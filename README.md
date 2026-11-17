# AoE2 Super Coach — prototipo

Primer paso del proyecto: demostrar que se puede leer una grabación real de
Age of Empires II: DE y medir o estimar con honestidad la inactividad del
centro urbano. No hay todavía API, base de datos, LLM ni panel web.

## Usar

```bash
uv venv --python 3.12 .venv && uv pip install --python .venv/bin/python -e ".[dev]"
```

```bash
.venv/bin/python -m aoe2coach fixtures/rec.aoe2record --out reports/informe-tc.md
```

```bash
.venv/bin/python -m aoe2coach fixtures/rec.aoe2record --validar validacion/hoja.csv --out validacion/resultado.md
```

```bash
.venv/bin/python -m pytest -q
```

## Qué hay

| Ruta | Contenido |
|---|---|
| `docs/01-viabilidad.md` | Matriz de viabilidad, hallazgos, riesgos y siguiente fase |
| `docs/02-economia.md` | Gastos, ingresos y cotas por recurso |
| `docs/arquitectura.html` | Mapa interactivo del código: qué función llama, crea, lee o modifica qué |
| `docs/resumen.html` | Resumen visual: cómo funciona, qué mide y qué falta |
| `docs/03-aldeanos.md` | Modelo de tareas de aldeanos: reglas, evidencia y prueba contra el sobreajuste |
| `reports/` | Informes generados (no se suben: contienen el alias del jugador) |
| `src/aoe2coach/replay.py` | Lectura: bytes → hechos observados, con trazabilidad |
| `src/aoe2coach/tc.py` | Producción del centro urbano: estimación y medición |
| `src/aoe2coach/economy.py` | Economía: libro de gastos, ingreso total, cotas y reparto por tipo |
| `src/aoe2coach/villagers.py` | Qué hace cada aldeano: edificios por posición y reglas de tarea |
| `src/aoe2coach/validation.py` | Validación contra la repetición: hoja ciega, controles duros y error del modelo |
| `validacion/` | Hoja en blanco e instrucciones para rellenarla viendo la repetición |
| `src/aoe2coach/report.py` | Informe con etiquetas de procedencia |
| `src/aoe2coach/refdata.py` | Datos de referencia y su origen |
| `tests/` | 36 pruebas, 29 de ellas contra la grabación real |
| `fixtures/` | Pon aquí tu grabación como `rec.aoe2record`. No se sube al repositorio porque contiene el alias del jugador; sin ella, las pruebas contra la grabación se saltan |

## Reglas que el código ya cumple

- Un archivo que no se entiende se rechaza con error. Nunca se devuelven datos a medias.
- Toda cifra del informe es observada, calculada, estimada o hipótesis, y lo dice.
- Las duraciones se calibran con cada grabación. La tabla de referencia no es la verdad.
- El análisis determinista no llama a ningún modelo de lenguaje.

## Licencias de terceros

`mgz` (MIT, happyleavesaoc) para decodificar acciones. Lector de objetos
iniciales copiado de `mgz-fast` 1.0.0 (MIT) en `src/aoe2coach/_vendor`. Esquema de cabecera
tomado de `aoe2rec` (MIT, aoe2ct). Tiempos y costes de `aoe2techtree` (MIT,
SiegeEngineers).
