# cosmoSys Architecture Toolkit

Companion de autoría CAD: documentación, modelos de ejemplo y herramientas
locales para preparar modelos Blender y exportarlos como GLB + YAML.

**Experimental.** Repositorio independiente, integrado en `csys` como submódulo.
No es un plugin Redmine ni un servicio desplegable. No se instala en Redmine,
no modifica su base de datos y no cambia sus opciones de deploy.

## Empezar

Puede clonarse sin el workspace privado de desarrollo:

```sh
git clone git@github.com:cosmoBots/cosmosys_arch_toolkit.git
cd cosmosys_arch_toolkit
```

Desde esta carpeta, sin instalar ni activar nada:

```sh
cp .env.example .env
# Editar .env con las rutas locales; nunca ejecutarlo con source.
./toolkit doctor
./toolkit init mi-observatorio --from examples/Altaz_C/Altaz_C.blend
./toolkit check modelos/mi-observatorio/1_blender/mi-observatorio.blend
./toolkit export modelos/mi-observatorio/1_blender/mi-observatorio.blend
./toolkit verify modelos/mi-observatorio/2_export
```

Abrir la copia de `1_blender/` para editar; guardar antes de `check` o `export`.
`mi-observatorio` es el nombre de tu carpeta y de sus archivos, no una escena
Blender. Por defecto se usa `csysArch`: si falta, se crea enlazando todos los
objetos del archivo, sin moverlos de las escenas originales ni duplicarlos.
Se copian las unidades de la escena activa. Si ya existe, se respeta exactamente
su contenido; añadir objetos nuevos o retirar variantes es responsabilidad del
usuario. Los objetos, drivers y constraints son compartidos entre escenas.
`--scene Nombre` selecciona explícitamente otra escena existente y evita crear
`csysArch`. Por defecto se procesan todas las raíces con mallas de la escena,
sin añadir un agrupador. `--root Nombre` limita el modelo a un único subárbol.
`Observatory` es sólo el nombre de la escena original de la demo Altaz_C.
Leer [la guía Blender → GLB/YAML](docs/blender-to-glb-yaml.md) y
[las instrucciones de Altaz_C](examples/Altaz_C/README.md) para ensayar los movimientos.

Requiere Python 3.10+ y Blender 4.5+ con exportador glTF. `doctor` los comprueba
y ofrece indicaciones si faltan; no instala dependencias automáticamente.
No necesita Redmine, Ruby, Node ni paquetes pip para el flujo normal.
El comando opcional `annotate` necesita PyYAML en el Python del toolkit
(en Debian/Ubuntu, paquete `python3-yaml`). Si falta, indica cómo localizarlo;
no se instala nada automáticamente ni se necesita PyYAML dentro de Blender.

## Partir de un modelo de intercambio y un YAML

```sh
./toolkit init modelo
# Depositar modelo.glb y modelo.yaml en modelos/modelo/0_import/.
./toolkit import modelos/modelo/0_import/modelo.glb
./toolkit annotate modelos/modelo/1_blender/modelo.blend \
  --controls modelos/modelo/0_import/modelo.yaml
# Abrir el .blend y ajustar control_value en las propiedades personalizadas.
./toolkit export modelos/modelo/1_blender/modelo.blend --name modelo
```

`import` admite GLB/glTF, OBJ, STL, PLY y FBX si su importador está disponible
en Blender. Para STEP, convertir primero a GLB con CAD Assistant y supervisar
la conversión; depositar el GLB revisado en `0_import`. No se integra ningún
conversor STEP en el toolkit. OBJ/STL/PLY no
garantizan unidades: verificar dimensiones e indicar `--scale` cuando proceda.
La importación conserva la geometría y los datos que entienda Blender, no una
historia paramétrica CAD ni todos los atributos de cualquier formato.

`annotate` crea por defecto una propiedad numérica `control_value` y un driver,
con la definición exportable en `control_definition` (coordenadas glTF).
Para ensayar: seleccionar el objeto, abrir **Object Properties → Custom
Properties** y cambiar `control_value` (grados o metros del YAML). Los límites
del campo y del driver acotan el movimiento; un giro conserva sus vueltas.
La sensibilidad del arrastre se ajusta al recorrido del control; es una
preferencia de edición de Blender, independiente del `step` exportado.
La definición exportable son los metadatos, no la posición de ensayo. Para el
mecanismo anterior, usar `--constraints`: genera únicamente constraints nativas,
cuyos límites/ejes vuelven a ser la fuente de exportación. No mezclar ambos.
El nombre antiguo del GLB dentro del YAML sirve para elegir el bloque, no para
buscar la geometría: con un único bloque se selecciona automáticamente; con
varios, usar `--model-key`. Exige objetos con nombres resolubles, un control por
objeto y rotación de reposo cero. Para reaplicar cambios del YAML, usar
`--update-existing`: sólo sustituye controles del toolkit con la misma clave y
objeto y un driver reconocido o una única constraint válida `Control: <clave>`.
Permite pasar de un modo al otro. Rechaza rigs ajenos; no elimina controles
omitidos ni reasigna controles entre objetos. También reconoce las constraints
de la demo Altaz_C original al actualizarla.
El anotador también cierra los candados de posición, rotación y escala que no
corresponden al grado de libertad, dejando libre sólo su eje de movimiento.
El toolkit no añade nodos agrupadores: Blender y GLB pueden tener varias raíces.
El contrato se anota en una raíz existente, sin modificar su jerarquía.
`annotate` normaliza automáticamente las
escalas del subárbol elegido, en la copia temporal, comprobando que no se
desplacen sus vértices más de 0,00001 m. No hay opción `--apply-scale`:
este paso es obligatorio cuando se necesita y no modifica nada si las escalas
ya son unitarias. Se rechazan escalas nulas, negativas o no finitas. Si hay que
normalizar un conjunto con animación ajena, constraints no reconocidas,
modificadores, shape keys, instancias o datos enlazados, se rechaza: no se
intenta convertir un rig arbitrario. Los controles reconocidos se retiran
antes de normalizar y se reconstruyen después. Un fallo conserva el Blender
anterior. `check` y `export` son de sólo lectura y exigen la preparación previa.
Los giros globales sólo se admiten con ancestros fijos alineados con el mundo.
No convierte automáticamente compensaciones de pose ni mecanismos arbitrarios.

`round_decimals` se conserva para consumidores como VR_ObjectGallery: allí
redondea comandos MQTT absolutos/incrementales y respuestas de posición, no
movimiento normalizado. En Blender sólo ajusta la precisión visual del campo
(hasta seis decimales), no redondea el driver ni sustituye `step`.

Las opciones de modelo `translation` y `rotation_degrees` son colocación de
galería: se conservan en el YAML y en `cosmosys_model.presentation` del GLB,
pero no transforman objetos, geometría ni pivotes de Blender. Cada control usa
offset cero como reposo, conservando la posición de montaje de la pieza.
Las traslaciones con montaje no nulo requieren modo driver; el modo constraints
sigue exigiendo un pivote con posición cero.

BancoIFU tiene su GLB enriquecido en `modelos/BancoIFU/2_export/`. Para importarlo
en Architecture, elegir **sin YAML**: el sidecar conserva opciones de galería VR
que el importador actual no combina con un GLB ya anotado. No se ha aplicado
ningún filtro ni eliminado tornillos.

Importar un GLB no reconstruye por sí solo los controles Blender desde sus
extras: en este flujo se crean explícitamente con `annotate` y el YAML.

## Configuración local

[.env.example](.env.example) es la plantilla versionada; `.env` está ignorado.
Admite `PYTHON_BIN`, `BLENDER_BIN`, `TOOLKIT_MODELOS_DIR` y `TOOLKIT_OUTPUT_DIR`.
Sólo se leen valores literales `CLAVE=valor`: no ejecuta shell ni expande `$VAR`
o comandos. Se admiten comillas envolventes; usar rutas absolutas de ejecutables.
Las carpetas relativas se resuelven desde el toolkit, no desde el directorio actual.

Prioridad: opciones (`--blender`, `--output-dir`) > entorno del proceso > `.env`
> valores por defecto. Python usa `python3` si no se configura; Blender se busca
en PATH y después en `~/soft/blender*/blender`. `doctor` muestra las rutas efectivas.
Si se cambia la carpeta de modelos, las rutas de entrada de los comandos también
deben apuntar a ella. Las rutas de entrada y `--output-dir` son relativas al
directorio desde el que se invoca el comando.

## Contenido

- `docs/`: guía de autoría y [alcance futuro](docs/roadmap.md).
- `toolkit`: entrada común (`--help` y `<comando> --help`): doctor, init,
  import, annotate, check, export y verify.
- `tools/blender/`: preflight y exportador genéricos, sin nombres de la demo.
- `tools/examples/altaz_c/`: generador y regresiones específicos del ejemplo.
- `examples/Altaz_C/`: fuente `.blend`, GLB/YAML de referencia e imágenes/documentación.
- `modelos/<proyecto>/0_import/`: formatos de entrada y YAML previo, si existen.
- `modelos/<proyecto>/1_blender/`: `.blend` de trabajo y controles anotados.
- `modelos/<proyecto>/2_export/`: GLB enriquecido, YAML generado e informes.
- `tests/`: pruebas del entorno y del contrato de exportación.

`modelos/` se crea al clonar el toolkit gracias a `.gitkeep`; su contenido, excepto
ese marcador, queda fuera del Git del toolkit mediante el `.gitignore` de su raíz
del toolkit. No hay `.gitignore` dentro: puedes ejecutar `git init` en `modelos/`
para versionar allí tus entradas, Blender y exportaciones de forma independiente.
Cada ejecución sustituye los mismos resultados, sin carpetas de timestamps ni
histórico. `import` y `annotate` escriben en `1_blender`; `export` y `check`, en
`2_export`. La anotación puede sustituir el propio `.blend` de trabajo después
de validarlo; para controles ya anotados, indicar `--update-existing`. `0_import`
no se modifica. Una operación fallida conserva los modelos anteriores, pero
actualiza su informe/log: no confundir esos modelos con resultados nuevos.
`check` genera sólo `check-informe.json` y su log. Export guarda `informe.json`
y `export-conversion.log`; import/annotate usan su propio prefijo.
Si se configura `TOOLKIT_OUTPUT_DIR`, usa `<ruta>/<proyecto>/<etapa>`;
`--output-dir` selecciona directamente la carpeta destino.
Las copias/versionado son responsabilidad del usuario. Las rutas externas configuradas
no quedan protegidas por este `.gitignore`: elegir una carpeta privada adecuada.

`verify` comprueba hashes e igualdad entre los controles GLB y el YAML canónico
generado por el toolkit; no importa ni valida YAML arbitrario escrito a mano.
Para limitarse a una raíz, usar `--root`; para otra escena, usar `--scene`.
Los modelos deben
cumplir [el subconjunto de autoría admitido](docs/blender-to-glb-yaml.md).

## Comprobaciones

Desde esta carpeta:

```sh
python3 -m unittest discover -s tests -v
blender --background --factory-startup --disable-autoexec -noaudio --python-exit-code 1 --python tests/blender_contract.py
blender --background --factory-startup --disable-autoexec -noaudio --python-exit-code 1 --python tests/blender_annotation.py
blender --background --factory-startup --disable-autoexec -noaudio --python-exit-code 1 --python tests/blender_drivers.py
blender --background --factory-startup --disable-autoexec -noaudio --python-exit-code 1 --python tests/blender_import.py
blender --background --factory-startup --disable-autoexec -noaudio --python-exit-code 1 --python tests/blender_scenes.py
blender --background --factory-startup --disable-autoexec -noaudio --python-exit-code 1 --python tests/blender_scales.py
blender --background --factory-startup --disable-autoexec -noaudio --python-exit-code 1 --python tests/blender_multi_root.py
```

En el segundo comando sustituir `blender` por el ejecutable local si no está
en PATH. Las pruebas usan temporales, no modifican los modelos del usuario.

## Uso independiente

Los scripts se ejecutan con el Blender del usuario y sólo deben utilizarse con
modelos de confianza. No son un sandbox para abrir archivos ajenos. No hay API
HTTP, Dockerfile, arranque de contenedores ni procesamiento de subidas.

El resultado es un par de ficheros de intercambio. La eventual carga en una
aplicación es manual y ajena al toolkit. Las anotaciones en `extras` son
experimentales; cada consumidor debe soportar explícitamente ese contrato.

## Licencia y procedencia

Código, documentación y modelo procedural Altaz_C bajo GPL-3.0; véase
[LICENSE](LICENSE). Se conserva el generador como fuente editable del ejemplo.
Altaz_C es una maqueta original creada para estas demostraciones: no incorpora
geometría NRT ni mallas de los observatorios usados como referencias visuales.
No se han trasladado aquí modelos de terceros.
