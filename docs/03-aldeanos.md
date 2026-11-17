# Fase 3 — Qué hace cada aldeano

Fecha: 2026-11-17. Probado contra la misma grabación (guardado 68.9).

## 1. Resultado

El modelo que reparte recursos por tipo pasó de contradecir 60 de 262 compras aceptadas a contradecir 14. Por más de 50 recursos, solo 10.

| Versión | Compras contradichas | Por más de 50 | Déficit acumulado |
|---|---|---|---|
| Modelo de la fase 2 | 60 | — | — |
| Reglas nuevas, sin reliquias | 22 | 19 | 4.665 |
| Reglas nuevas y oro de reliquias | 14 | 10 | 2.019 |
| Recuento de aldeanos corregido (sección 6) | 25 | 20 | 3.873 |

Sigue siendo una **estimación**, ahora con confianza baja. El informe la usa como contexto y nunca como prueba.

## 2. Qué cambió

1. **Registro de edificios propios por posición.** Cada orden de construir da tipo y coordenadas. Cuando una orden posterior hace clic justo ahí, su objetivo queda identificado. Reconoce 34 órdenes que antes eran opacas: el carro de mulas, molinos, centros urbanos, casas a medio construir.
2. **Solo cuentan los aldeanos.** Son aldeanos los iniciales, quien construye algo y quien recibe orden de recoger. Se excluye a quien patrulla o ataca en movimiento. Antes, las órdenes del ejército contra edificios enemigos dejaban «sin tarea» a aldeanos que no existían.
3. **Reglas de comportamiento, cada una medida por separado:**

| Regla | Evidencia |
|---|---|
| Quien termina un punto de entrega recoge lo que tiene al lado | Observado: dos de los seis constructores del carro de mulas no reciben otra orden en toda la partida, y la mina de oro está a dos casillas. Sin esta regla, 35 compras de oro imposibles |
| Quien termina otro edificio vuelve a su tarea | Mejora el acuerdo (24 → 19 contradicciones graves) |
| Llevar carga a un punto de entrega no cambia la tarea | Mejora el acuerdo (32 → 19) |
| n granjas encadenadas ocupan a n constructores | Mejora mucho el final de la partida (29 → 19) |

4. **Oro de reliquias aparte.** Medio oro por segundo y reliquia, según dos fuentes comunitarias que no dicen a qué parche corresponden. Se cuenta desde el aviso de reliquia recogida, lo que lo sobreestima un poco. Los datos de esta partida no distinguen entre medio y un oro por segundo.

## 3. Prueba contra el sobreajuste

Elegí las reglas mirando las compras, así que el examen no es del todo independiente. Para medirlo, escogí las reglas solo con la primera mitad de la partida y las examiné con la segunda:

- La regla del punto de entrega gana en las dos mitades. Está respaldada.
- La de las granjas encadenadas no se puede elegir con la primera mitad, porque solo hay granjas encadenadas al final. Con la primera mitad se habría descartado y la segunda daría 25 contradicciones en vez de 6. **Está respaldada solo por datos que también se usaron para elegirla.**

## 4. Lo que falla todavía

Esta lista es de antes de corregir el recuento. Después, los fallos de madera pasan a ser 17, entre los minutos 11 y 16 (ver sección 6).

- Madera, minutos 11 a 14: cuatro compras que el modelo ve imposibles por entre 70 y 160. Probable causa: reparto proporcional al número de aldeanos, sin ritmos distintos por recurso.
- Oro, minutos 15 a 22: cinco compras, por entre 100 y 320. Puede ser el ritmo de las reliquias o mineros que no se ven.
- Comida, minuto 28: una compra de exploradores, por 380. Al final el modelo llega a dar comida negativa, así que en los últimos minutos no es fiable.
- Supuestos sin resolver: nadie muere; las tareas cambian al dar la orden, no al llegar; un aldeano nuevo que aparece por primera vez sale del grupo sin identificar en orden de antigüedad.
- No modela mercado ni tributos. En esta partida no los usaste; en otras habrá que añadirlo.

## 5. Qué dice ya de tu partida

- [ESTIMADO] Durante el paro largo del centro urbano (14:53 a 18:59), la comida estaba entre unas 2.100 y 4.200. No fue falta de comida. Esta conclusión se mantiene con las dos versiones del modelo.
- [ESTIMADO] En el tramo final (22:35 a 27:59) la comida cae hasta casi cero por el gasto en húsares. Ahí la escasez es plausible, pero es justo donde el modelo falla más, y la producción ya estaba parada antes de esa caída.
- [CALCULADO] Lo firme sigue siendo lo de las cotas: nunca está demostrado que faltara comida.

## 6. Corrección del recuento y lo que reveló

Al preparar la validación contra la repetición comparé un hecho duro que antes no miraba: el modelo nunca puede tener más aldeanos que los tres iniciales más los creados. Lo incumplía en todas las muestras, con hasta 11 de más.

Tres causas, corregidas:

1. El centro urbano y el explorador contaban como aldeanos cuando recibían una orden sobre un recurso. Ahora se excluye todo objeto de tipo conocido que no sea aldeano y todo edificio que produce o investiga.
2. Un aldeano que recibía una orden sin objetivo reconocido entraba en la cuenta sin salir del grupo sin identificar. Contaba dos veces.
3. El ganado ya capturado tiene dueño y no se reconocía como comida.

Ahora el recuento es exacto hasta el minuto 8. Desde ahí se excede en el 22 % de las muestras, con un máximo de 7 al final.

**Lo incómodo:** con el recuento corregido, el acuerdo con las compras empeora, de 10 contradicciones graves a 20, casi todas de madera entre los minutos 11 y 16. Es decir, parte del buen resultado anterior venía de errores que se compensaban. Tampoco se sostiene ya que el oro de reliquias mejore el acuerdo: con el recuento corregido lo empeora un poco (18 frente a 20).

**Causa probable:** las tareas se pegan. Un aldeano marcado en comida por pastorear sigue en comida para siempre, aunque las ovejas se acaben y pase a otra cosa sin una orden que el modelo entienda.

**Qué sigue en pie:** las reglas siguen ganando con claridad al modelo ingenuo (20 frente a 41), y la conclusión sobre el paro largo del centro urbano no cambia.

**Qué lo decide:** la validación con la repetición. El juego muestra cuántos aldeanos hay en cada recurso, que es justo lo que aquí se discute. Instrucciones y hoja en la carpeta de validación.
