# Fase 7 — Cadenas causales

Fecha: 2026-11-17. Probado contra la misma grabación (guardado 68.9).

## 1. Qué hace

Para cada paro largo del centro urbano, y para cada tramo en que había cola pagada pero no salía nada, construye una cadena:

1. **Efecto**: qué se midió y cuánto duró.
2. **Causa inmediata**: no había nada en cola, o había cola y no avanzaba. Desglosado por centro urbano.
3. **Causas posibles**, cada una con pruebas a favor y en contra y un veredicto.
4. **¿Y por qué?**: para las causas que siguen en pie, el eslabón anterior.
5. **Coste**: aldeanos sin hacer y una estimación de los recursos que no se recogieron.

## 2. Cómo se evita confundir correlación con causalidad

Una **prueba decisiva** es una contradicción con la mecánica del juego, nunca una coincidencia en el tiempo:

- El juego no acepta una compra sin recursos. Una compra aceptada de 100 de comida demuestra que había al menos 100 en ese instante.
- Si la población máxima posible es menor que el tope de casas, había hueco seguro, aunque no sepamos cuántas unidades murieron.
- Si las cotas dicen que el total almacenado era menor que el precio, faltaba seguro.

Un **indicio** encaja con la causa pero no la demuestra: casas que se terminan justo cuando se reanuda la producción, o muchas órdenes al ejército durante un paro.

| Veredicto | Regla |
|---|---|
| Respaldada | Prueba decisiva a favor y ninguna en contra |
| En parte | Pruebas decisivas a favor y en contra, o descartada en unos momentos y con indicios en otros |
| Descartada | Prueba decisiva en contra y ningún indicio en los momentos no cubiertos |
| Compatible | Solo indicios a favor |
| Sin datos | Nada a favor ni en contra |

Dos reglas fijas, con prueba automática:

- Ninguna prueba decisiva sale del modelo de aldeanos, que tiene confianza baja. Solo de hechos observados o de cuentas sobre ellos.
- La atención del jugador y sus decisiones nunca pasan de «compatible». La grabación no ve la pantalla ni la intención. Se describe qué órdenes dio, no qué pensaba.

## 3. Causas que se comprueban

| Causa | A favor | En contra |
|---|---|---|
| Falta de comida | Cotas: total almacenado menor que 50 | Compras aceptadas con comida durante el paro; cotas que demuestran 50 o más |
| Tope de población | Población posible igual o mayor que el tope (indicio); casas terminadas justo antes de reanudar (indicio) | Población máxima posible por debajo del tope |
| Centro urbano nuevo sin órdenes | Terminado en T, primera orden en T′ | — |
| Guardar el TC para avanzar de edad | Lo siguiente que hizo ese TC fue investigar la edad (indicio) | — |
| Dejar de hacer aldeanos | No hubo más órdenes de aldeano hasta el final (indicio) | — |
| Atención en otra parte | Mayoría de órdenes al ejército; avisos de ataque (indicios) | — |

**La población.** Cada aviso de unidad creada se retrasa su tiempo de entrenamiento: desde ese momento ocupa población. Así la cota superior incluye las unidades que se están entrenando. El tope sale de los avisos de casa y de centro urbano terminados. No ve las muertes, por eso «lleno» es solo un indicio. Tampoco ve las casas destruidas, y eso es un supuesto del «hueco seguro».

## 4. Qué dice de tu partida

**Paro de 14:53 a 18:59, 314 s·TC.**
- ✔ El segundo centro urbano se terminó a las 14:53 y no recibió órdenes hasta las 15:33. Explica 40 s.
- ✘ No fue falta de comida: el juego aceptó diez compras con comida durante el paro.
- ◐ Tope de población: había hueco seguro en 41 de 50 instantes. En los otros 9, cerca de las 15:33, pudo estar lleno.
- ? El centro urbano inicial estuvo parado de 15:33 a 18:45, y lo siguiente que hizo fue investigar Imperial. Encaja con guardarlo para avanzar. El modelo estima comida de sobra, así que hacer aldeanos mientras tanto no habría retrasado el avance.
- ? Diste 196 órdenes en esos cuatro minutos, 127 de ellas al ejército, y hubo dos avisos de ataque.
- Coste: unos 13 aldeanos sin hacer.

**Paro de 20:01 a 21:20, 153 s·TC.**
- ✔ El tercer centro urbano se terminó a las 20:01 y no recibió órdenes hasta las 21:20.
- ✘ No fue comida ni población.
- ? Las 53 órdenes de ese tramo fueron al ejército, con cinco avisos de ataque.

**Paro de 22:35 al final.**
- ? No volviste a encargar aldeanos. Puede ser una decisión, con 71 creados. Si lo fue, el coste no aplica.
- ◐ Tope de población: en la mayor parte del tramo la población posible alcanzaba el tope.

**Producción bloqueada de 23:24 a 25:04.**
- ◐ Tope de población: hasta las 23:54 pudo haberlo; desde ahí había hueco seguro. Se terminaron seis casas durante el bloqueo.
- Queda sin explicar el tramo con hueco. Puede ser una cola cancelada, que la grabación no muestra.

## 5. Límites

- Solo cubre paros del centro urbano. Faltan otras cadenas: avance de edad tardío, ejército perdido, economía estancada.
- Las causas son un catálogo cerrado. Una causa que no está en la lista no aparece.
- No hay partidas de referencia, así que no se puede decir si un hábito es peor que lo habitual.
