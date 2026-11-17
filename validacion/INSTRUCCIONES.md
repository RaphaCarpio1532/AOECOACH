# Cómo validar el modelo con la repetición

Unos veinte minutos. Sirve para saber si el modelo acierta, no para corregir tu juego.

## Qué hacer

1. Abre en el juego la grabación de esta partida: Arabia, 2 contra 2 con IA, con georgianos.
2. Elige tu propia vista de jugador, la del jugador 1. Así arriba a la izquierda salen tus recursos.
3. Avanza hasta cada hora de la tabla y pausa. Si no clavas el segundo, no pasa nada: apunta la hora que marca el reloj al pausar.
4. En cada pausa apunta lo que veas. Vale dejar huecos.

## Instantes

2:06 · 4:54 · 8:24 · 11:54 · 16:05 · 18:27 · 20:56 · 25:04

Están elegidos para cubrir las cuatro edades, el paro largo del centro urbano y los tramos donde el modelo falla más.

## Qué apuntar en cada pausa

- **Los cuatro almacenes**: comida, madera, oro y piedra, tal como salen en pantalla.
- **Aldeanos en cada recurso**, si el juego los muestra junto a cada recurso.
- **Aldeanos en total**, si lo ves.
- **Centros urbanos produciendo**: cuántos tienen una barra de progreso en marcha.

## Cómo devolverlo

Lo más cómodo: dímelo de viva voz, instante a instante, y yo relleno la hoja.

Si prefieres escribirlo tú, rellena la hoja `hoja.csv` de esta carpeta y ejecuta:

```bash
.venv/bin/python -m aoe2coach fixtures/rec.aoe2record --validar validacion/hoja.csv --out validacion/resultado.md
```

## Por qué la hoja no trae las predicciones

Está en blanco a propósito. Si vieras lo que espera el modelo, sería fácil leer lo que confirma la predicción.

## Qué se comprueba

- **Controles duros.** La suma de tus cuatro almacenes debe coincidir con el total que guarda la grabación. Cada almacén debe caer dentro de las cotas calculadas. Nunca puede haber más aldeanos que los tres iniciales más los creados. Si alguno falla, hay un error en el lector o en las cotas.
- **Controles del modelo.** Cuánto se equivoca al estimar cada almacén y cuántos aldeanos hay en cada recurso.
