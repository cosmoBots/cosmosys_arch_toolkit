"""Write the triangulated FreeCAD scene using the shared cosmoSys contract."""
from array import array
import json
import struct
import sys
from pathlib import Path

from exchange import CONTRACT, CONTRACT_VERSION, yaml_text


class Scene:
    def __init__(self):
        self.data = bytearray()
        self.document = {
            'asset': {'version': '2.0', 'generator': 'cosmosys_arch_toolkit / FreeCAD'},
            'scene': 0, 'nodes': [], 'meshes': [], 'bufferViews': [], 'accessors': [],
        }

    def accessor(self, values, *, count, kind, target, bounds=None):
        if sys.byteorder != 'little':
            values.byteswap()
        views = self.document['bufferViews']
        accessors = self.document['accessors']
        start = len(self.data)
        self.data.extend(values.tobytes())
        views.append(dict(buffer=0, byteOffset=start, byteLength=len(self.data) - start, target=target))
        accessor = dict(bufferView=len(views) - 1, count=count, type=kind,
                        componentType=5126 if values.typecode == 'f' else 5125)
        if bounds:
            accessor.update(min=bounds[0], max=bounds[1])
        accessors.append(accessor)
        return len(accessors) - 1

    def mesh(self, vertices, triangles):
        if not triangles:
            return None
        coordinates = array('f', (coordinate for vertex in vertices for coordinate in vertex))
        indices = array('I', (index for triangle in triangles for index in triangle))
        bounds = (
            [min(coordinates[axis::3]) for axis in range(3)],
            [max(coordinates[axis::3]) for axis in range(3)],
        )
        position = self.accessor(coordinates, count=len(vertices), kind='VEC3', target=34962, bounds=bounds)
        index = self.accessor(indices, count=len(indices), kind='SCALAR', target=34963)
        meshes = self.document['meshes']
        meshes.append({'primitives': [{'attributes': {'POSITION': position}, 'indices': index}]})
        return len(meshes) - 1

    def write(self, directory, name, roots, controls, presentation):
        nodes = self.document['nodes']
        indices = {node['name']: index for index, node in enumerate(nodes)}
        for key, definition in controls.items():
            node = nodes[indices[definition['target_node']]]
            node.setdefault('extras', {})['cosmosys_controls'] = {key: definition}
        contract = dict(schema=CONTRACT, version=CONTRACT_VERSION, rotation_order='XYZ',
                        coordinate_system='glTF Y-up, metres', rest='Offsets from zero pose')
        if presentation:
            contract['presentation'] = presentation
        nodes[roots[0]].setdefault('extras', {})['cosmosys_model'] = contract
        self.document['scenes'] = [{'nodes': roots}]
        self.document['buffers'] = [{'byteLength': len(self.data)}]
        metadata = json.dumps(self.document, ensure_ascii=False, allow_nan=False,
                              separators=(',', ':')).encode('utf8')
        metadata += b' ' * (-len(metadata) % 4)
        path = Path(directory) / f'{name}.glb'
        with path.open('wb') as output:
            output.write(struct.pack('<4sII', b'glTF', 2, 28 + len(metadata) + len(self.data)))
            output.write(struct.pack('<I4s', len(metadata), b'JSON'))
            output.write(metadata)
            output.write(struct.pack('<I4s', len(self.data), b'BIN\0'))
            output.write(self.data)
        path.with_suffix('.yaml').write_text(
            yaml_text(path.name, controls, presentation, source='.FCStd and its controls'), encoding='utf8')
