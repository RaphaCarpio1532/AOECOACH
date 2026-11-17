# Fase 2 — Economía: gastos, ingresos y recursos por tipo

Fecha: 2026-11-17. Todo lo de esta página está **probado aquí** contra la misma grabación (guardado 68.9).

## 1. Resultado en cuatro líneas

1. **Gastos por tipo: resuelto.** 203 órdenes con coste, todas con coste de referencia.
2. **Ingreso total: resuelto.** Sale de la suma de recursos que guarda la grabación más los gastos. Cero tramos imposibles de 119.
3. **Recursos por tipo, exactos: no se puede.** Lo que sí se puede es acotarlos con rigor, sin modelo.
4. **Modelo de reparto por aldeanos: hoy no es fiable.** Lo contradicen 60 de 262 compras. Queda medido y fuera de las conclusiones.

## 2. Tres niveles, tres certezas

### Nivel 1 — Libro de gastos [CALCULADO]

Cada orden de entrenar, investigar o construir, por su coste de referencia.

| Recurso | Gastado en la partida |
|---|---|
| Comida | 16.820 |
| Madera | 9.860 |
| Oro | 8.045 |
| Piedra | 800 |

No ve: resiembra automática de granjas, devoluciones por cancelar, reparaciones.

### Nivel 2 — Ingreso total [CALCULADO]

Ingreso de un tramo = variación de la suma observada + gastos del tramo.

| Tramo | Ingreso por minuto | Gasto por minuto |
|---|---|---|
| Alta Edad Media | 346 | 235 |
| Feudal | 783 | 800 |
| Castillos | 1.566 | 1.251 |
| Imperial | 2.392 | 2.369 |

Es un mínimo, por los gastos que no se ven.

### Nivel 3a — Cotas por recurso [CALCULADO, sin modelo]

- **Mínimo.** Si más adelante se acepta una compra de X, y entre medias el ingreso total fue como mucho Y, ahora había al menos X − Y. Las compras seguidas se suman.
- **Máximo.** El total observado menos los mínimos de los otros tres recursos.

Con esto se responde con rigor a «¿pudo faltar comida para un aldeano?»: demostrado que sí había en 32 de 119 muestras, demostrado que no en 0, indecidible en el resto.

### Nivel 3b — Modelo de reparto [ESTIMADO, confianza baja]

Deduce a qué recurso va cada aldeano por puntos de reunión y órdenes, y reparte el ingreso total en proporción.

- Clasifica al 71 % de los aldeanos.
- Lo contradicen 60 de 262 compras aceptadas: 35 de oro y 25 de madera.
- Causa identificada: 78 órdenes a objetivos que la cabecera no describe. Seis aldeanos construyen el carro de mulas y el modelo no sabe que después minan oro.

## 3. Controles cruzados que ya funcionan

| Control | Resultado | Qué demuestra |
|---|---|---|
| Unidades creadas nunca superan a las ordenadas, en ningún instante | 5 líneas de 5 | El juego aceptó las órdenes; «cinco unidades en N edificios» son cinco, no cinco por edificio |
| Ingreso derivado nunca negativo | 119 tramos de 119 | Los costes de referencia valen para esta partida |
| Mínimos por recurso compatibles con el total observado | 119 muestras de 119 | Costes y aceptación son coherentes entre sí |
| Recursos de inicio recuperados de la primera muestra | 700, el estándar | La suma observada es realmente la suma de los cuatro almacenes |
| TC inicial deducido de las órdenes frente a la cabecera | Coincide | La identificación de edificios por órdenes es correcta |

El segundo control ya detectó un error real durante el desarrollo: dos tramos negativos señalaron las mejoras de Arquero a caballo pesado y Húsar, cuyo coste faltaba en la tabla.

## 4. Qué cambia para el análisis causal

Sobre el ejemplo del encargo (mercado → menos madera → granjas tarde → falta de comida → TC parado):

| Eslabón | Estado hoy |
|---|---|
| Se construyó un mercado en T | Observado |
| Costó 175 de madera | Calculado, coste auditado |
| Después hubo menos madera disponible | **Solo cota.** Decidible si el total almacenado era bajo |
| Las granjas se ordenaron más tarde de lo habitual | Observado el cuándo; «lo habitual» necesita partidas de referencia |
| Faltó comida | **Cota.** Demostrable cuando el total almacenado es menor que el precio; refutable cuando hay compras de comida cerca |
| El TC paró | Medido o estimado, según haya avisos |

En esta partida la cadena no aplica: los paros largos del TC coinciden con entre 2.200 y 6.500 recursos almacenados, y durante ellos se gastó comida en otras cosas. Eso apunta a hábito o atención, no a escasez. Sigue siendo hipótesis.

## 5. Siguiente paso

1. Identificar los edificios propios por su posición: toda orden de construir da coordenadas, y las órdenes posteriores a ese punto se pueden emparejar. Con eso se sabría qué aldeanos van a granjas, campamentos y carro de mulas, que es donde falla el modelo.
2. Usar las cotas como restricciones del modelo, en vez de solo como examen.
3. Repetir todo con una partida igualada reciente. Sigue pendiente saber si trae avisos.
4. Validación manual contra la repetición en cinco instantes.
