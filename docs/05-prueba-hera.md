# Prueba con una partida profesional y su vídeo

Fecha: 2026-11-17.

## 1. Qué se probó

- **Partida**: 1v1 clasificatoria en el mapa Michi, 25 de octubre de 2026. Hera con britanos contra Emu Warrior con mongoles. Partida número 516341955, 153 minutos de juego.
- **Grabación**: la de Emu Warrior, descargada de los servidores oficiales de Age of Empires. La de Hera ya había caducado. Una grabación contiene las órdenes y los totales de los dos jugadores, así que sirve para analizar a Hera.
- **Control**: el vídeo de Hera de esa partida, publicado en su canal de gameplay. Muestra su pantalla con sus cuatro recursos, los aldeanos en cada uno y el reloj de la partida.
- **Método**: se pausó el vídeo en once momentos, del minuto 3 al 1:20 de juego, y se apuntó lo que se ve. La hoja está en la carpeta de validación. Se comparó con lo que calcula el sistema para Hera.

Aviso de método: quien leyó el vídeo ya había visto las predicciones del sistema. Se leyeron cifras impresas en pantalla, así que el riesgo de sesgo es bajo, pero la lectura no fue ciega.

## 2. Resultados

| Qué | Resultado |
|---|---|
| Lectura de la grabación multijugador | Completa: 33.062 acciones, ninguna sin interpretar, en menos de un segundo |
| Controles duros contra el vídeo | **55 de 55 cumplidos** |
| Suma de los cuatro recursos en pantalla frente al total de la grabación | Exacta en 5 de 11 momentos; en el resto, dentro del margen por la diferencia de segundos |
| Modelo de aldeanos por recurso | 22 de 44 dentro del margen; sobrestima la madera desde el minuto 14 |
| Modelo de recursos por tipo | **Suspende**: da comida negativa desde el minuto 4; contradice 693 de 1.802 compras |

## 3. Qué se aprendió

1. **El lector es correcto también en partidas multijugador recientes.** Es la confirmación más fuerte hasta ahora, porque se comprueba contra la pantalla real del jugador.
2. **Las grabaciones multijugador no traen avisos de pantalla** («aldeano creado» y similares). Sin ellos:
   - el paro del centro urbano solo se puede estimar, como mínimo, no medir;
   - la población no se puede acotar.
3. **Había un fallo grave en las cadenas causales.** Sin avisos, el sistema calculaba la población como si nadie se hubiera creado y daba por *descartado* el tope de población con una prueba «decisiva» falsa. Hera estaba en 200 de 200. **Corregido**: sin avisos del jugador analizado, la población queda «sin datos».
4. **El modelo de aldeanos estaba ajustado a una sola partida.** En esta falla mucho: no ve muertes (Hera pasó de 137 aldeanos a 58), ni mercado, ni carros de comercio. **Corregido**: si contradice a más del 10 % de las compras, sus cifras no se usan en ninguna parte del informe ni de las causas.
5. **Faltan gastos en el libro.** Compras y ventas en el mercado (113 órdenes), murallas (20), borrar edificios y reparar. Por eso salen 32 tramos de ingreso negativo de 1.014. Pendiente.
6. **Los tramos de paro con varios centros urbanos se funden** en uno solo de 125 minutos, porque casi siempre hay alguno parado. Con población llena, eso es normal y no un error. **Corregido** en parte: un tramo largo que llega al final ya no se cuenta como aldeanos perdidos. Pendiente: separar la fase de producción de la fase con objetivo cumplido.
7. **Corrección en tu propia partida.** La cadena del paro final decía que no volviste a encargar aldeanos desde el minuto 22 y medio. Era falso: el centro urbano inicial siguió produciendo hasta el 26:22. El error venía de comprobar órdenes después del final del tramo, no dentro. Corregido.

## 4. Lo siguiente

- Añadir al libro de gastos el mercado, las murallas, las reparaciones y el borrado.
- Probar con la grabación del propio jugador analizado, para tener avisos y medir en vez de estimar.
- Rehacer el modelo de aldeanos con muertes y varias partidas, o sustituirlo por algo que no dependa de él.
