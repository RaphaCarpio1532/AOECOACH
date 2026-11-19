# AoE2 Super Coach — prototipo

Primer paso del proyecto: demostrar que se puede leer una grabación real de
Age of Empires II: DE y medir o estimar con honestidad la inactividad del
centro urbano. No hay todavía API, base de datos, LLM ni panel web.

## Probarlo en Windows, con doble clic

1. Instala Python 3.12 desde python.org. Durante la instalación, marca la casilla «Add python.exe to PATH».
2. En esta página de GitHub, pulsa el botón verde «Code» y luego «Download ZIP». Descomprime la carpeta donde quieras.
3. Juega una partida, o usa una que ya tengas.
4. Haz doble clic en `analizar.bat`. La primera vez tarda un minuto en prepararse.

Analiza tu partida más reciente y abre el informe en el navegador: arriba, las tres cosas que más te costaron, con su coste en aldeanos y qué hacer la próxima vez; debajo, la línea de tiempo de la partida, las gráficas, el mapa de dónde construiste y la comparación contra tu rival. El informe forense completo va plegado al final, para quien quiera la letra pequeña. Para analizar otra, arrastra su archivo `.aoe2record` encima de `analizar.bat`. Si en la partida hay más de un humano, te pregunta cuál eres y lo recuerda para la próxima vez. Los informes se guardan en la carpeta `informes`.

Si Windows muestra «Windows protegió su PC», pulsa «Más información» y luego «Ejecutar de todas formas»: el aviso sale con cualquier archivo descargado que no esté firmado.

## Usar desde la terminal

```bash
uv venv --python 3.12 .venv && uv pip install --python .venv/bin/python -e ".[dev]"
```

```bash
.venv/bin/python -m aoe2coach fixtures/rec.aoe2record --html reports/informe.html
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
| `src/aoe2coach/battle.py` | Lo militar: qué pidió cada jugador, qué contrarresta a qué (de la tabla del juego) y cómo acabó |
| `src/aoe2coach/buildorders.py` | Órdenes de construcción de referencia con niveles A+ a E, y de cuál se parece más a lo que jugaste |
| `src/aoe2coach/coach.py` | Entrenador: de la evidencia a los pocos consejos que importan, ordenados por lo que costaron |
| `src/aoe2coach/page.py` | La página que ve el jugador: un HTML sin internet ni dependencias |
| `src/aoe2coach/postgame.py` | Tabla final de la partida: quién ganó, tiempos de edad de cada jugador, recursos, bajas |
| `src/aoe2coach/report.py` | Informe forense con etiquetas de procedencia |
| `src/aoe2coach/refdata.py` | Datos de referencia y su origen |
| `tests/` | 55 pruebas que no se clavan a ninguna partida: las que necesitan los avisos de pantalla se saltan si la grabación no los trae |
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

## Cómo se decide qué contarte

El motor produce pruebas con su procedencia: medido, calculado, estimado o hipótesis. Encima de eso,
`coach.py` elige las POCAS que merece la pena contar y las ordena por una moneda común, **aldeanos
equivalentes**:

- Un paro del centro urbano cuesta sus segundos parados entre lo que tarda un aldeano.
- Llegar tarde a una edad cuesta los segundos de retraso, medidos contra lo que tardó tu rival
  (los dos tiempos los escribe el juego en la tabla final, no se estiman).
- Tener menos aldeanos que el rival cuesta esa diferencia.
- Llegar a una edad por debajo del nivel E del baremo cuesta los segundos de más.
- Que su unidad principal no tuviera respuesta cuesta según cuántas hizo.

Los contraataques no son opinión: cada unidad del juego lleva sus clases de armadura y sus bonus de
ataque. Si la tuya tiene bonus contra una clase que la suya lleva, la contrarresta, y el número sale
de la tabla del juego.

Los avisos del juego se leen en el idioma del jugador (inglés y español) y en el formato JSON de las versiones recientes. Sin ellos, los tiempos de edad salen igual, pero la producción solo se estima.

El baremo de tiempos depende del plan que jugaste, porque un Fast Castle llega tarde a Feudal a
propósito. El plan se deduce de tus aldeanos al subir de edad y de lo que produjiste.

Por debajo de un aldeano no se cuenta nada: un informe que señala todo no señala nada. El consejo de
«la próxima vez» es un consejo de juego y va marcado como tal; todo lo demás sale de la grabación.

## Habilidades de diseño

La página se construyó siguiendo `impeccable` (suelo de calidad de interfaz) y la guía de
visualización de datos: paleta validada contra daltonismo y contraste en claro y oscuro, iconos
dibujados en vez de emojis, teclado y `prefers-reduced-motion` atendidos. Las habilidades no se
suben al repositorio; `skills-lock.json` dice cuáles son y con qué versión, y se reinstalan con
`npx skills add`.
