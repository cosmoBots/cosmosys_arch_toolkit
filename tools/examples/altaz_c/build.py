"""Canonical Altaz C: wide slit + laterally translating curved shutter.

Builds the shared telescope scaffold in a temporary directory, then replaces
the enclosure and adjusts fork height. No external CAD input.
Run with Blender: blender -b --python-exit-code 1 -P this_file.py -- --output OUTPUT
"""
import argparse
import json
import math
from pathlib import Path
import runpy
import sys
from tempfile import TemporaryDirectory

import bpy
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree

HERE = Path(__file__).resolve().parent
original_args = sys.argv[:]
parser = argparse.ArgumentParser()
parser.add_argument('--output', type=Path, required=True)
parser.add_argument('--no-render', action='store_true')
args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else [])
OUT = args.output.resolve()
OUT.mkdir(parents=True, exist_ok=False)
with TemporaryDirectory(prefix='altaz-scaffold-') as scaffold:
    try:
        sys.argv = [str(HERE/'_build_base.py'), '--', '--output', scaffold]
        env = runpy.run_path(str(HERE/'_build_base.py'))
    finally:
        sys.argv = original_args
main = bpy.data.scenes['Observatory']
bpy.context.window.scene = main
namespace = env['mesh'].__globals__
namespace['current'] = env['collections']['02_Enclosure']
mesh, box = env['mesh'], env['box']
dome = bpy.data.objects['DOF_Dome_Azimuth']
dome.constraints[0].min_z = math.radians(-300)
dome.constraints[0].max_z = math.radians(300)
shutter = bpy.data.objects['DOF_Shutter']
elevation = bpy.data.objects['DOF_Elevation']
optics = bpy.data.objects['Optical_Assembly']
azimuth = bpy.data.objects['DOF_Azimuth']

# 12 m building; lower rim clears the entire pupil even at the horizon.
scale = 6.0 / 5.20
for name in ['Foundation_slab', 'Building_front_panel', 'Building_rear_wall',
             'Fixed_dome_track', 'Rotating_dome_track']:
    obj = bpy.data.objects[name]
    for vertex in obj.data.vertices:
        vertex.co.x *= scale
        vertex.co.y *= scale
        if name.startswith('Building_'):
            vertex.co.z *= 2.63/3.05
        elif name == 'Fixed_dome_track':
            vertex.co.z -= 0.42
dome.location.z = 2.75
bpy.data.objects['Service_annex'].location.x = -6.1
bpy.data.objects['Service_door'].location.x = -7.02

# Rear instrument must also clear the fork crossbeam at zenith.
elevation.location.z += 0.85
for side in ['Left', 'Right']:
    arm = bpy.data.objects['Fork_arm_'+side]
    arm.location.z += 0.425
    for vertex in arm.data.vertices:
        vertex.co.z *= (1.72+0.85)/1.72
    for prefix in ['Elevation_bearing_', 'Bearing_cap_']:
        bpy.data.objects[prefix+side].location.z += 0.85
bpy.data.objects['Elevation_drive'].location.z += 0.85

for name in ['Dome_shell', 'Curved_shutter', 'Shutter_guide_Left', 'Shutter_guide_Right']:
    bpy.data.objects.remove(bpy.data.objects[name], do_unlink=True)
for constraint in list(shutter.constraints):
    shutter.constraints.remove(constraint)
limit = shutter.constraints.new('LIMIT_LOCATION')
limit.name = 'DOF - lateral opening (metres)'
limit.owner_space = 'LOCAL'
limit.use_transform_limit = True
for axis in 'xyz':
    setattr(limit, 'use_min_'+axis, True)
    setattr(limit, 'use_max_'+axis, True)
    setattr(limit, 'min_'+axis, 0)
    setattr(limit, 'max_'+axis, 3.6 if axis == 'x' else 0)
shutter.lock_location = (False, True, True)
shutter.lock_rotation = (True, True, True)
del shutter['control_step_degrees']
shutter['control_step_metres'] = 0.05
shutter['help'] = 'Location X in metres: 0 closed, 3.6 open. Edit native Limit Location.'

RADIUS, HALF_WIDTH, REAR_ANGLE = 6.0, 1.6, math.radians(20)


def patch(name, parent, radius, x0, x1, t0, t1, nx, nt, material):
    """Sphere sliced by parallel x planes, NOT converging longitude wedges.

    t is angle from zenith, positive toward front +Y. Constant transverse width
    is maintained at zenith and the opening continues 20 deg beyond zenith.
    """
    verts, faces = [], []
    for i in range(nx+1):
        x = x0+(x1-x0)*i/nx
        rho = math.sqrt(max(0, radius*radius-x*x))
        for j in range(nt+1):
            t = t0+(t1-t0)*j/nt
            verts.append((x, rho*math.sin(t), rho*math.cos(t)))
    for i in range(nx):
        for j in range(nt):
            a = i*(nt+1)+j
            faces.append((a, a+nt+1, a+nt+2, a+1))
    obj = mesh(name, parent, verts, faces, material)
    solid = obj.modifiers.new('Thin enclosure skin', 'SOLIDIFY')
    solid.thickness = 0.045
    for polygon in obj.data.polygons:
        polygon.use_smooth = True
    return obj


# Tiny degenerate boundary at x=+-R is closed by the solidify modifier; no top cap
# spans the slit. Three patches are a single fixed casing assembly.
shells = []
shells.append(patch('Dome_left_shell', dome, RADIUS, -RADIUS, -HALF_WIDTH,
                    -math.pi/2, math.pi/2, 56, 80, env['WHITE']))
shells.append(patch('Dome_right_shell', dome, RADIUS, HALF_WIDTH, RADIUS,
                    -math.pi/2, math.pi/2, 56, 80, env['WHITE']))
shells.append(patch('Dome_rear_bridge', dome, RADIUS, -HALF_WIDTH, HALF_WIDTH,
                    -math.pi/2, -REAR_ANGLE, 24, 32, env['WHITE']))
cover = patch('Curved_shutter', shutter, 6.4, -1.74, 1.74,
              -math.radians(22), math.pi/2, 28, 80, env['TEAL'])

# A single horizontal translation, with no implicit coupled parameters.
for label, y, z in [('Front', 6.46, -0.05), ('Rear', -2.40, 5.94)]:
    box('Shutter_rail_'+label, dome, (1.8, y, z), (7.7, 0.12, 0.12), env['SILVER'], 0.025)
for x in [-1.85, 5.45]:
    box('Front_rail_support_'+str(x), dome, (x, 6.46, -0.23), (0.18, 0.18, 0.50), env['DARK'], 0.02)

def pose(obj, value):
    if obj == shutter:
        obj.location.x = value
    else:
        axis = 0 if obj == elevation else 2
        obj.rotation_euler[axis] = math.radians(value)
    bpy.context.view_layer.update()


# Sample the full pupil, not just a central ray. 2.2m conservative pupil diameter
# exceeds the actual 1.86m mirror. Test a +/-0.5-degree field too.
enclosure = [o for o in env['collections']['02_Enclosure'].objects if o.type == 'MESH']
pose(shutter, 3.6)
rays, failures = 0, []
for azi in [0, 45, 120, 240]:
    pose(azimuth, azi)
    pose(dome, (azi+180)%360-180)
    for mechanical in range(0, 91, 5):
        pose(elevation, mechanical)
        deps = bpy.context.evaluated_depsgraph_get()
        surfaces = [(o.name, o.matrix_world.inverted(), BVHTree.FromObject(o, deps)) for o in enclosure]
        optical = optics.evaluated_get(deps).matrix_world
        pupil = [(0.0, 0.0)]
        for radius in [0.55, 1.1]:
            pupil += [(radius*math.cos(i*math.pi/12), radius*math.sin(i*math.pi/12)) for i in range(24)]
        for px, pz in pupil:
            origin = optical @ Vector((px, -0.91, pz))
            for field in [-0.5, 0, 0.5]:
                # Field in the meridian plane; transverse width already includes
                # generous pupil margin. A separate x-direction field is tested.
                for transverse in [False, True]:
                    tilt = optical.to_3x3() @ (Vector((math.tan(math.radians(field)), 1, 0)) if transverse else Vector((0,1,math.tan(math.radians(field)))))
                    ray = tilt.normalized()
                    rays += 1
                    for name, inverse, tree in surfaces:
                        hit = tree.ray_cast(inverse @ origin, (inverse.to_3x3() @ ray).normalized(), 50)[0]
                        if hit is not None:
                            failures.append(dict(azimuth=azi, mechanical=mechanical, pupil=[px,pz], field=field, object=name))
                            break
assert not failures, json.dumps(failures[:10])

# Closed lid must block at least the on-axis zenith beam.
pose(azimuth, 0); pose(dome, 0); pose(elevation, 0); pose(shutter, 0)
deps = bpy.context.evaluated_depsgraph_get()
tree = BVHTree.FromObject(cover, deps)
inverse = cover.matrix_world.inverted()
origin = optics.matrix_world @ Vector((0, -0.91, 0))
assert tree.ray_cast(inverse @ origin, inverse.to_3x3() @ Vector((0,0,1)), 50)[0] is not None

# Record the maximum radial envelope of the COMPLETE moving telescope relative
# to dome centre, including rear instrument; no safety certification implied.
maximum_radius = 0.0
minimum_rear_height = float('inf')
for mechanical in range(0,91,2):
    pose(elevation, mechanical)
    deps = bpy.context.evaluated_depsgraph_get()
    for obj in env['collections']['01_Telescope'].objects:
        if obj.type != 'MESH':
            continue
        evaluated = obj.evaluated_get(deps)
        data = evaluated.to_mesh()
        for vertex in data.vertices:
            point = evaluated.matrix_world @ vertex.co
            maximum_radius = max(maximum_radius, (point-Vector((0,0,2.75))).length)
            if obj.name in {'Rear_instrument', 'Instrument_connector'}:
                minimum_rear_height = min(minimum_rear_height, point.z)
        evaluated.to_mesh_clear()
assert maximum_radius < RADIUS-0.045
assert minimum_rear_height > 2.5

# Continuous conservative beam bounds, complementing sampled ray tests. The
# mirror pupil is a disk radius1.1 at axial offset-.91 from the elevation pivot.
# Any point is <=hypot(1.1,.91) from it. Across the 0..90 elevation quadrant the
# central ray has nonnegative front/vertical components. A .5-degree field can
# subtract at most 14*tan(.5deg) over this enclosure and projecting hardware.
pupil_extent=math.hypot(1.1,0.91)
field_drift=14*math.tan(math.radians(0.5))
beam_x=1.1+field_drift
beam_y_min=-pupil_extent-field_drift
beam_z_min=5.0-pupil_extent-field_drift
rear_opening_y=-math.sqrt(RADIUS**2-HALF_WIDTH**2)*math.sin(REAR_ANGLE)
assert beam_x < HALF_WIDTH-0.045
assert beam_y_min > rear_opening_y+0.045
assert beam_z_min > 2.91
assert beam_x < 3.6-1.74-0.045
beam_bounds=dict(max_abs_x=beam_x,min_y=beam_y_min,min_z=beam_z_min,
                 rear_slit_y=rear_opening_y,front_rim_top=2.91,
                 pupil_radius=1.1,field_drift_allowance=field_drift,
                 path_length_allowance=14)

# All comparison matrices are rederived from this candidate, including position.
basis = Matrix(((1,0,0,0),(0,0,1,0),(0,-1,0,0),(0,0,0,1)))
samples = []
for values in [dict(azimuth=45,elevation=30,dome_azimuth=45,shutter_open=3.6),
               dict(azimuth=-300,elevation=90,dome_azimuth=60,shutter_open=1.8),
               dict(azimuth=300,elevation=0,dome_azimuth=0,shutter_open=0)]:
    for obj in [azimuth,elevation,dome,shutter]:
        pose(obj, values[obj['control_key']])
    matrices = {}
    for name in ['Telescope_Foundation','DOF_Azimuth','Fork_Assembly','DOF_Elevation',
                 'Optical_Assembly','Building_Fixed','DOF_Dome_Azimuth','DOF_Shutter']:
        matrix = basis @ bpy.data.objects[name].matrix_world @ basis.inverted()
        matrices[name] = [matrix[r][c] for c in range(4) for r in range(4)]
    samples.append(dict(values=values,matrices=matrices))
for obj in [azimuth,elevation,dome,shutter]: pose(obj,0)
controls = env['exporter'].export(OUT, scene_name='Observatory', root_name='Observatory_Root', name='Altaz_C')
report = dict(blender_version=bpy.app.version_string,controls=controls,pose_samples=samples,
              source_geometry='Original procedural model, no external CAD meshes',
              dimensions_m=dict(building_diameter=12.0,dome_radius=6.0,dome_centre_height=2.75,
                                telescope_pivot_height=5.0,slit_width=3.2,mirror_diameter=1.86,
                                tested_pupil_diameter=2.2,shutter_travel=3.6),
              optical_tests=dict(rays=rays,blocked_open=len(failures),mechanical_range=[0,90],
                                 azimuths=[0,45,120,240],field_half_angle_deg=0.5,
                                 max_telescope_radius=maximum_radius,
                                 radial_margin=RADIUS-0.045-maximum_radius,
                                 rear_instrument_min_height=minimum_rear_height,
                                 rear_instrument_crossbeam_clearance=minimum_rear_height-2.5,
                                 shutter_shell_clearance_lower_bound=math.sqrt(6.4**2-1.74**2)-0.045-RADIUS))
report['optical_tests']['conservative_beam_bounds']=beam_bounds
(OUT/'validation.json').write_text(json.dumps(report,indent=2),encoding='utf8')
bpy.data.texts['START_HERE.txt'].clear()
bpy.data.texts['START_HERE.txt'].write('''ALTAZ C - wide optical slit and lateral shutter
DOF_Shutter: N > Item > Location X, metres, 0 closed / 3.6 open.
DOF_Azimuth and DOF_Dome_Azimuth: local Rotation Z.
DOF_Elevation: local Rotation X, 0 deg zenith / 90 deg horizon.
Edit native local constraints to change the control limits.
Save the blend, then use the Architecture Toolkit check/export commands.
See README.md and OPTICAL_VALIDATION.md for details.
''')
bpy.context.window.scene = main
bpy.ops.object.select_all(action='DESELECT')
shutter.select_set(True)
bpy.context.view_layer.objects.active = shutter
bpy.data.objects['Camera_Observatory'].data.ortho_scale=19.0
for screen in bpy.data.screens:
    for area in screen.areas:
        if area.type == 'VIEW_3D':
            area.spaces.active.region_3d.view_distance=23
            area.spaces.active.region_3d.view_location=(1.0,0,4.0)
            area.spaces.active.region_3d.view_rotation=bpy.data.objects['Camera_Observatory'].rotation_euler.to_quaternion()
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'Altaz_C.blend'))
print('LATERAL PROPOSAL VALIDATION',json.dumps(report['optical_tests']))
if not args.no_render:
    pose(elevation,40); pose(shutter,3.6)
    main.render.filepath=str(OUT/'preview_observatory.png')
    bpy.ops.render.render(write_still=True,scene=main.name)
    pose(elevation,0)
    camera=bpy.data.objects['Camera_Observatory']
    camera.location=(11,14,22)
    camera.rotation_euler=(Vector((0,0,4.0))-camera.location).to_track_quat('-Z','Y').to_euler()
    main.render.filepath=str(OUT/'preview_zenith.png')
    bpy.ops.render.render(write_still=True,scene=main.name)
