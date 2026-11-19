# Filtrar antes de trabajar en Blender

Coloca `filters.csv` junto al fichero de `0_import`: `toolkit import` lo lee
automáticamente. `--filters ruta.csv` permite elegir otro. Perfiles editables:
[example1.csv](../examples/filters/example1.csv) y
[example2.csv](../examples/filters/example2.csv).

```csv
search,pattern,action
text,iston,exclude
text,vastago,exclude
regex,^Conjunto_,atomic
text,Conjunto_especial,include
```

- `text`: fragmento del nombre, sin distinguir mayúsculas.
- `regex`: expresión regular Python, sin distinguir mayúsculas. Los perfiles
  suministrados también son compatibles con el preflight web.
- `exclude`: borra el objeto y sus descendientes del Blender generado.
- `atomic`: conserva su geometría y propone un solo ítem en Architecture.
- `include`: excepción que conserva el objeto y retira una preferencia atómica
  anterior. La última regla coincidente decide la política de cada objeto.

Excluir un padre excluye todo su subárbol, incluso si un hijo coincide con una
excepción. Para conservar ese hijo hay que conservar también sus ancestros.
Atómico no elimina los hijos geométricos. Se busca por **nombre importado en
Blender**, no por ruta; Blender puede añadir sufijos para nombres repetidos.
Patrones de hasta 256 caracteres; su ejecución queda acotada por `--timeout`.

## Revisar y aplicar

Desde la raíz del toolkit:

```sh
./toolkit import modelos/BancoIFU/0_import/BancoIFU.glb --preflight --timeout 300
# Revisa modelos/BancoIFU/1_blender/import-informe.json
./toolkit import modelos/BancoIFU/0_import/BancoIFU.glb --timeout 300
```

El preflight importa en memoria y escribe sólo informe y log: no guarda ni
sustituye el `.blend`. El informe incluye coincidencias directas por regla,
excluidos contando descendientes, marcas atómicas y mallas antes/después.
Estos recuentos no equivalen a piezas físicas. Revisa también reglas sin
coincidencias. Sin `--preflight`, una importación correcta sustituye el Blender
de la etapa 1: guarda tus cambios manuales o prueba con `--output-dir`.

No se admite eliminar toda la geometría ni borrar objetos con controles
anotados. Si después se anota desde YAML, sus objetivos deben seguir existiendo;
una referencia eliminada hará fallar la anotación. No se modifica el YAML.

## Preferencias atómicas

Continúa con `annotate`, `check` y `export`. El exportador conserva por nodo
`extras.cosmosys_import = {"version": 1, "mode": "atomic"}`. Architecture con
esta función (a partir del desarrollo **0.1.10-dirty**) lo usa como selección
inicial editable en preflight. Un plugin anterior puede ignorarlo: revisa la
selección antes de confirmar. No exige YAML ni cambia el contrato de controles.

Para marcar manualmente un conjunto, selecciona su raíz (objeto o Empty) en
el Outliner y ejecuta en la consola Python de Blender:

```python
bpy.context.active_object['cosmosys_import'] = {'version': 1, 'mode': 'atomic'}
```

Para retirar la preferencia:

```python
bpy.context.active_object.pop('cosmosys_import', None)
```

Una Collection no sustituye a una raíz de objetos glTF. Architecture sigue
rechazando un atómico que esconda objetivos de controles internos: expándelo
en el preflight para exponer esos grados de libertad.

## Perfiles

BancoIFU excluye familias DIN/ISO enumeradas, pasadores ISO2338 y nombres con
diámetro×longitud como `M03X12` o `M2_5X03`. Conserva explícitamente los
posicionadores `POSICIONADOR_M04X10`, `POSICIONADOR_M03X05` y `ST_M12X10_C`.
No filtra por `SCREW`, `TORNILLO`, `DIN_TRACK_35`, `FOLDING` ni `M70` genéricos.
Es un perfil para este modelo, no una clasificación universal.

NRT excluye `iston` y `vastago`, sin tildes como en ese CAD. Los CSV de trabajo
están en `0_import/filters.csv`; las copias versionadas, en `examples/filters/`.
