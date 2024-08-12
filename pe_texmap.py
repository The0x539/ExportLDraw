from __future__ import annotations

import typing

from mathutils import Vector, Matrix
from bmesh.types import BMesh, BMFace

if typing.TYPE_CHECKING:
    from .ldraw_node import LDrawNode

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

    def init_with_target_part_matrix(self, target_part_matrix: Matrix) -> None:
        self.matrix = self.matrix or Matrix.Identity(4)
        (translation, rotation, scale) = (target_part_matrix @ self.matrix).decompose()

        self.box_extents = scale * 0.5

        mirroring = Vector((1, 1, 1))
        if scale.x < 0:
            mirroring.x = -1
            self.box_extents.x = -self.box_extents.x
        if scale.y < 0:
            mirroring.y = -1
            self.box_extents.y = -self.box_extents.y
        if scale.z < 0:
            mirroring.z = -1
            self.box_extents.z = -self.box_extents.z

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
    def build_pe_texmap(ldraw_node: LDrawNode, child_node: LDrawNode) -> PETexmap | None:
        # child_node is a 3 or 4 line
        _params = child_node.line.split()[2:]

        pe_texmap = None
        for p in ldraw_node.pe_tex_info:
            point_min = p.point_min or Vector((0, 0))
            point_max = p.point_max or Vector((1, 1))
            point_diff = p.point_diff or point_max - point_min

            pe_texmap = PETexmap()
            pe_texmap.texture = p.image

            p.init_with_target_part_matrix(ldraw_node.matrix)

            m = p.matrix_inverse or Matrix.Identity(4)
            vertices = [m @ v for v in child_node.vertices]

            # # custom minifig head > 3626tex.dat (has no pe_tex) > 3626texpole.dat (has no uv data)
            if len(_params) == 15:  # use uvs provided in file
                uv_params = _params[len(vertices) * 3:]
                for i in range(len(vertices)):
                    x = round(float(uv_params[i * 2]), 3)
                    y = round(float(uv_params[i * 2 + 1]), 3)
                    uv = Vector((x, y))
                    pe_texmap.uvs.append(uv)

            else:
                # calculate uvs

                ab = vertices[1] - vertices[0]
                bc = vertices[2] - vertices[1]
                face_normal = ab.cross(bc).normalized()

                texture_normal = Vector((0.0, -1, 0.0))
                if abs(face_normal.dot(texture_normal)) < 0.001:
                    continue

                for vert in vertices:
                    # if face is within p.boundingbox
                    # is_intersecting = (p.matrix @ p.bounding_box).interects(vert)

                    uv = Vector((0, 0))
                    uv.x = (vert.x - point_min.x) / point_diff.x
                    uv.y = (vert.z - point_min.y) / point_diff.y

                    pe_texmap.uvs.append(uv)

        return pe_texmap
