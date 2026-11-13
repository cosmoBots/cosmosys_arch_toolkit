# Validación: ranura ancha y compuerta de traslación lateral

Abrir **Altaz_C.blend** en esta carpeta. Es la única versión vigente del modelo.
La abertura triangular se retiró por obstruir el haz. No se importan mallas de
las fotos de referencia.

El archivo se abre en **Observatory**, con **DOF_Shutter** seleccionado:

1. En **N → Item → Location**, cambiar **X** de **0 m** a **3,6 m**.
2. La compuerta se retira lateralmente, dejando libre una abertura que no se
   estrecha en el cénit. No cambiar su rotación: está bloqueada.
3. Seleccionar **DOF_Elevation**: rotación local **X=0°** mira al cénit;
   **X=90°**, al horizonte. PORIS astronómico sigue usando CAD=90−PORIS.
4. Para girar el observatorio, usar **DOF_Dome_Azimuth → Rotation Z**; arrastra
   carcasa, raíles y compuerta. El telescopio tiene su propio **DOF_Azimuth**.

Siguen siendo cuatro parámetros independientes: tres rotaciones en grados y
una traslación en metros. El YAML generado identifica `shutter_open` como
`transform: position`, eje local X, rango 0…3.6 y paso 0.05. No hay acoplamientos
ocultos ni mecanismos que deba resolver el runtime.

## Dimensiones elegidas

| Magnitud | Propuesta |
| --- | --- |
| Diámetro del cuerpo cilíndrico | 12 m (antes 10,4 m) |
| Radio de la carcasa hemisférica | 6 m |
| Altura del centro de la cúpula | 2,75 m |
| Altura del eje de elevación | 5 m (antes 4,15 m) |
| Diámetro del espejo primario representado | 1,86 m |
| Diámetro de pupila usado para comprobar | 2,20 m |
| Ancho de la abertura | 3,20 m, entre planos paralelos |
| Continuación hacia atrás desde el cénit | 20° |
| Recorrido lateral de la cubierta | 3,60 m |

La ranura ya no se obtiene recortando una cuña de longitud angular constante.
Se recorta entre **x=−1,60 m y x=+1,60 m** y se continúa detrás del cénit.
Por tanto, conserva anchura allí donde antes convergía a un punto.

La cubierta tiene mayor radio (6,40 m), se solapa al cerrar y se aparta por X.
Su radio y ancho dejan una holgura radial conservadora de unos **11 cm** frente
a la carcasa durante la traslación. No requiere levantar una gran hoja ni
hacerla descender por la parte posterior del edificio.

Subir el eje de elevación también deja unos **29 cm** entre el instrumento
trasero y el travesaño de la horquilla en el muestreo del recorrido. Se mantiene
un margen radial aproximado de **77 cm** entre la envolvente muestreada del
telescopio y la piel interior de la cúpula.

## Comprobación de apertura óptica

El generador lanza **22.344 rayos** desde una pupila conservadora de 2,20 m:

- Elevación mecánica de 0° a 90°, cada 5° (incluye cénit y horizonte).
- Azimuths 0°, 45°, 120° y 240°, con la cúpula alineada.
- Centro y dos anillos de pupila; desviaciones de campo de −0,5°, 0° y +0,5°,
  tanto en el plano meridiano como transversal.
- Se incluyen carcasa, compuerta abierta, raíles, edificio y anexo como obstáculos.

**Resultado: cero bloqueos en los rayos muestreados.** Cerrada, la compuerta
bloquea el eje óptico cenital, para comprobar que el ensayo detecta un obstáculo.

Se añaden cotas conservadoras de la sección del haz para no depender sólo del
muestreo: para una pupila de radio 1,10 m, desfase axial 0,91 m y un margen de
trayecto de 14 m, la deriva de campo es `14*tan(0,5°) ≈ 0,122 m`. La cota
transversal del haz es ±1,223 m, menor que la semianchura útil de 1,60 m.
Las cotas de posición mínima hacia atrás y en altura también quedan dentro
del hueco y por encima del raíl frontal. Los valores se guardan en validation.json.

Son cálculos geométricos de esta maqueta; no un trazado óptico completo, cálculo
constructivo ni certificación de colisiones. Por petición del usuario, viento y
cargas quedan fuera del alcance. El telescopio se comprueba como conjunto rígido
y no se modelan mecanismos de accionamiento, apoyos detallados o estanqueidad.

## Reproducir

Desde la raíz del toolkit, usando el Blender ya instalado:

```sh
blender --background --factory-startup --disable-autoexec -noaudio --python-exit-code 1 \
  --python tools/examples/altaz_c/build.py -- --output modelos/reconstruccion --no-render

node tools/examples/altaz_c/verify_glb.mjs modelos/reconstruccion

blender --background --disable-autoexec -noaudio \
  examples/Altaz_C/Altaz_C.blend --python-exit-code 1 \
  --python tools/examples/altaz_c/verify_blend.py
```

El primer comando reconstruye el modelo en una carpeta que no debe existir:
no usarlo para exportar ediciones manuales (para eso está `./toolkit export`).
Sustituir `blender` por la ruta local configurada en `.env` si no está en PATH.
El exportador común deriva la configuración de las restricciones nativas:
Limit Rotation para los giros y Limit Location para la traslación.
