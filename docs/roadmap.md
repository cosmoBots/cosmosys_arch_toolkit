# Alcance futuro del companion

Este documento describe intención, no servicios implementados ni una
autorización para modificar plugins o despliegues.

## Ahora

- Repositorio independiente, incorporado a csys como submódulo; uso local autónomo.
- Guía de autoría y Altaz_C; scripts separados en `tools/`.
- CLI local `doctor/init/import/annotate/check/export/verify`, exportador común y pruebas.
- Configuración `.env` ignorada y cajones privados `modelos/`, sin instalador.
- Exportación local de ficheros de confianza, sin conexión con Architecture.
- El ejemplo conserva controles tanto en YAML como en extras del GLB.

## Siguientes etapas

### Exportación ligera y preferencias de importación

Ideas acordadas el 2026-11-12, pendientes: no forman parte de los comandos
actuales ni cambian la importación en Redmine.

- Filtrar la exportación desde Blender por fragmentos de nombre/ruta o por
  expresiones regulares, siguiendo la experiencia del preflight Architecture.
  Exportar un GLB realmente ligero, sin la geometría excluida, no sólo ocultarla.
  Previsualizar selección y resolver qué ocurre con pivotes, descendientes y
  controles que quedarían sin objetivo; no dejar referencias colgantes.
- Anotar preferencias por nodo, como `atomic`, para que Architecture proponga
  una única entrada para el conjunto sin crear ítems por cada descendiente.
  Eso no elimina geometría del GLB ni equivale al filtrado de exportación.
  Las preferencias serán propuestas revisables en el preflight: no permiso
  para crear ítems automáticamente ni para saltar controles/validaciones.
- Entregar junto con esa función una guía de autoría desde Blender, no sólo
  scripts: identificar la raíz de un subconjunto en el Outliner, prepararla
  como objeto/Empty con sus piezas hijas conservando transformaciones, marcar
  la preferencia de importación en sus propiedades y comprobarla al exportar
  y revisar en Architecture. Una Collection no sustituye al nodo de jerarquía
  glTF. Explicar incluir/excluir/atómico y distinguirlo de ocultar o eliminar
  geometría; ensayar también el caso de controles dentro de un conjunto atómico.
  El nombre/tipo de la propiedad y su panel se definirán al cerrar el contrato:
  no documentar ahora una propiedad inventada como si ya funcionase.
- Versionar estos metadatos antes de incorporarlos al contrato. Reutilizar los
  conceptos de include/exclude/atomic del importador sin acoplar el toolkit al
  runtime del plugin ni prometer que ambas implementaciones comparten código.

### Colisiones y movimiento: ideas para el ecosistema Architecture–PORIS

Anotadas el 2026-11-13, no implementadas. El seguimiento de ejecución pertenece
al puente/runtime, no presupone convertir el toolkit en un servicio:

- Detectar colisiones de la geometría CAD al ejecutar un plan PORIS y hacer fallar
  la comprobación si el modelo ya no admite la configuración o el recorrido
  requeridos. Debe permitir detectar regresiones tras modificar el CAD. Habrá que
  definir contactos permitidos, geometría de colisión, tolerancias y cobertura;
  muestrear unas poses no garantiza todos los valores de un rango.
- Interpolar los DoF en transiciones elegidas para visualizar movimientos.
  Separar objetivo confirmado del runtime y pose visual temporal, conservando
  límites, vueltas, jerarquías y conversiones; estudiar colisiones en el trayecto,
  no sólo en las poses inicial/final.

El toolkit podría ayudar a preparar/verificar los datos necesarios, pero no se
fija aún formato, motor de colisiones, dependencia ni API. No es certificación
de seguridad ni control de equipos reales.

### Rendimiento de modelos complejos y derivados parciales

Observación del 2026-11-13: al cambiar un DoF en BancoIFU se aprecia retraso.
Investigar primero qué trabajo domina la actualización, diferenciando runtime,
transformaciones, encuadre y renderizado. Evaluar modelos parciales por subárbol
como posible alternativa, no como solución decidida. Deben conservar pivotes,
coordenadas, referencias y cinemática, y no eliminar los obstáculos necesarios
para una futura validación de colisiones. La generación de derivados podría
ser una función del companion, pero su ubicación y contrato quedan abiertos.

### Distribución y servicios

1. Ampliar los casos probados de autoría y los diagnósticos del preflight antes
   de admitir más mecanismos Blender, manteniendo una sola lógica de exportación.
2. Formalizar la compatibilidad y distribución del contrato de intercambio, con pruebas que exporten
   Altaz_C y comprueben su interpretación. Mantener independiente el versionado
   del toolkit respecto al plugin y documentar compatibilidades comprobadas.
3. Distribuir herramientas, documentación y demos desde el repositorio propio,
   sin instalarlas en Redmine; la extracción del workspace ya está realizada.
4. Ofrecer opcionalmente servicios de preflight/conversión, fuera del proceso
   Redmine, además del uso local. El arranque correspondería al deploy, siguiendo
   el patrón de Kroki; el plugin sería cliente, sin acceso al socket Docker.

Una conversión remota no confirma ni crea ítems: entregar resultados para
revisión humana antes del preflight y la importación propios de Architecture.
Las imágenes de ejecución no necesitan contener la demo ni toda la documentación.

## Condiciones antes de ofrecer subidas de .blend

La apertura inicial ya procesa entrada no fiable. El aislamiento debe existir
antes de ese paso: scripts automáticos deshabilitados, sólo código de conversión
conocido, sin secretos, BD ni acceso innecesario a red o al sistema de archivos
del host. Acotar tiempo, memoria, CPU, concurrencia, temporales y salida, y
comprobarlo en el entorno de despliegue real. No equiparar `--disable-autoexec`
ni un contenedor por sí solo a una garantía de aislamiento.

No se añade ahora API, cola, imagen Docker, servicio Compose, setting Redmine,
opción de deploy ni dependencia nueva de cosmosys_arch.
