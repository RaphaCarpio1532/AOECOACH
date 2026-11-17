# AoE2 Super Coach — prototipo

Primer paso del proyecto: demostrar que se puede leer una grabación real de
Age of Empires II: DE y medir o estimar con honestidad la inactividad del
centro urbano. No hay todavía API, base de datos, LLM ni panel web.

## Probarlo en Windows, con doble clic

1. Instala Python 3.12 desde python.org. Durante la instalación, marca la casilla «Add python.exe to PATH».
2. En esta página de GitHub, pulsa el botón verde «Code» y luego «Download ZIP». Descomprime la carpeta donde quieras.
3. Juega una partida, o usa una que ya tengas.
4. Haz doble clic en `analizar.bat`. La primera vez tarda un minuto en prepararse.

Analiza tu partida más reciente y abre el informe en el navegador. Para analizar otra, arrastra su archivo `.aoe2record` encima de `analizar.bat`. Si en la partida hay más de un humano, te pregunta cuál eres y lo recuerda para la próxima vez. Los informes se guardan en la carpeta `informes`.

Si Windows muestra «Windows protegió su PC», pulsa «Más información» y luego «Ejecutar de todas formas»: el aviso sale con cualquier archivo descargado que no esté firmado.

## Usar desde la terminal

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
| `docs/05-prueba-hera.md` | Prueba con una partida profesional multijugador y el vídeo del jugador |
| `docs/04-causas.md` | Cadenas causales: cómo se prueba o descarta cada causa y qué dice de la partida |
| `reports/` | Informes generados (no se suben: contienen el alias del jugador) |
| `src/aoe2coach/replay.py` | Lectura: bytes → hechos observados, con trazabilidad |
| `src/aoe2coach/tc.py` | Producción del centro urbano: estimación y medición |
| `src/aoe2coach/economy.py` | Economía: libro de gastos, ingreso total, cotas y reparto por tipo |
| `src/aoe2coach/villagers.py` | Qué hace cada aldeano: edificios por posición y reglas de tarea |
| `src/aoe2coach/causal.py` | Cadenas causales: efecto, causa inmediata, causas con pruebas a favor y en contra, coste |
| `src/aoe2coach/validation.py` | Validación contra la repetición: hoja ciega, controles duros y error del modelo |
| `validacion/` | Hoja en blanco, instrucciones, y la hoja leída del vídeo de Hera |
| `src/aoe2coach/report.py` | Informe con etiquetas de procedencia |
| `src/aoe2coach/refdata.py` | Datos de referencia y su origen |
| `tests/` | 44 pruebas: 32 contra tu grabación y 3 contra una partida profesional (ninguna de las dos grabaciones se sube; esas pruebas se saltan si faltan) |
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
