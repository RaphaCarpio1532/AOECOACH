# AoE2 Super Coach — Viabilidad y primera demostración

Fecha: 2026-11-17. Estado: fase 1 (investigación) y prueba de concepto del centro urbano.

Cada dato lleva su procedencia: **probado aquí** (lo ejecuté contra una grabación real),
**fuente** (lo leí en la fuente enlazada, sin ejecutarlo) o **no verificado**.

## 1. Conclusión en cinco líneas

1. Es viable. Una grabación `.aoe2record` actual (guardado 68.9) se lee completa: 114.906 acciones, cero tipos desconocidos.
2. Ningún parser acierta en todo con la versión actual. Hace falta una capa propia, fina y con pruebas por versión.
3. La inactividad del centro urbano se puede **estimar** solo con órdenes, y coincide con la medición independiente a 2 segundos mientras hay un solo TC.
4. Esa estimación es una **cota inferior**: no ve bloqueos de producción. En la partida de prueba se le escapan 74 segundos·TC de 674 en la fase final.
5. La grabación guarda órdenes, no estado. Recursos por tipo, población y bajas no están. Todo análisis causal serio depende de reconstruir ese estado o de aceptar que es hipótesis.

## 2. Matriz de viabilidad

| Componente | Qué es | Mantenimiento | Licencia | Resultado con guardado 68.9 | Veredicto |
|---|---|---|---|---|---|
| **mgz** (aoc-mgz) | Parser Python de referencia | Activo: 99 versiones desde 2017, última 1.8.51 el 2026-02-01; último commit 2026-10-19 (fuente: PyPI y GitHub) | MIT | **Probado aquí.** Cabecera: falla (sus pruebas llegan a 66.6). Cuerpo: se lee entero y decodifica bien las órdenes de cola, investigación y construcción | Usar para el cuerpo |
| **mgz-fast** | Paquete derivado, publicado desde el fork de AoEInsights | Una sola versión, 1.0.0 del 2026-02-27 (fuente: PyPI) | MIT según sus metadatos | **Probado aquí.** Cabecera: correcta, con objetos iniciales y posiciones. Cuerpo: se lee entero, pero devuelve mal los identificadores de edificio en las órdenes de cola | Usar para la cabecera. Ojo: se instala con el mismo nombre de módulo que mgz; no pueden convivir |
| **aoe2rec** | Parser en Rust con bindings Python y WASM | Activo: aoe2rec-py 0.1.24 del 2026-10-01; arreglo específico para 68.9 el 2026-09-22 (fuente: GitHub) | MIT | **Probado aquí.** Cabecera: correcta. Cuerpo: falla a 364 KB del inicio y el binding aborta en vez de devolver error | Mejor documentación del formato. No usar en producción todavía |
| **Capa propia** (`aoe2coach.replay`) | Cabecera mínima según el esquema de aoe2rec + cuerpo con los decodificadores de mgz | Este repositorio | — | **Probado aquí.** Lee todo; rechaza archivos corruptos con error explícito | Base del prototipo |
| **CaptureAge** (Free y Pro) | Visor y herramienta de retransmisión | Producto comercial | Propietaria | **Fuente.** Su documentación describe funciones de visor. No encontré API pública ni exportación de datos en dos búsquedas; un catálogo comunitario afirma que no existe | No depender. Útil solo para validar a ojo |
| **AoE2 Insights** | Web de estadísticas con análisis por partida | Activo | Propietaria | **Fuente.** Anuncia inactividad de TC acumulada como función de pago | Competidor directo en la métrica; referencia para contrastar |
| **AoE2 Coach** (aoe2coach.net) | Análisis de grabaciones con chatbot que compara con ganadores de tu ELO | Activo según el foro oficial | Propietaria | **Fuente** | Competidor directo en el concepto |
| **AoE2 Companion** | App de seguimiento de partidas | **No verificado** | **No verificado** | No encontré documentación de API pública | Investigar antes de contar con ella |
| **Agelytics** | — | — | — | **No encontrado** en dos búsquedas. No puedo confirmar que exista con ese nombre | Confirmar el nombre o descartar |
| **Descarga oficial de grabaciones** | Página de estadísticas de ageofempires.com | Oficial | Términos de Microsoft | **Fuente.** Existe un artículo de soporte oficial que explica cómo descargar grabaciones | Vía legítima para partidas profesionales; revisar términos antes de almacenar o redistribuir |
| **aoe2techtree** | Tiempos y costes de unidades, edificios y tecnologías | Activo: último cambio 2026-10-27 | MIT | **Probado aquí**, con una salvedad seria (ver 3.4) | Usar como referencia, nunca como verdad |

Proyectos abiertos parecidos que conviene leer antes de diseñar: marsupi-projects/aoe2-coach-v2 (agente LLM sobre grabaciones), Mauro0o/AOE2-Analyst, polaryse/aoe2-coach, byrnesy924/AgeAlyser_2. No los he ejecutado.

## 3. Qué se demostró con una partida real

Grabación: partida propia en Arabia, 2 contra 2 con IA, 28:24 de juego, guardado 68.9.

### 3.1 Reconstrucción

- Ficha, jugadores, civilizaciones y mapa: observados en la cabecera.
- Cronología de órdenes de los cuatro jugadores: 547 órdenes de cola, 162 investigaciones y 638 construcciones, con tipo, coordenadas e identificadores.
- Cada evento conserva su posición en el archivo, así que cualquier cifra del informe se puede auditar.
- El tiempo acumulado coincide con la marca de tiempo que cada acción lleva dentro (comprobado en la primera orden de cola).

### 3.2 Dos métodos independientes para el centro urbano

**A. Estimación por órdenes.** Simula la cola de cada TC. Funciona con cualquier grabación.

**B. Medición por avisos.** Esta grabación contiene los avisos en pantalla del jugador: 69 de «aldeano creado», 32 de «investigación completada», 2 de «centro urbano terminado». Son hechos observados con marca de tiempo.

Resultado de compararlos:

| Fase | Medido (B) | Estimado (A) | No determinable por A | Sin explicar |
|---|---|---|---|---|
| Un TC, 0:00–14:53 | 9 s·TC | 7 s·TC | 0 | 2 |
| Dos TC, 14:53–20:01 | 314 s·TC | 271 s·TC | 40 | 3 |
| Tres TC, 20:01–27:59 | 674 s·TC | 521 s·TC | 79 | 74 |

- Con un TC, las órdenes predicen 29 de 29 aldeanos con un error mediano de 0,03 segundos.
- Los 74 segundos·TC sin explicar son producción ordenada que no salía: un bloqueo entre 23:24 y 25:25 que las órdenes no dejan ver.
- Solape imposible del modelo (más TC ocupados que existentes): 0,7 segundos en toda la partida.

### 3.3 Semántica confirmada con datos

- Las unidades encoladas se pagan al encolar: a los 14 segundos el total de recursos es exactamente el inicial menos dos casas y cuatro aldeanos.
- Una investigación espera en la cola detrás de los aldeanos ya encolados. Feudal se ordenó en 6:07 y empezó en 6:45.
- Una orden de «cinco aldeanos» sobre tres TC reparte cinco, no quince: 71 ordenados, 69 creados, 2 en curso al acabar.

### 3.4 Sorpresas que cambian el diseño

- **Las investigaciones duraron el 40 % del tiempo de referencia** en esta partida (16 de 29 exactamente 0,40). Causa desconocida: ajuste, mod de datos o parche. Consecuencia: prohibido usar duraciones fijas; hay que calibrar con cada grabación y avisar cuando la tabla no encaja.
- **El aldeano tardó 24,8 segundos, no 25.** Pequeño, pero acumulado desplaza las predicciones.
- **Los avisos en pantalla no aparecen en ninguna de las 21 grabaciones multijugador de prueba de aoc-mgz que pude leer** (guardados 13.34 a 66.6). No sé si dependen del modo de un jugador, de una opción o de la versión. Hasta comprobarlo con una partida igualada reciente, el producto debe funcionar solo con el método A.
- La IA produce con una acción distinta a la del jugador humano. El análisis de producción de rivales IA no está cubierto.

## 4. Qué permite y qué no permite el formato

| Dato | Disponibilidad |
|---|---|
| Jugadores, civilización, mapa, ajustes | Observado |
| Órdenes de cola, investigación, construcción, movimiento, mercado, tributo | Observado |
| Tiempo de cada orden | Observado |
| Avance de edad de todos los jugadores | Observado (mensajes públicos) |
| Suma de los cuatro recursos por jugador, cada ~14 s | Observado, interpretación comprobada en un punto |
| Número de objetos por jugador | Observado, significado aproximado |
| Finalización de unidades y tecnologías del propio jugador | Observado solo si la grabación trae avisos |
| Recursos por tipo, población, bajas, combates | **No está.** Requiere simular el juego o visión artificial |
| Cancelaciones de cola, órdenes rechazadas | No identificadas |
| Tipo de unidad de cada identificador | Parcial: se deduce de la orden que la creó |

Consecuencia para el análisis causal: la cadena «mercado temprano → menos madera → granjas tarde → falta de comida → TC parado» tiene eslabones observables (la orden del mercado, las órdenes de granja, el paro del TC) y eslabones que hoy no lo son (madera y comida disponibles). Sin reconstrucción de estado, esos eslabones solo pueden ser hipótesis, y el informe debe decirlo.

## 5. Riesgos

1. **Rotura por parche.** Cada actualización del juego puede cambiar el formato. Mitigación: una grabación de prueba por versión, lista de versiones comprobadas, y rechazo explícito de lo no comprobado.
2. **Dependencia de parsers de terceros** con uno o dos mantenedores. Mitigación: capa propia fina; fijar versiones.
3. **Avisos ausentes en multijugador.** Si se confirma, la medición exacta solo existe en partidas contra IA.
4. **Datos de referencia que no coinciden con la partida.** Ya ocurrió. Mitigación: calibración por grabación.
5. **Competencia existente** en la métrica básica. La diferencia tiene que estar en la explicación causal validada, no en la cifra.
6. **Términos de uso** para almacenar grabaciones profesionales y para cualquier asistencia en vivo. Sin revisar.

## 6. Siguiente fase propuesta

Objetivo: pasar de «cuándo paró el TC» a «qué recursos había», que es lo que desbloquea las cadenas causales.

1. Conseguir dos grabaciones más: una igualada 1 contra 1 reciente y una profesional descargada por la vía oficial. Comprobar si traen avisos.
2. Reconstrucción de recursos por tipo: ingresos estimados por aldeano asignado y gastos observados, anclada a la suma real que da la grabación cada 14 segundos. La suma real sirve de control de error.
3. Población estimada: unidades creadas menos bajas inferidas, con el contador de objetos como control.
4. Validación manual: abrir la partida en el juego y contrastar cinco instantes concretos del informe.

Criterios de aceptación de la fase:

- Las tres grabaciones se leen o se rechazan con un error claro. Ninguna da datos a medias.
- El error del total de recursos reconstruido frente al observado queda documentado, sea el que sea.
- Ningún informe afirma una causa sin etiquetarla como hipótesis y sin listar la evidencia en contra.

## 7. Fuentes

- mgz en PyPI: https://pypi.org/project/mgz/ · código: https://github.com/happyleavesaoc/aoc-mgz
- mgz-fast en PyPI: https://pypi.org/project/mgz-fast/ · fork: https://github.com/AoEInsights/aoc-mgz
- aoe2rec: https://github.com/aoe2ct/aoe2rec · binding: https://pypi.org/project/aoe2rec-py/
- CaptureAge, documentación de Pro: https://captureage.com/docs/cade-latest/pro
- Catálogo comunitario de APIs: https://github.com/ustacode/aoe2-apis
- AoE2 Coach en el foro oficial: https://forums.ageofempires.com/t/aoe2-coach-aoe2coach-net-data-based-replay-analysis-tool-and-chatbot-that-compares-you-to-winners-at-your-elo/287451
- AoE2 Insights: https://www.aoe2insights.com/premium/
- Descarga oficial de grabaciones: https://support.ageofempires.com/hc/en-us/articles/34920298779540-Downloading-Replay-Files-through-the-Age-of-Empires-Stats-page
- Datos de referencia: https://github.com/SiegeEngineers/aoe2techtree
- Proyectos parecidos: https://github.com/marsupi-projects/aoe2-coach-v2 · https://github.com/Mauro0o/AOE2-Analyst · https://github.com/polaryse/aoe2-coach · https://github.com/byrnesy924/AgeAlyser_2
