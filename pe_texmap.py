from __future__ import annotations

import typing

from mathutils import Vector, Matrix, Quaternion
from bmesh.types import BMesh, BMFace

if typing.TYPE_CHECKING:
    from .ldraw_node import LDrawNode
    from .ldraw_meta import Winding

class PETexInfo:
    def __init__(
        self,
        point_min: Vector | None = None,
        point_max: Vector | None = None,
        point_diff: Vector | None = None,
        box_extents: Vector | None = None,
        matrix: Matrix | None = None,
        matrix_inverse: Matrix | None = None,
        image: None = None,
    ) -> None:
        self.point_min = point_min  # bottom corner of bounding box
        self.point_max = point_max  # top corner of bounding box
        self.point_diff = point_diff  # center of bounding box
        self.box_extents = box_extents
        self.matrix = matrix
        self.matrix_inverse = matrix_inverse
        self.image = image

    def clone(self) -> PETexInfo:
        return PETexInfo(self.point_min, self.point_max, self.point_diff, self.box_extents, self.matrix, self.matrix_inverse, self.image)

    def init_with_target_part_matrix(self, target_part_matrix: Matrix) -> None:
        self.matrix = self.matrix or Matrix.Identity(4)
        (translation, rotation, scale) = (target_part_matrix @ self.matrix).decompose()

        self.box_extents = scale * 0.5

        mirroring = Vector((1, 1, 1))
        for dim in range(3):
            if scale[dim] < 0:
                mirroring[dim] *= -1
                self.box_extents[dim] *= -1

        rhs = Matrix.LocRotScale(translation, rotation, mirroring)
        self.matrix = (target_part_matrix.inverted() @ rhs).freeze()
        self.matrix_inverse = self.matrix.inverted().freeze()

class PETexmap:
    def __init__(self) -> None:
        self.texture = None
        self.uvs: list[Vector] = []

    def uv_unwrap_face(self, bm: BMesh, face: BMFace) -> None:
        if not self.uvs:
            return

        uv_layer = bm.loops.layers.uv.verify()
        uvs = {}
        for i, loop in enumerate(face.loops):
            p = loop.vert.co.copy().freeze()
            if p not in uvs:
                uvs[p] = self.uvs[i]
            loop[uv_layer].uv = uvs[p]

    @staticmethod
    def build_pe_texmap(
        ldraw_node: LDrawNode,
        child_node: LDrawNode,
        winding: Winding | None,
    ) -> PETexmap | None:
        if not ldraw_node.pe_tex_info:
            return None
        elif len(ldraw_node.pe_tex_info) > 1:
            raise NotImplementedError()
        else:
            p = ldraw_node.pe_tex_info[0].clone()

        pe_texmap = PETexmap()
        pe_texmap.texture = p.image

        # child_node is a 3 or 4 line
        _params = child_node.line.split()[2:]

        # # custom minifig head > 3626tex.dat (has no pe_tex) > 3626texpole.dat (has no uv data)
        if len(_params) == 15:  # use uvs provided with polygon
            n = len(child_node.vertices)
            uv_params = _params[n * 3:]
            for i in range(n):
                x = round(float(uv_params[i * 2]), 3)
                y = round(float(uv_params[i * 2 + 1]), 3)
                uv = Vector((x, y))
                pe_texmap.uvs.append(uv)

            return pe_texmap

        elif p.matrix_inverse:  # calculate uvs by projecting transformed texture onto polygon
            assert p.point_min is not None
            assert p.point_max is not None
            assert p.point_diff is not None
            assert p.box_extents is not None

            p.init_with_target_part_matrix(ldraw_node.matrix)

            vertices = [p.matrix_inverse @ v for v in child_node.vertices]
            if winding == 'CW':
                vertices.reverse()

            # if not intersect(vertices, p.box_extents):
                # return None

            ab = vertices[1] - vertices[0]
            bc = vertices[2] - vertices[1]
            face_normal = ab.cross(bc).normalized()

            texture_normal = Vector((0.0, -1, 0.0)) # "down"
            if abs(face_normal.dot(texture_normal)) < 0.001:
                return None

            for vert in vertices:
                # TODO: there's still the "atlas" min/max/diff, which seems to be 0.05:0.95
                u = (vert.x - p.point_min.x) / p.point_diff.x
                v = (vert.z - p.point_min.y) / p.point_diff.y
                uv = Vector((u, v))
                pe_texmap.uvs.append(uv)

            return pe_texmap
        else:
            return None

def intersect(triangle: list[Vector], box_extents: Vector) -> bool:
    a, b, c = triangle[:3]
    edges = [b - a, c - b, a - c]
    normal = edges[0].cross(edges[1])
    num: float
    for i in range(3):
        for j in range(3):
            rhs: Vector
            e, be = edges[j], box_extents
            if i == 0:
                rhs = Vector((0, -e.z, e.y))
                num = be.y * abs(e.z) + be.z * abs(e.y)
            elif i == 1:
                rhs = Vector((e.z, 0, -e.x))
                num = be.x * abs(e.z) + be.z * abs(e.x)
            else:
                rhs = Vector((-e.y, e.x, 0))
                num = be.x * abs(e.y) + be.y * abs(e.x)

            dot_products = [v.dot(rhs) for v in (a, b, c)]
            miximum = max(-max(dot_products), min(dot_products))
            if miximum > num:
                return False

    for dim in range(3):
        coords = (a[dim], b[dim], c[dim])
        if max(coords) < -box_extents[dim] or min(coords) > box_extents[dim]:
            return False

    abs_normal = Vector(abs(v) for v in normal.to_tuple())
    return normal.dot(a) <= abs_normal.dot(box_extents)
