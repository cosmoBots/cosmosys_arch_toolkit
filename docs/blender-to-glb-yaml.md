# De Blender a GLB y YAML: autoría con Altaz_C

Esta guía explica cómo construir un modelo articulado usando Altaz_C como
ejemplo director. La geometría y las restricciones se editan en Blender; el
YAML se deriva de ellas, no se mantiene a mano como una segunda fuente.

El toolkit se usa localmente y es independiente de Redmine. Su exportador
común admite modelos que cumplan el contrato de esta guía, sin nombres fijados
a Altaz_C. No convierte automáticamente cualquier mecanismo de Blender.

Hay dos modos de autoría. La demo Altaz_C de referencia conserva constraints
nativas y sigue siendo válida; las secciones de creación manual de constraints
describen ese modo. Ahora `annotate` usa **drivers por defecto**, sin constraints:
`control_definition` contiene la definición exportable glTF y `control_value`
es el valor de ensayo (grados/metros del YAML). Para crear constraints, añadir
`--constraints`. Ambos modos producen el mismo contrato GLB/YAML.

Para ensayar un driver, seleccionar el objeto y abrir **Object Properties →
Custom Properties → control_value**. No editar la rotación morada conducida por
el driver. El campo conserva el ángulo acumulado y el driver lo acota al rango,
también por encima de una vuelta. El exportador ignora la pose de ensayo,
exporta a cero y la restaura. La autoridad es `control_definition`, no la fórmula
del driver ni sus preferencias de presentación; si se editan por separado,
mantenerlos alineados es responsabilidad del autor. Drivers ajenos no se aceptan.

## 1. Abrir el ejemplo y conservar la fuente

Abrir [Altaz_C.blend](../examples/Altaz_C/Altaz_C.blend) con Blender 4.5 LTS
o posterior. En este workspace se usa Blender 5.2.3 de `~/soft`.
No hace falta habilitar la ejecución automática de scripts del fichero.

Desde la raíz del toolkit, copiar `.env.example` a `.env`, ajustar las rutas
de Python/Blender si es necesario y ejecutar `./toolkit doctor`.
La configuración local y `modelos/` están ignorados por Git. No se ejecuta
`.env` con `source`; sólo admite los valores literales de su plantilla.

```sh
./toolkit init mi-observatorio --from examples/Altaz_C/Altaz_C.blend
```

Trabajar sobre la copia en `modelos/mi-observatorio/1_blender/`. El `.blend` es la fuente
editable; GLB y YAML son productos de exportación. Guardar el `.blend` antes
de exportarlo desde consola: el proceso sólo leerá lo guardado en disco.

La escena `Observatory` contiene el observatorio completo; `Telescope - inspect`
permite inspeccionar el telescopio sin el edificio. Comparten los objetos.
Por defecto el toolkit usa `csysArch`. Si falta, la crea enlazando todos los
objetos existentes y copiando las unidades de la escena activa, sin modificar
las escenas originales. Si ya existe, respeta su contenido; el usuario mantiene
los objetos que contiene. Para seleccionar sólo una escena original, usar
`--scene Observatory` o `--scene "Telescope - inspect"` explícitamente.
Los drivers y controles se comparten porque pertenecen a los mismos objetos.
`annotate` guarda la escena creada en su Blender de salida; `check` y `export`
no guardan cambios en el `.blend` de entrada.

## 2. Organizar los pivotes y la jerarquía

Un grado de libertad necesita un objeto que actúe como pivote o articulación.
Puede ser un Empty. Su origen define el centro del giro y sus ejes locales
definen la dirección del movimiento. Toda la geometría que deba acompañarlo
debe quedar dentro de su subárbol.

En el ejemplo:

```text
Observatory_Root
├── …telescopio fijo…
│   └── DOF_Azimuth
│       └── Fork_Assembly
│           └── DOF_Elevation
│               └── Optical_Assembly
└── …edificio fijo…
    └── DOF_Dome_Azimuth
        └── DOF_Shutter
```

Es un esquema de los elementos relevantes, no el árbol completo. El azimuth
mueve horquilla y óptica; la elevación sólo mueve la óptica y sus piezas
solidarias. La cúpula es independiente del telescopio y arrastra la compuerta.

Para adaptar geometría propia:

- Situar el pivote en el eje mecánico y orientar sus ejes antes de articular.
- Emparentar las piezas conservando inicialmente su transformación mundial;
  ensayar después que giran alrededor del eje deseado.
- Colocar los siguientes pivotes como descendientes cuando sus movimientos
  deban acumularse. No emparentar el edificio fijo bajo el azimuth del telescopio.
- Mantener nombres únicos: el YAML actual identifica los objetivos por nombre.
- No aplicar transformaciones ni recolocar orígenes después de configurar los
  pivotes sin revisar de nuevo el movimiento y la exportación.

Usar metros, con `Scene → Units → Metric` y escala de unidad 1. Aplicar la escala
de todos los objetos exportables (1,1,1). Se admiten MESH y EMPTY bajo una raíz
sin padre, sin instancias (convertirlas a objetos reales). Cámaras y luces no se
exportan ni deben ser padres de geometría exportable. Incluir las colecciones en la capa
activa; los objetos ocultos del subárbol también se incluyen, con un aviso.
Se rechazan animaciones/drivers ajenos al toolkit, shape keys y constraints activas
sin un control válido; no se hornean mecanismos arbitrarios silenciosamente.

## 3. Añadir las restricciones (modo constraints)

Seleccionar el pivote y abrir `Object Constraints / Restricciones de objeto`.
El subconjunto usado por el exportador es:

- Un único `Limit Rotation` para giro, o un único `Limit Location` para traslación.
- `Owner Space: Local`.
- También se admite `World` para controles globales a reposo cero con ancestros
  fijos alineados con el mundo. No equivale a convertir cualquier jerarquía local
  a coordenadas mundiales; los casos no soportados se rechazan.
- Influencia 1 y rotación Euler XYZ, sin transformaciones delta del pivote.
- Límites habilitados en los tres ejes; sólo un eje con mínimo menor que máximo.
- Los otros dos ejes fijados a cero. En traslación, habilitar mínimo y máximo.
- Cero incluido en el intervalo del eje móvil: es la posición de reposo exportada.
- Activar `Affect Transform` para ensayar con las herramientas de Blender.

El bloqueo de ejes en Transform facilita la edición, pero **no sustituye la
constraint**. El exportador lee los límites de la constraint, no los candados.

| Pivote del ejemplo | Restricción | Eje local Blender | Límites |
| --- | --- | --- | --- |
| `DOF_Azimuth` | Limit Rotation | Z | −300°…300° |
| `DOF_Elevation` | Limit Rotation | X | 0°…90° |
| `DOF_Dome_Azimuth` | Limit Rotation | Z | −300°…300° |
| `DOF_Shutter` | Limit Location | X | 0…3,6 m |

No se exporta la ejecución de constraints, drivers, IK ni mecanismos acoplados.
Si hacen falta movimientos independientes en varios ejes, usar pivotes separados
y volver a validar la jerarquía; no ampliar silenciosamente este contrato.

## 4. Añadir las propiedades del control

En `Object Properties → Custom Properties`, cada pivote articulado del ejemplo
tiene:

- `control_key`: texto, identificador único y estable, como `azimuth`.
- `control_step_degrees`: número positivo para giros, por ejemplo 1.
- `control_step_metres`: número positivo para traslaciones, por ejemplo 0.05.

Sólo se necesita la propiedad de paso correspondiente al movimiento. En el
exportador `control_key` identifica los pivotes dentro del subárbol seleccionado.
Su valor no debe repetirse. `cosmosys_controls` es una instantánea derivada:
no editar sus límites manualmente; se recalcula en el GLB al exportar.

Se exportan la raíz y su subárbol completo. No se exige `demo_model` ni se usa
la selección manual de Blender. Elegir `--root NOMBRE` si hay varias raíces;
se reconoce una raíz anotada con `cosmosys_model` cuando es única. También
se admiten modelos estáticos sin controles, con un aviso en el informe.

## 5. Ensayar y guardar

Abrir `N → Item / Elemento → Transform` y escribir valores locales de prueba.
Empezar por 0, un valor intermedio y los extremos. Comprobar:

- que se mueve la pieza esperada y sus descendientes, no los otros conjuntos;
- que el centro del giro y el signo son correctos;
- que el reposo es realmente el deseado y no una compensación del YAML;
- que no hay geometría suelta o extraordinariamente alejada del conjunto.

En Altaz_C, elevación mecánica 0° mira al cénit y 90° al horizonte. Para una
elevación astronómica, la conversión posterior sería `CAD = -PORIS + 90`.
No incorporarla además en el modelo si se quiere demostrar esa conversión.

Las matrices de rotación son cíclicas. Los límites −300°…300° no son un
contador de vueltas de cable; Blender puede conservar un valor escrito fuera
del límite aunque represente una pose limitada. Véanse las advertencias del
[ejemplo](../examples/Altaz_C/README.md#consultar-y-modificar-los-límites).

Guardar el `.blend` antes del siguiente paso.

## 6. Validar y exportar

Desde la raíz de este toolkit:

```sh
./toolkit check modelos/mi-observatorio/1_blender/mi-observatorio.blend --scene Observatory --root Observatory_Root
./toolkit export modelos/mi-observatorio/1_blender/mi-observatorio.blend --scene Observatory --root Observatory_Root
```

Para elegir el Blender instalado:

```sh
./toolkit doctor --blender /ruta/al/blender
```

Cada exportación escribe `informe.json` y `export-conversion.log` en la carpeta fija
`modelos/mi-observatorio/2_export/`. Sólo `export` añade GLB/YAML, después de
superar el preflight. Un fallo devuelve código 1 y deja sus diagnósticos; no usar
resultados de una ejecución marcada `failed`. `--timeout` limita el proceso
(120 s por defecto). No se modifica el `.blend`, ni se recalculan óptica o renders.

El nombre de salida toma el del `.blend`; `--name NOMBRE` cambia tanto el nombre
del GLB como su clave YAML. `--output-dir RUTA` permite elegir otra carpeta de
destino. Los resultados anteriores se sustituyen, sin histórico. `check` guarda
su propio informe/log y no sustituye el informe de exportación. Consultar el
README para las rutas configurables en `.env`.

La exportación pone los pivotes a cero y restaura su pose de inspección en
memoria. No se ejecutan los textos incorporados al `.blend`. El texto histórico
`export_altaz_c.py` de la demo queda retirado: usar siempre el comando común.

**Exportar y reconstruir no son lo mismo:** `tools/examples/altaz_c/build.py`
recrea la maqueta procedural en una carpeta nueva elegida mediante `--output`.
No usarlo para exportar ediciones manuales que se quieran conservar.

## 7. Revisar los dos resultados

El GLB contiene geometría, nombres, jerarquía y anotaciones en
`extras.cosmosys_controls`. El YAML contiene las mismas definiciones bajo
`models → Altaz_C.glb → controls`. Conservar ambos ficheros juntos.

Blender usa Z vertical; glTF usa Y vertical. El exportador convierte:

| Blender | GLB/YAML |
| --- | --- |
| X | X |
| Y | −Z |
| Z | Y |

Los giros pasan de radianes internos a grados; las traslaciones se expresan en
metros. Los intervalos se invierten cuando cambia el signo del eje. No volver
a convertir los ejes en el consumidor. Comprobar las poses si se cambian los
marcos de referencia o la jerarquía de los pivotes.

Validar una ejecución sin volver a arrancar Blender:

```sh
./toolkit verify modelos/mi-observatorio/2_export
```

Comprueba hashes e igualdad GLB/YAML. El YAML se compara con la representación
canónica del exportador: no es un parser de YAML arbitrario. Para cambiar límites,
editar el Blender y repetir la exportación, sustituyendo los mismos ficheros.

Comprobación estructural opcional, con Node.js y Ruby para leer YAML:

```sh
node tools/examples/altaz_c/verify_glb.mjs
```

Este verificador comprueba la demo de referencia, incluidos sus cuatro
controles y recorridos esperados. Si se cambian esos recorridos o la estructura,
hay que adaptar sus aserciones; la validación genérica es `check`/`verify`.

Las anotaciones no convierten el GLB en un programa ejecutable. El consumidor
debe implementar el contrato para leer controles desde `extras`. El desarrollo
actual de Architecture incorpora esa lectura; no implica que esté desplegada en
una instancia ni que todos los lectores Godot la implementen. Este toolkit no
carga nada en Redmine.

## 8. Pasar a un modelo propio

Crear el cajón con `./toolkit init mi-modelo`, poner el `.blend` y sus recursos
en `modelos/mi-modelo/1_blender/` y aplicar los mismos pasos. No hay que editar los
scripts ni renombrar los objetos como en Altaz_C. `check` indica los problemas
que impiden exportar; el informe incluye inventario, controles y dimensiones
calculadas con los vértices evaluados a reposo cero (ejes Blender, en metros).
Esto ayuda a detectar geometría lejana, pero no certifica apertura óptica,
colisiones ni corrección mecánica. No se copian automáticamente dependencias
externas: empaquetar las texturas en Blender o conservar rutas accesibles.

Los [servicios remotos y la distribución futura](roadmap.md) siguen fuera de
esta etapa. Abrir sólo modelos de confianza: desactivar autoexec no es aislamiento.

## 9. Aprovechar un YAML existente o empezar desde un GLB

El comando `annotate` evita introducir a mano los controles descritos en un
YAML. Si ya se tiene un `.blend`, no hace falta importarlo primero:

```sh
./toolkit annotate modelos/mi-modelo/1_blender/modelo.blend \
  --controls modelos/mi-modelo/0_import/modelo.yaml
```

Se sustituye el `.blend` de trabajo sólo después de validar la anotación. No hay
histórico automático: guardar las copias necesarias antes de ejecutar.
Se mantienen las raíces originales de la escena, sin crear un Empty agrupador.
Por defecto se procesan todas las raíces con mallas; `--root` permite elegir
un único subárbol. El contrato embebido se guarda en una de las raíces existentes,
sin añadir otro nodo ni cambiar su jerarquía. La normalización de escalas es
automática y obligatoria en `annotate`: compara todos los vértices antes/después
con tolerancia de 0,00001 m y conserva el fichero anterior si falla. No se usa
`--apply-scale`. Se admiten escalas positivas finitas en mallas/Empties estáticos;
se rechazan escalas nulas/negativas y normalizaciones de rigs, instancias,
modificadores, shape keys o datos enlazados que no podemos garantizar.
Sólo se preparan los subárboles elegidos y todos los controles deben pertenecer a ellos.
Por defecto no reemplaza constraints, animaciones ni controles.
Para actualizar límites/ejes de un control ya anotado, conservar su clave/objeto
y usar `--update-existing`. Las escalas se comprueban
en cada anotación y sólo se normalizan si hace falta:

```sh
./toolkit annotate modelos/NRT/1_blender/NRT.blend \
  --controls modelos/NRT/0_import/NRT.yaml --update-existing
./toolkit export modelos/NRT/1_blender/NRT.blend
```

Reconoce drivers del toolkit y constraints válidas `Control: <clave>`; permite
convertir entre los dos modos, añadiendo `--constraints` si se desea ese modo.
No borra rigs ajenos ni controles omitidos. Editar el YAML de `0_import`, no el
generado en `2_export`, o la definición de autoría directamente en Blender.
Los candados del objeto dejan libre sólo el eje de rotación/traslación definido;
los demás canales y la escala quedan bloqueados. Los candados ayudan a editar;
los límites los aplica el driver, o la constraint si se eligió ese modo.
El nombre del bloque `models` puede ser antiguo: con uno solo se
selecciona ese bloque, con varios hay que indicar `--model-key`.

El YAML de entrada usa ejes glTF. Para generar las constraints se hace la
conversión inversa: X→X, Y→Z y Z→−Y, incluyendo signos de límites. Los pivotes
deben estar a reposo cero; un giro almacenado como quaternion identidad se pasa
a presentación Euler XYZ en la copia. En modo driver, una traslación parte de
la posición de montaje almacenada en `control_rest_position`; el valor del
control es cero en reposo, no la coordenada de montaje. En modo constraints
se sigue requiriendo un pivote de posición cero.
`translation` y `rotation_degrees` de modelo se conservan sólo como preferencias
de presentación de galería: no se aplican a las coordenadas Blender. Se exportan
en el YAML y como `cosmosys_model.presentation` del GLB. No hay doble aplicación.
`round_decimals` se conserva como precisión numérica de VR_ObjectGallery/MQTT;
no redondea la geometría ni el movimiento normalizado, ni sustituye `step`.
Transforms por nodo y campos desconocidos se rechazan explícitamente.
`annotate` necesita PyYAML en el Python del toolkit; el resto del flujo no.

Para empezar con STEP, convertir manualmente con CAD Assistant a GLB, revisar
nombres, ensamblaje, unidades y geometría, y colocar ese GLB en `0_import`.
El toolkit no incorpora ahora conversión STEP automática ni otra dependencia.

Para partir de GLB/glTF, OBJ, STL, PLY o FBX:

```sh
./toolkit import /ruta/modelo.glb --name modelo
```

El importador debe estar disponible en Blender. A continuación usar el `.blend`
creado como entrada de `annotate`; exportar la copia anotada con `export`.
Consultar [el flujo completo](../README.md#partir-de-un-modelo-de-intercambio-y-un-yaml).
Los formatos sin unidades garantizadas deben revisarse e importarse con el
factor `--scale` apropiado. No se admite STEP ni se reconstruye historia CAD.

## 10. Preparar subconjuntos y futuras preferencias de importación

Para que un subconjunto sea reconocible, darle una raíz clara en el árbol de
objetos: puede ser una pieza que ya actúe como raíz o un Empty con un nombre
descriptivo. Sus piezas deben ser descendientes de ese objeto. Al emparentar,
conservar las transformaciones mundiales y comprobar que no cambian las poses
ni los pivotes. Una Collection sirve para organizar Blender, pero no equivale
por sí sola a un nodo padre del GLB.

**Disponible ahora:** las propiedades `control_key` y los pasos, descritas
arriba, se editan en Object Properties → Custom Properties y se exportan junto
con las constraints admitidas. No hacen atómico un conjunto.

**Pendiente:** la preferencia de importación atómica. Cuando se implemente,
la guía mostrará cómo seleccionar esa raíz en el Outliner, marcar su política
en las propiedades y verificar en el preflight de Architecture que se propone
un único ítem conservando toda la geometría descendiente. Hasta entonces no hay
una propiedad `atomic` soportada por el toolkit/importador; no basta con crear
manualmente una propiedad con ese nombre.

La futura guía incluirá un ejemplo sin controles y otro con grados de libertad
internos: no se esconderán controles simplemente por declarar atómico un
subárbol. Véase [el alcance pendiente](roadmap.md#exportación-ligera-y-preferencias-de-importación).
