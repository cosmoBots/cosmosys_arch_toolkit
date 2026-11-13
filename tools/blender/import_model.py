"""Import supported interchange formats into a fresh Blender scene."""
from pathlib import Path

import bpy
from mathutils import Matrix

IMPORTERS = {
    '.glb': ('import_scene', 'gltf'),
    '.gltf': ('import_scene', 'gltf'),
    '.obj': ('wm', 'obj_import'),
    '.stl': ('wm', 'stl_import'),
    '.ply': ('wm', 'ply_import'),
    '.fbx': ('import_scene', 'fbx'),
}


def import_model(request):
    source = Path(request['source'])
    names = IMPORTERS.get(source.suffix.lower())
    if names is None:
        raise ValueError('Formato no soportado. Usa GLB/glTF, OBJ, STL, PLY o FBX con importador disponible.')
    operator = getattr(getattr(bpy.ops, names[0]), names[1])
    try:
        operator.get_rna_type()
    except (AttributeError, RuntimeError) as error:
        raise ValueError(f'El importador {source.suffix} no está disponible en este Blender.') from error
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.name = 'csysArch'
    scene.unit_settings.system = 'METRIC'
    scene.unit_settings.scale_length = 1
    result = operator(filepath=str(source))
    if 'FINISHED' not in result:
        raise ValueError('Blender no completó la importación.')
    meshes = [obj for obj in scene.objects if obj.type == 'MESH']
    if not meshes or not any(obj.data.polygons for obj in meshes):
        raise ValueError('El fichero no contiene superficies de malla importables.')
    warnings = []
    if source.suffix.lower() in {'.obj', '.stl', '.ply'}:
        warnings.append('Formato sin unidad garantizada: se interpreta 1 unidad como 1 metro; verifica dimensiones o indica --scale.')
    scale = request['scale']
    if scale != 1:
        for obj in [obj for obj in scene.objects if obj.parent is None]:
            obj.matrix_world = Matrix.Scale(scale, 4) @ obj.matrix_world
        bpy.context.view_layer.update()
        warnings.append(f'Factor de escala de importación: {scale:g}. Aplicar escalas antes de exportar controles.')
    path = Path(request['output']) / (request['name'] + '.blend')
    if path.exists():
        raise ValueError('El .blend de salida ya existe; no se sobrescribe.')
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=str(path))
    return dict(errors=[], warnings=warnings, scene=scene.name, objects=len(scene.objects),
                meshes=len(meshes), imported_blend=str(path))
