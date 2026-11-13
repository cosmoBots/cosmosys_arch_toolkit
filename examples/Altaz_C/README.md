# Altaz C — telescopio y observatorio de demostración

Ejemplo director del [Architecture Toolkit](../../README.md). Para preparar
otros modelos, empezar por [la guía Blender → GLB/YAML](../../docs/blender-to-glb-yaml.md).

Al preparar una copia con el toolkit, `annotate` normaliza automáticamente las
escalas si es necesario y verifica que conserva la geometría; no hay que activar
una opción para ello. La referencia original mantiene sus constraints y escenas.
Por defecto el toolkit crea/usa `csysArch` en la copia; para limitarse a una de
las escenas originales, indicar `--scene Observatory` o
`--scene "Telescope - inspect"`. Ver la guía para convertir constraints a drivers.
El toolkit respeta las raíces originales y no añade contenedores: exporta todas
las raíces de la escena por defecto, o el subárbol elegido con `--root`.

La única versión es la **cúpula con compuerta lateral**, con ranura de anchura
constante hasta más allá del cénit. La abertura triangular anterior se ha retirado.
Dimensiones y comprobación del haz en [OPTICAL_VALIDATION.md](OPTICAL_VALIDATION.md).

Modelo procedural original para aprender a importar arquitectura CAD y grados
de libertad en cosmoSys, y compartirlos con VRObjectGallery/Godot. No reproduce
un telescopio real ni contiene geometría, materiales o texturas del NRT o de
otros modelos. Es una maqueta cinemática didáctica: no un diseño constructivo,
óptico ni una simulación de colisiones.

## Abrir y orientarse

Abrir **Altaz_C.blend** en Blender 4.5 LTS o posterior. No hace falta activar
scripts automáticos, instalar complementos ni importar otros ficheros.

El archivo contiene dos escenas, seleccionables en la barra superior:

- **Telescope - inspect**: telescopio despejado para estudiar la horquilla.
- **Observatory**: el mismo telescopio con edificio, cúpula y compuerta.

Ambas escenas comparten los mismos objetos, no son copias del mecanismo.
El archivo arranca en Observatory con la compuerta seleccionada y cerrada. Sus límites
se muestran en el editor de propiedades. El texto **START_HERE.txt**, dentro
del archivo, recuerda las instrucciones básicas.

## Ensayar los cuatro movimientos

En el Outliner (árbol superior derecho), buscar `DOF_` y seleccionar el objeto
exacto de la tabla. Pulsar **N** sobre el visor 3D para abrir la barra lateral;
en **Item / Elemento → Transform**, escribir el giro o desplazamiento indicado.
Estos valores son LOCALES, no coordenadas mundiales.
La unidad de la interfaz puede aparecer como `°`; también se puede escribir
explícitamente `45deg`.

| Objeto/pivote | Escena | Eje en Blender | Prueba | Intervalo inicial |
| --- | --- | --- | --- | --- |
| `DOF_Azimuth` | Cualquiera | Z | 45° | −300° a 300° |
| `DOF_Elevation` | Cualquiera | X | 45° | 0° a 90° |
| `DOF_Dome_Azimuth` | Observatory | Z | 60° | −300° a 300° |
| `DOF_Shutter` | Observatory | Location X | 3,6 m | 0 a 3,6 m |

Volver a **0** devuelve cada articulación a su reposo. Azimuth arrastra la
horquilla, sus motores y la óptica completa. Elevación sólo arrastra el conjunto
óptico y los muñones móviles, no la horquilla ni sus carcasas. El giro de cúpula
arrastra la compuerta, pero no el telescopio ni el edificio fijo.

### Coordenadas mecánicas y astronómicas

La elevación CAD es **mecánica**: **0° = cénit**, **90° = horizonte**. Es una
posición real de reposo dentro del GLB, no una compensación añadida en el YAML.
El pivote permanece a cero; la orientación de reposo está en su conjunto óptico
hijo. Un marco fijo de la horquilla hace que el giro positivo se dirija a la
abertura frontal de la cúpula, sin cambiar los ejes locales de los controles.

Si PORIS usa elevación **astronómica** (0° horizonte, 90° cénit), la relación es:

```text
elevación_CAD = -1 × elevación_PORIS + 90
m = -1, h = 90
```

Ejemplos: PORIS 90° → CAD 0°; PORIS 60° → CAD 30°; PORIS 0° → CAD 90°.
Esto documenta una correspondencia para ensayar; no modifica las relaciones
existentes en la instancia cosmoSys ni introduce la conversión dentro del visor.

Para probar con el ratón también puede usarse **R**, después **X X** o **Z Z**
(dos pulsaciones eligen el eje local), mover y confirmar. **Esc** cancela.
Es más fácil empezar con los campos numéricos: son valores absolutos; el comando
R aplica incrementos a la pose actual. No aplicar transforms, cambiar el origen
ni separar los hijos: los pivotes son parte del mecanismo.

### Ver la óptica dentro de la cúpula

En Observatory, poner `DOF_Shutter` en **Location X = 3,6 m** para abrir. Para una
vista seccionada del interior, ocultar temporalmente `Building_front_panel`
desde el ojo del Outliner. Esto sólo es una ayuda de inspección: el GLB conserva
el edificio completo. La escena Telescope - inspect evita todo este obstáculo.

## Consultar y modificar los límites

Con el pivote seleccionado, abrir **Object Constraints / Restricciones de objeto**
en el editor de propiedades. Los giros usan **Limit Rotation** y la compuerta
usa **Limit Location**, ambas nativas de Blender:

- **Owner Space / Espacio**: Local.
- El eje móvil tiene un mínimo y máximo distintos.
- Los otros dos ejes están restringidos a 0° y bloqueados en la interfaz.
- **Affect Transform / Afectar transformación** está activado.

Ejemplo: cambiar el máximo X de `DOF_Elevation` a 70° y probar una elevación
de 80°. Probar también un ángulo negativo: debe limitarse al mínimo 0°.
Restaurar el máximo a 90° si se quiere volver a la configuración original.
La restricción recorta la pose evaluada: en ciertos métodos de introducción
numérica Blender puede conservar 80° en el campo aunque el modelo se vea a 70°.
No confundir el valor introducido con el resultado visual de la restricción.

El azimuth del telescopio exporta −300°…300° (600° entre extremos); el de la
cúpula también está ajustado a −300°…300°. Las matrices de Blender son **cíclicas**: una matriz
de rotación no distingue 205° de −155° ni cuenta vueltas de cable. Para probar
topes visuales inequívocos en Blender se puede reducir temporalmente su recorrido
a −90°…90°. No interpretar la restricción de Blender como un modelo de
enrollamiento ni como un bloqueo estricto del valor escrito en la interfaz.
El YAML sí conserva los intervalos numéricos y ModelControls rechaza 301°/−301°
para el telescopio.

## Anotaciones y exportación

La fuente de los límites y ejes es la restricción nativa, no un YAML mantenido
en paralelo. Las propiedades personalizadas de cada pivote añaden:

- `control_key`: clave estable de su control, independiente del nombre visible.
- `control_step_degrees`: paso del futuro slider, inicialmente 1°.
- `control_step_metres`: paso de la compuerta, inicialmente 0,05 m.
- `cosmosys_controls`: instantánea de exportación, **derivada** de los campos
  anteriores y de la restricción. No editar manualmente sus límites.

Para regenerar GLB y YAML después de guardar cambios en Blender, desde la raíz
del toolkit (no reconstruye el modelo ni sobrescribe el `.blend`):

```sh
./toolkit export examples/Altaz_C/Altaz_C.blend --scene Observatory --root Observatory_Root
```

Configurar las rutas locales en `.env`, copiando `.env.example`; `./toolkit doctor`
comprueba Python, Blender y glTF. Cada exportación sustituye los resultados en
`modelos/Altaz_C/2_export/`, con GLB/YAML, informe y log. No reemplaza los derivados
versionados del ejemplo. Para experimentar, usar `./toolkit init mi-modelo --from
examples/Altaz_C/Altaz_C.blend` y abrir `modelos/mi-modelo/1_blender/mi-modelo.blend`.

El `.blend` de referencia conserva un texto histórico `export_altaz_c.py`:
**no usarlo**, queda sustituido por el comando común. Las instrucciones antiguas
de exportación en `START_HERE.txt` tampoco son el flujo vigente; los movimientos
siguen siendo los descritos arriba. La herramienta nunca ejecuta textos del modelo.
Exporta los cuatro pivotes a cero, restaura la pose de inspección en memoria y
no guarda ni cambia metadatos en el `.blend` de entrada.

La vertical de Blender es Z; la del GLB es Y. El exportador convierte los ejes:
Z→Y, X→X y Y→−Z (invirtiendo los límites cuando procede). El YAML y los metadatos
GLB ya están en coordenadas glTF; no volver a convertirlos en el consumidor.
Los límites del exportador se redondean a cuatro decimales
de grado, evitando los residuos de precisión de los radianes de Blender.

Cada nodo articulado contiene `extras.cosmosys_controls`, con una entrada igual
a la definición de `controls` del YAML. `Observatory_Root` incluye la versión
del pequeño contrato (`cosmosys_model`, versión 1). No son una extensión oficial
glTF ni una funcionalidad ya instalada en los lectores de cosmoSys/Godot.

Esta demo entrega ambas representaciones. Architecture en desarrollo ya puede
leer el contrato embebido sin YAML; comprobar la versión instalada. En otros
consumidores, como VRObjectGallery, no asumir esa capacidad hasta adaptarlos.
Las restricciones y scripts
de Blender no se ejecutan dentro del GLB: sólo viajan geometría, jerarquía y datos.

## Reproducir y validar

Desde un proceso independiente (reinicia su escena de Blender, no usar sobre un
trabajo sin guardar):

```sh
blender --background --factory-startup --disable-autoexec -noaudio --python-exit-code 1 \
  --python tools/examples/altaz_c/build.py -- --output modelos/reconstruccion --no-render
```

Los comandos de esta sección se ejecutan desde la raíz del toolkit. El conjunto
vive en `examples/Altaz_C`, separado de los plugins y de los modelos de terceros.
Se conservan el `.blend`, el GLB, el YAML, dos previsualizaciones PNG y
`validation.json` con las comprobaciones cinemáticas y ópticas en el ejemplo;
el generador y las pruebas específicos están en `tools/examples/altaz_c/`.
La exportación no incluye cámaras, luces ni animaciones de demostración.
**Reconstruir es distinto de exportar**: el generador crea un `.blend` nuevo con
la geometría procedural y recalcula la validación. La carpeta `--output` no debe
existir. `--no-render` omite los renders; quitar esa opción para producirlos.
`_build_base.py` es un auxiliar interno: genera un andamio temporal que el
generador completa, no otra alternativa de observatorio.
`./toolkit export` conserva tus ediciones, pero no recalcula `validation.json` ni las
previsualizaciones: los ensayos ópticos documentados corresponden a la geometría
procedural validada, no automáticamente a futuras modificaciones manuales.

Comprobar estructura, referencias y coincidencia GLB/YAML (Node.js y Ruby,
sin Redmine, plugins ni paquetes npm):

```sh
node tools/examples/altaz_c/verify_glb.mjs
```

El verificador conserva los recorridos esperados de esta demo. Si se cambia su
estructura o esos límites, adaptar las aserciones antes de usarlo como prueba.

Para reabrir el .blend y verificar límites y exportador (requiere Blender):

```sh
blender --background --disable-autoexec -noaudio examples/Altaz_C/Altaz_C.blend --python-exit-code 1 \
  --python tools/examples/altaz_c/verify_blend.py
```

En este equipo usar el Blender existente:
`/home/txinto/soft/blender-5.2.3-linux-x64/blender` (Blender 5.2.3 LTS).
Si no está en PATH, sustituir `blender` por ese ejecutable en los ejemplos.
El exportador y las pruebas sólo deben ejecutarse sobre ficheros de confianza.
Deshabilitar scripts automáticos no convierte Blender en un sandbox.

## Licencia

Modelo procedural, scripts y documentación bajo GPL-3.0; véase
[LICENSE](../../LICENSE). La geometría es original, sin mallas NRT ni de terceros.
