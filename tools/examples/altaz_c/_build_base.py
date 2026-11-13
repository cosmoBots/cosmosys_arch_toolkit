"""Original procedural altaz demonstrator. Never reads any external CAD mesh.

Internal scaffold for build_altaz_c.py, not a usable observatory alternative.
Its intermediate enclosure is replaced before producing the canonical model.
This creates a NEW scene from factory settings: use a separate Blender process.
"""
import argparse
import importlib.util
import json
import math
from pathlib import Path
import sys

import bpy
from mathutils import Vector

parser = argparse.ArgumentParser()
parser.add_argument('--output', type=Path, required=True)
parser.add_argument('--render', action='store_true')
args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else [])
OUT = args.output.resolve()
OUT.mkdir(parents=True, exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.context.preferences.filepaths.save_version = 0
main = bpy.context.scene
main.name = 'Observatory'
main.unit_settings.system = 'METRIC'
collections = {}
for name in ['00_Root', '01_Telescope', '02_Enclosure', '90_Studio']:
    coll = bpy.data.collections.new(name)
    main.collection.children.link(coll)
    collections[name] = coll
current = collections['01_Telescope']


def material(name, color, metal=0.0, roughness=0.5):
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = (*color, 1)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get('Principled BSDF')
    bsdf.inputs['Base Color'].default_value = (*color, 1)
    bsdf.inputs['Metallic'].default_value = metal
    bsdf.inputs['Roughness'].default_value = roughness
    return mat


TEAL = material('Enamel - deep teal', (0.055, 0.29, 0.30), 0.12)
SILVER = material('Satin aluminium', (0.62, 0.67, 0.70), 0.25, 0.4)
DARK = material('Graphite housings', (0.085, 0.105, 0.12), 0.1)
WHITE = material('Dome - warm white', (0.79, 0.81, 0.79), 0.04)
STONE = material('Building - pale concrete', (0.57, 0.61, 0.59))
MIRROR = material('Mirror - muted blue', (0.24, 0.38, 0.45), 0.7, 0.18)
ORANGE = material('Drive indicator', (0.88, 0.33, 0.065))


def adopt(obj, name, parent=None, location=(0, 0, 0), mat=None, model=True):
    obj.name = name
    for coll in list(obj.users_collection):
        coll.objects.unlink(obj)
    current.objects.link(obj)
    obj.parent = parent
    obj.location = location
    obj.rotation_mode = 'XYZ'
    if model:
        obj['demo_model'] = True
    if mat:
        obj.data.materials.append(mat)
        obj.color = mat.diffuse_color
    return obj


def empty(name, parent=None, location=(0, 0, 0)):
    obj = bpy.data.objects.new(name, None)
    current.objects.link(obj)
    obj.parent, obj.location = parent, location
    obj.rotation_mode = 'XYZ'
    obj.empty_display_type = 'ARROWS'
    obj.empty_display_size = 0.7
    obj['demo_model'] = True
    return obj


def box(name, parent, center, size, mat, bevel=0.05):
    bpy.ops.mesh.primitive_cube_add(size=1)
    obj = adopt(bpy.context.object, name, parent, center, mat)
    # Bake dimensions into vertices, never leave nonuniform scale on ancestors.
    for vertex in obj.data.vertices:
        vertex.co = Vector(tuple(vertex.co[i] * size[i] for i in range(3)))
    if bevel:
        modifier = obj.modifiers.new('Small machined edges', 'BEVEL')
        modifier.width, modifier.segments = bevel, 2
    return obj


def cylinder(name, parent, center, radius, depth, mat, axis='z', vertices=48):
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices, radius=radius, depth=depth)
    obj = adopt(bpy.context.object, name, parent, center, mat)
    if axis == 'x':
        obj.rotation_euler.y = math.pi / 2
    elif axis == 'y':
        obj.rotation_euler.x = math.pi / 2
    for polygon in obj.data.polygons:
        polygon.use_smooth = len(polygon.vertices) == 4
    return obj


def mesh(name, parent, verts, faces, mat):
    data = bpy.data.meshes.new(name + '_mesh')
    data.from_pydata(verts, [], faces)
    data.update()
    obj = bpy.data.objects.new(name, data)
    current.objects.link(obj)
    obj.parent = parent
    obj['demo_model'] = True
    obj.data.materials.append(mat)
    obj.color = mat.diffuse_color
    return obj


def ring(name, parent, center, outer, inner, depth, mat, axis='z', segments=64):
    verts, faces = [], []
    for level in [-depth / 2, depth / 2]:
        for radius in [outer, inner]:
            for i in range(segments):
                a = 2 * math.pi * i / segments
                p = (radius * math.cos(a), radius * math.sin(a), level)
                if axis == 'y':
                    p = (p[0], p[2], -p[1])
                elif axis == 'x':
                    p = (p[2], p[1], -p[0])
                verts.append(tuple(p[j] + center[j] for j in range(3)))
    n = segments
    for i in range(n):
        j = (i + 1) % n
        faces.extend([(i, j, 2*n+j, 2*n+i), (n+j, n+i, 3*n+i, 3*n+j),
                      (j, i, n+i, n+j), (2*n+i, 2*n+j, 3*n+j, 3*n+i)])
    return mesh(name, parent, verts, faces, mat)


def strut(name, parent, start, end, radius, mat):
    start, end = Vector(start), Vector(end)
    obj = cylinder(name, parent, (start + end) / 2, radius, (end-start).length, mat, vertices=16)
    obj.rotation_euler = (end-start).to_track_quat('Z', 'Y').to_euler('XYZ')
    return obj


def pivot(name, parent, location, key, axis, minimum, maximum):
    obj = empty(name, parent, location)
    obj['control_key'] = key
    obj['control_step_degrees'] = 1.0
    obj['help'] = 'Native Limit Rotation in LOCAL space is the source of limits. See README.'
    obj.lock_location = (True, True, True)
    obj.lock_scale = (True, True, True)
    obj.lock_rotation = tuple(a != axis for a in 'xyz')
    constraint = obj.constraints.new('LIMIT_ROTATION')
    constraint.name = 'DOF - edit limits here'
    constraint.owner_space = 'LOCAL'
    constraint.use_transform_limit = True
    for a in 'xyz':
        setattr(constraint, 'use_limit_' + a, True)
        setattr(constraint, 'min_' + a, math.radians(minimum) if a == axis else 0)
        setattr(constraint, 'max_' + a, math.radians(maximum) if a == axis else 0)
    return obj


current = collections['00_Root']
root = empty('Observatory_Root')
current = collections['01_Telescope']
fixed = empty('Telescope_Foundation', root)
cylinder('Anchor_plate', fixed, (0, 0, 0.12), 1.28, 0.24, DARK)
cylinder('Fixed_pier', fixed, (0, 0, 0.97), 0.90, 1.50, WHITE)
cylinder('Fixed_azimuth_race', fixed, (0, 0, 1.80), 1.22, 0.20, SILVER)
azimuth = pivot('DOF_Azimuth', fixed, (0, 0, 1.90), 'azimuth', 'z', -300, 300)
cylinder('Rotating_azimuth_race', azimuth, (0, 0, 0.12), 1.18, 0.24, DARK)
fork = empty('Fork_Assembly', azimuth)
# Fixed mechanical reference: local +X points along world -X. Positive
# mechanical elevation tips the zenith-pointing optics toward the front slit.
fork.rotation_euler.z = math.pi
box('Fork_crossbeam', fork, (0, 0, 0.40), (3.6, 1.20, 0.40), TEAL, 0.1)
for sign, side in [(-1, 'Left'), (1, 'Right')]:
    arm = empty('Fork_' + side, fork)
    box('Fork_arm_' + side, arm, (sign*1.55, 0, 1.30), (0.46, 0.96, 1.72), TEAL, 0.12)
    cylinder('Elevation_bearing_' + side, arm, (sign*1.55, 0, 2.25), 0.47, 0.50, SILVER, 'x')
    cylinder('Bearing_cap_' + side, arm, (sign*1.85, 0, 2.25), 0.37, 0.12, DARK, 'x')
box('Azimuth_drive', fork, (0.78, -0.92, 0.22), (0.70, 0.55, 0.50), SILVER)
box('Azimuth_drive_indicator', fork, (0.78, -1.21, 0.22), (0.16, 0.03, 0.16), ORANGE, 0.01)
box('Elevation_drive', fork, (-2.10, -0.05, 2.25), (0.42, 0.62, 0.63), SILVER)
elevation = pivot('DOF_Elevation', fork, (0, 0, 2.25), 'elevation', 'x', 0, 90)
optics = empty('Optical_Assembly', elevation)
# Geometry was constructed along local +Y. This FIXED rest transform points it
# at the zenith while DOF_Elevation remains exactly zero (not a saved test pose).
optics.rotation_euler.x = math.pi / 2
ring('Tube_saddle', optics, (0, 0, 0), 1.13, 0.94, 0.26, DARK, 'y', 8)
for sign, side in [(-1, 'Left'), (1, 'Right')]:
    cylinder('Moving_trunnion_' + side, optics, (sign*1.23, 0, 0), 0.33, 0.42, DARK, 'x')
cell = empty('Primary_Cell_Assembly', optics)
ring('Primary_cell', cell, (0, -1.15, 0), 1.13, 0.86, 0.46, DARK, 'y', 8)
cylinder('Primary_mirror', cell, (0, -0.91, 0), 0.93, 0.07, MIRROR, 'y')
box('Rear_instrument', cell, (0, -1.76, 0), (0.78, 0.60, 0.68), SILVER)
cylinder('Instrument_connector', cell, (0, -2.12, 0), 0.18, 0.17, DARK, 'y')
truss = empty('Truss_Assembly', optics)
for i in range(8):
    angle = 2*math.pi*i/8 + math.pi/8
    shifted = angle + (math.pi/8 if i % 2 == 0 else -math.pi/8)
    strut(f'Truss_strut_{i+1:02}', truss,
          (1.02*math.cos(angle), -0.85, 1.02*math.sin(angle)),
          (0.94*math.cos(shifted), 2.65, 0.94*math.sin(shifted)), 0.052, SILVER)
secondary = empty('Secondary_Assembly', optics)
ring('Secondary_ring', secondary, (0, 2.65, 0), 1.06, 0.88, 0.18, DARK, 'y', 8)
cylinder('Secondary_holder', secondary, (0, 2.65, 0), 0.22, 0.27, DARK, 'y')
for i in range(4):
    angle = i*math.pi/2
    strut(f'Secondary_spider_{i+1}', secondary, (0, 2.65, 0),
          (0.91*math.cos(angle), 2.65, 0.91*math.sin(angle)), 0.018, DARK)

# Enclosure has its own fixed branch: dome motion NEVER moves the telescope.
current = collections['02_Enclosure']
building = empty('Building_Fixed', root)
ring('Foundation_slab', building, (0, 0, 0.02), 5.55, 1.30, 0.12, STONE)


def wall_sector(name, a0, a1):
    verts, faces, steps = [], [], 32
    for z in [0.08, 3.05]:
        for radius in [5.20, 5.03]:
            for i in range(steps+1):
                a = a0+(a1-a0)*i/steps
                verts.append((radius*math.sin(a), radius*math.cos(a), z))
    n = steps+1
    for i in range(steps):
        j = i+1
        faces.extend([(i, j, 2*n+j, 2*n+i), (n+j, n+i, 3*n+i, 3*n+j),
                      (2*n+i, 2*n+j, 3*n+j, 3*n+i), (j, i, n+i, n+j)])
    faces.extend([(0, 2*n, 3*n, n), (n-1, 2*n-1, 4*n-1, 3*n-1)])
    return mesh(name, building, verts, faces, STONE)


wall_sector('Building_front_panel', -math.pi/3, math.pi/3)
wall_sector('Building_rear_wall', math.pi/3, 5*math.pi/3)
box('Service_annex', building, (-5.30, -1.2, 1.0), (1.8, 2.30, 2.0), WHITE)
box('Service_door', building, (-6.22, -1.2, 0.85), (0.05, 0.90, 1.65), DARK, 0.01)
ring('Fixed_dome_track', building, (0, 0, 3.06), 5.36, 4.98, 0.20, SILVER)
dome = pivot('DOF_Dome_Azimuth', building, (0, 0, 3.17), 'dome_azimuth', 'z', -180, 180)
ring('Rotating_dome_track', dome, (0, 0, 0.08), 5.34, 5.07, 0.16, DARK)


def sphere_strip(name, parent, radius, phi0, phi1, nphi, ntheta, mat, polar0=0.0, polar1=math.pi/2):
    verts, faces = [], []
    # Polar patches, no duplicated pole: tiny 0.15-degree cap kept separate.
    polar0 = max(polar0, math.radians(0.15))
    for j in range(ntheta+1):
        theta = polar0+(polar1-polar0)*j/ntheta
        for i in range(nphi+1):
            phi = phi0+(phi1-phi0)*i/nphi
            verts.append((radius*math.sin(theta)*math.sin(phi),
                          radius*math.sin(theta)*math.cos(phi), radius*math.cos(theta)))
    for j in range(ntheta):
        for i in range(nphi):
            a = j*(nphi+1)+i
            faces.append((a, a+nphi+1, a+nphi+2, a+1))
    obj = mesh(name, parent, verts, faces, mat)
    solid = obj.modifiers.new('Thin shell', 'SOLIDIFY')
    solid.thickness = 0.045
    for polygon in obj.data.polygons:
        polygon.use_smooth = True
    return obj


half_slit = math.radians(14)
sphere_strip('Dome_shell', dome, 5.24, half_slit, 2*math.pi-half_slit, 108, 32, WHITE)
shutter = pivot('DOF_Shutter', dome, (0, 0, 0), 'shutter_open', 'x', 0, 100)
sphere_strip('Curved_shutter', shutter, 5.34, -half_slit-0.018, half_slit+0.018, 12, 32, TEAL)
# Side guides follow the stationary dome shell. Shutter slides OVER its rear.
for sign, side in [(-1, 'Left'), (1, 'Right')]:
    phi = sign*(half_slit+0.028)
    sphere_strip('Shutter_guide_' + side, dome, 5.29, phi-0.006, phi+0.006, 2, 36, SILVER)

current = collections['90_Studio']
world = bpy.data.worlds.new('Soft studio world')
world.use_nodes = True
world.node_tree.nodes['Background'].inputs[0].default_value = (0.78, 0.83, 0.87, 1)
world.node_tree.nodes['Background'].inputs[1].default_value = 0.65
main.world = world


def camera(name, position, look_at, scale):
    data = bpy.data.cameras.new(name)
    obj = bpy.data.objects.new(name, data)
    current.objects.link(obj)
    obj.location = position
    obj.rotation_euler = (Vector(look_at)-obj.location).to_track_quat('-Z', 'Y').to_euler()
    data.type, data.ortho_scale = 'ORTHO', scale
    return obj


cam_telescope = camera('Camera_Telescope', (11, 14, 9), (0, 0.4, 3.7), 9.9)
cam_observatory = camera('Camera_Observatory', (17, 22, 15), (0, 0, 3.7), 16.5)
for name, position, energy, size in [('Key', (2, 5, 14), 2200, 8), ('Fill', (-9, 1, 9), 1800, 7), ('Rim', (3, -9, 12), 2500, 7)]:
    data = bpy.data.lights.new(name, 'AREA')
    data.energy, data.shape, data.size = energy, 'DISK', size
    obj = bpy.data.objects.new(name, data)
    current.objects.link(obj)
    obj.location = position
    obj.rotation_euler = (-obj.location).to_track_quat('-Z', 'Y').to_euler()
main.camera = cam_observatory
inspect = bpy.data.scenes.new('Telescope - inspect')
for name in ['00_Root', '01_Telescope', '90_Studio']:
    inspect.collection.children.link(collections[name])
inspect.world, inspect.camera = world, cam_telescope
inspect.unit_settings.system = 'METRIC'
for scene in [main, inspect]:
    scene.render.engine = 'CYCLES'
    scene.cycles.samples = 24
    scene.cycles.use_denoising = True
    scene.render.threads_mode, scene.render.threads = 'FIXED', 4
    scene.render.resolution_x, scene.render.resolution_y = 1100, 900
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'PNG'
    scene.render.film_transparent = True
    scene.view_settings.view_transform = 'AgX'

# Export annotations and YAML from constraints, at ZERO pose, not showroom pose.
spec = importlib.util.spec_from_file_location('export_model', Path(__file__).resolve().parents[2] / 'blender/export_model.py')
exporter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(exporter)
controls = exporter.export(OUT, scene_name='Observatory', root_name='Observatory_Root', name='Altaz_C')

# Numerical checks on native Blender evaluation: hierarchy, travel, isolation.
def pose(key, degrees):
    obj = next(o for o in [azimuth, elevation, dome, shutter] if o['control_key'] == key)
    axis = next(a for a in 'xyz' if getattr(obj.constraints[0], 'max_'+a) > getattr(obj.constraints[0], 'min_'+a))
    obj.rotation_euler['xyz'.index(axis)] = math.radians(degrees)
    bpy.context.view_layer.update()


def world_matrix(obj):
    return obj.evaluated_get(bpy.context.evaluated_depsgraph_get()).matrix_world.copy()


def close(a, b):
    return all(abs(a[r][c]-b[r][c]) < 1e-5 for r in range(4) for c in range(4))


rest = {o: world_matrix(o) for o in [azimuth, fork, elevation, optics, building, dome, shutter]}
for mechanical in [0, 30, 90]:
    pose('elevation', mechanical)
    direction = (world_matrix(optics).to_3x3() @ Vector((0, 1, 0))).normalized()
    assert abs(direction.z-math.cos(math.radians(mechanical))) < 1e-5
    assert abs(direction.y-math.sin(math.radians(mechanical))) < 1e-5
pose('elevation', 0)
pose('azimuth', 45)
assert not close(world_matrix(fork), rest[fork])
assert not close(world_matrix(optics), rest[optics])
assert close(world_matrix(building), rest[building])
assert close(world_matrix(dome), rest[dome])
pose('azimuth', 0)
pose('elevation', 60)
assert close(world_matrix(fork), rest[fork])
assert not close(world_matrix(optics), rest[optics])
pose('elevation', 0)
pose('dome_azimuth', 70)
assert close(world_matrix(optics), rest[optics])
assert not close(world_matrix(shutter), rest[shutter])
pose('dome_azimuth', 0)
pose('shutter_open', 80)
assert close(world_matrix(dome), rest[dome])
assert not close(world_matrix(shutter), rest[shutter])
pose('shutter_open', 0)
samples = []
for values in [dict(azimuth=45, elevation=30, dome_azimuth=70, shutter_open=80),
               dict(azimuth=-300, elevation=90, dome_azimuth=-90, shutter_open=100),
               dict(azimuth=300, elevation=0, dome_azimuth=0, shutter_open=0)]:
    for key, value in values.items():
        pose(key, value)
    from mathutils import Matrix
    basis = Matrix(((1, 0, 0, 0), (0, 0, 1, 0), (0, -1, 0, 0), (0, 0, 0, 1)))
    matrices = {}
    for obj in [fixed, azimuth, fork, elevation, optics, building, dome, shutter]:
        converted = basis @ world_matrix(obj) @ basis.inverted()
        # Column-major, matching Three.js Matrix4.elements.
        matrices[obj.name] = [converted[r][c] for c in range(4) for r in range(4)]
    samples.append(dict(values=values, matrices=matrices))
for key in ['azimuth', 'elevation', 'dome_azimuth', 'shutter_open']:
    pose(key, 0)
for obj in [azimuth, elevation, dome, shutter]:
    c = obj.constraints[0]
    a = next(a for a in 'xyz' if getattr(c, 'max_'+a) > getattr(c, 'min_'+a))
    idx = 'xyz'.index(a)
    if getattr(c, 'max_'+a) - getattr(c, 'min_'+a) >= 2*math.pi - 1e-6:
        # Full-turn azimuth is cyclic: a rotation matrix cannot count turns.
        # glTF metadata/slider limits still define the configured numeric range.
        continue
    obj.rotation_euler[idx] = getattr(c, 'max_'+a) + math.radians(25)
    bpy.context.view_layer.update()
    actual = obj.evaluated_get(bpy.context.evaluated_depsgraph_get()).matrix_local.to_euler('XYZ')[idx]
    # Rotation matrices wrap at 180 deg; compare through sin/cos.
    assert abs(math.sin(actual)-math.sin(getattr(c, 'max_'+a))) < 1e-5
    assert abs(math.cos(actual)-math.cos(getattr(c, 'max_'+a))) < 1e-5
    obj.rotation_euler[idx] = 0
    bpy.context.view_layer.update()

bpy.context.window.scene = inspect
bpy.ops.object.select_all(action='DESELECT')
elevation.select_set(True)
bpy.context.view_layer.objects.active = elevation
for screen in bpy.data.screens:
    for area in screen.areas:
        if area.type == 'PROPERTIES':
            area.spaces.active.context = 'CONSTRAINT'
        elif area.type == 'VIEW_3D':
            space = area.spaces.active
            space.shading.type, space.shading.color_type = 'SOLID', 'MATERIAL'
            space.region_3d.view_distance = 12
            space.region_3d.view_location = (0, 0.2, 3.6)
            space.region_3d.view_rotation = cam_telescope.rotation_euler.to_quaternion()
            space.clip_end = 1000
            space.show_region_ui = True
guide = bpy.data.texts.new('START_HERE.txt')
guide.write('''ALTAZ C - original procedural demonstration

Select DOF_Azimuth / DOF_Elevation in the Outliner.
N > Item > Rotation: change Z for azimuth or X for elevation.
Properties > Object Constraints (chain icon): edit DOF limits.
Scene Telescope - inspect hides the enclosure only for inspection.
Scene Observatory shows the same telescope inside its enclosure.
DOF_Dome_Azimuth uses local Z; DOF_Shutter uses local X.
All poses are offsets from zero; rotations are inherited by children.
Mechanical elevation: 0 deg = zenith, 90 deg = horizon.
PORIS astronomical elevation -> CAD: CAD = 90 - PORIS (m=-1, h=90).
To export after editing limits: save the blend and use Architecture Toolkit.
GLB and YAML are derived from native constraints by its check/export commands.
''')
bpy.ops.wm.save_as_mainfile(filepath=str(OUT / 'Altaz_C.blend'))
(OUT / 'validation.json').write_text(json.dumps({
    'blender_version': bpy.app.version_string, 'controls': controls,
    'checks': ['azimuth carries fork and optics', 'elevation does not move fork',
               'dome independent of telescope', 'shutter inherits dome rotation',
               'native constraints clamp bounded elevation and shutter',
               'native azimuth matrices are cyclic, exported numeric range is bounded',
               'mechanical elevation zero=zenith, 90=horizon; CAD=90-PORIS', 'zero-pose export'],
    'source_geometry': 'Only procedural primitives; no external mesh input',
    'pose_samples': samples,
}, indent=2), encoding='utf8')

if args.render:
    pose('elevation', 48)  # 42 deg astronomical altitude.
    inspect.render.filepath = str(OUT / 'preview_telescope.png')
    bpy.ops.render.render(write_still=True, scene=inspect.name)
    pose('shutter_open', 95)
    # Cutaway is presentation only, never part of the saved file or GLB.
    bpy.data.objects['Building_front_panel'].hide_render = True
    main.render.filepath = str(OUT / 'preview_observatory.png')
    bpy.ops.render.render(write_still=True, scene=main.name)
print('ALTAZ C: BUILT / EXPORTED / NATIVE HIERARCHY TESTS PASS')
