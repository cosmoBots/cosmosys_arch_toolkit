"""Import static glTF triangles as FreeCAD meshes, without converting them to BRep faces."""
import base64
import json
import math
from pathlib import Path
import struct
from urllib.parse import unquote, urlsplit

import FreeCAD as App
import Mesh

from exchange import read_glb_json

COMPONENT_FORMATS = {5121: 'B', 5123: 'H', 5125: 'I', 5126: 'f'}


def import_data(path):
    binary = None
    if path.suffix.lower() == '.glb':
        document = read_glb_json(path)
        with path.open('rb') as stream:
            stream.seek(12)
            size = struct.unpack('<I', stream.read(4))[0]
            stream.seek(20 + size)
            chunk = stream.read(8)
            if len(chunk) == 8:
                size, kind = struct.unpack('<I4s', chunk)
                if kind == b'BIN\0':
                    binary = stream.read(size)
    else:
        document = json.loads(path.read_text(encoding='utf8'))
    if len(document.get('scenes', [])) != 1 or document.get('extensionsRequired'):
        raise ValueError('Se necesita una escena glTF sin extensiones obligatorias.')
    if document.get('skins') or document.get('animations'):
        raise ValueError('Se necesita un glTF estático, sin skin ni animaciones.')
    buffers = []
    for index, buffer in enumerate(document.get('buffers', [])):
        uri = buffer.get('uri')
        if uri is None and index == 0 and binary is not None:
            data = binary
        elif uri and uri.startswith('data:') and ';base64,' in uri:
            data = base64.b64decode(uri.split(',', 1)[1], validate=True)
        else:
            url = urlsplit(uri or '')
            if url.scheme or url.netloc or not url.path or Path(unquote(url.path)).is_absolute():
                raise ValueError('Los buffers glTF externos deben ser archivos locales relativos.')
            data = (path.parent / unquote(url.path)).read_bytes()
        if len(data) < buffer['byteLength']:
            raise ValueError('Buffer glTF truncado.')
        buffers.append(memoryview(data)[:buffer['byteLength']])
    return document, buffers


def accessor_data(document, buffers, index, kind):
    accessor = document['accessors'][index]
    component = accessor['componentType']
    if (accessor['type'] != kind or 'sparse' in accessor or accessor.get('normalized') or
            (component == 5126) != (kind == 'VEC3') or component not in COMPONENT_FORMATS):
        raise ValueError('Accessor glTF no soportado para vértices o índices.')
    view = document['bufferViews'][accessor['bufferView']]
    data = buffers[view['buffer']]
    start = view.get('byteOffset', 0)
    end = start + view['byteLength']
    offset = start + accessor.get('byteOffset', 0)
    count = accessor['count']
    reader = struct.Struct('<' + COMPONENT_FORMATS[component] * (3 if kind == 'VEC3' else 1))
    stride = view.get('byteStride', reader.size)
    if (count <= 0 or stride < reader.size or not 0 <= start <= offset or
            offset + (count - 1) * stride + reader.size > end or end > len(data)):
        raise ValueError('Rango de accessor glTF inválido.')
    if stride == reader.size:
        return reader.iter_unpack(data[offset:offset + count * stride])
    return (reader.unpack_from(data, offset + i * stride) for i in range(count))


def gltf_placement(node, inherited):
    if 'matrix' in node:
        matrix = node['matrix']
        if len(matrix) != 16 or any(not math.isfinite(value) for value in matrix):
            raise ValueError('Matriz glTF inválida.')
        x, y, z = (App.Vector(*matrix[start:start + 3]) for start in (0, 4, 8))
        if (any(abs(matrix[i] - expected) > 1e-6 for i, expected in ((3, 0), (7, 0), (11, 0), (15, 1)))
                or abs(x.Length - 1) > 1e-6 or abs(y.Length - 1) > 1e-6
                or abs(x.dot(y)) > 1e-6 or (x.cross(y) - z).Length > 1e-6):
            raise ValueError('Se necesita una matriz glTF rígida. Guarda las escalas como TRS o aplícalas.')
        rotation = App.Rotation(x, y, z, 'ZXY')
        translation = matrix[12:15]
        scale = (1, 1, 1)
    else:
        quaternion = node.get('rotation', (0, 0, 0, 1))
        if len(quaternion) != 4 or not all(math.isfinite(value) for value in quaternion) or not any(quaternion):
            raise ValueError('Cuaternión glTF inválido.')
        rotation = App.Rotation(*quaternion)
        translation = node.get('translation', (0, 0, 0))
        scale = node.get('scale', (1, 1, 1))
    if len(scale) != 3 or any(not math.isfinite(value) or value <= 0 for value in scale):
        raise ValueError('Las escalas glTF deben ser finitas y positivas.')
    rx, ry, rz, rw = rotation.Q
    placement = App.Placement(cad_point(inherited.multiply(App.Vector(*translation))),
                              App.Rotation(rx, -rz, ry, rw))
    scaling = App.Matrix()
    scaling.A11, scaling.A22, scaling.A33 = scale
    r = rotation.toMatrix()
    # Carry the non-rigid part into the geometry and descendant positions,
    # keeping the original rotation as the editable FreeCAD Placement.
    residual = r.inverse().multiply(inherited).multiply(r).multiply(scaling)
    return placement, residual


def cad_point(vector):
    if not all(math.isfinite(value) for value in (vector.x, vector.y, vector.z)):
        raise ValueError('Coordenadas glTF no finitas.')
    return App.Vector(vector.x * 1000, -vector.z * 1000, vector.y * 1000)


def create_mesh(document, buffers, index, residual):
    facets = []
    for primitive in document['meshes'][index]['primitives']:
        if primitive.get('mode', 4) != 4 or 'targets' in primitive:
            raise ValueError('Se necesitan primitivas glTF de triángulos sin morph targets.')
        positions = accessor_data(document, buffers, primitive['attributes']['POSITION'], 'VEC3')
        points = [cad_point(residual.multiply(App.Vector(*point))) for point in positions]
        if 'indices' in primitive:
            indices = [value for value, in accessor_data(document, buffers, primitive['indices'], 'SCALAR')]
        else:
            indices = range(len(points))
        if len(indices) % 3 or any(index >= len(points) for index in indices):
            raise ValueError('Índices de triángulos glTF inválidos.')
        facets.extend(tuple(points[index] for index in indices[start:start + 3])
                      for start in range(0, len(indices), 3))
    if not facets:
        raise ValueError('La malla glTF no contiene triángulos.')
    return Mesh.Mesh(facets), len(facets)


def import_gltf(path, freecad_document):
    document, buffers = import_data(path)
    visited = set()
    names = set()
    source_triangles = 0

    def label_for(name):
        label = name
        suffix = 2
        while label in names:
            label = f'{name} ({suffix})'
            suffix += 1
        names.add(label)
        return label

    def visit(index, parent, inherited):
        nonlocal source_triangles
        if index in visited:
            raise ValueError('La jerarquía glTF debe ser un árbol con una sola referencia por nodo.')
        visited.add(index)
        node = document['nodes'][index]
        label = label_for(node.get('name') or f'Node{index}')
        try:
            placement, residual = gltf_placement(node, inherited)
        except (TypeError, ValueError) as error:
            raise ValueError(f'{label}: {error}') from error
        children = node.get('children', [])
        make = parent.newObject if parent else freecad_document.addObject
        if children or 'mesh' not in node:
            item = make('App::Part', 'Group')
            if 'mesh' in node:
                mesh = item.newObject('Mesh::Feature', 'Surface')
                mesh.Label = label_for(f'{label} (malla)')
            for child in children:
                visit(child, item, residual)
        else:
            item = make('Mesh::Feature', 'Surface')
            mesh = item
        if 'mesh' in node:
            geometry, count = create_mesh(document, buffers, node['mesh'], residual)
            mesh.Mesh = geometry
            source_triangles += count
        item.Label, item.Placement = label, placement
        if App.GuiUp:
            item.ViewObject.show()
            if 'mesh' in node and mesh is not item:
                mesh.ViewObject.show()

    for root in document['scenes'][0]['nodes']:
        visit(root, None, App.Matrix())
    return source_triangles
