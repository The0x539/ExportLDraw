import mathutils

from bmesh.types import BMesh, BMFace
from mathutils import Vector

import math
import uuid
from typing import Literal

from . import helpers

texmap_prefix = "0 !: "


def is_texmap_line(line: str) -> bool:
    return line.startswith(texmap_prefix)


def clean_line(line: str) -> str:
    return line.replace(texmap_prefix, "")

TexMapMethod = Literal['PLANAR', 'CYLINDRICAL', 'SPHERICAL']

# https://github.com/trevorsandy/lpub3d/blob/e7c39cd3df518cf16521dc2c057a9f125cc3b5c3/lclib/common/lc_meshloader.h#L56
# https://github.com/trevorsandy/lpub3d/blob/e7c39cd3df518cf16521dc2c057a9f125cc3b5c3/lclib/common/lc_meshloader.cpp#L12
# https://github.com/trevorsandy/lpub3d/blob/e7c39cd3df518cf16521dc2c057a9f125cc3b5c3/lclib/common/lc_meshloader.cpp#L1486
# https://stackoverflow.com/questions/53970131/how-to-find-the-clockwise-angle-between-two-vectors-in-python#53970746
class TexMap:
    def __init__(self, method: TexMapMethod | None = None) -> None:
        self.id = str(uuid.uuid4())
        self.method = method
        self.parameters: \
            tuple[Vector, Vector, Vector] \
            | tuple[Vector, Vector, Vector, float] \
            | tuple[Vector, Vector, Vector, float, float] \
            | None = None
        self.texture = None
        self.glossmap = None

    def is_planar(self) -> bool:
        return self.method == 'PLANAR'

    def is_cylindrical(self) -> bool:
        return self.method == 'CYLINDRICAL'

    def is_spherical(self) -> bool:
        return self.method == 'SPHERICAL'

    def uv_unwrap_face(self, bm: BMesh, face: BMFace) -> None:
        if self.is_planar():
            self.__map_planar(bm, face)
        elif self.is_cylindrical():
            self.__map_cylindrical(bm, face)
        elif self.is_spherical():
            self.__map_spherical(bm, face)

    def uv_unwrap_face_basic(self, bm: BMesh, face: BMFace) -> None:
        uv_layer = bm.loops.layers.uv.verify()
        uvs = {}
        for i, loop in enumerate(face.loops):
            p = loop.vert.co.copy().freeze()
            if p not in uvs:
                uv = [0, 0]
                uvs[p] = uv
            loop[uv_layer].uv = uvs[p]

    # negative v because blender uv starts at bottom left of image, LDraw orientation of up=-y so use top left
    def __map_planar(self, bm: BMesh, face: BMFace) -> None:
        assert self.parameters is not None
        a = self.parameters[0]
        b = self.parameters[1]
        c = self.parameters[2]

        ab = b - a
        bc = c - b
        ac = c - a

        # texmap_cross = ab.cross(ac)
        # texmap_normal = texmap_cross / texmap_cross.length

        p1_length = ab.length
        p1_normal = ab / p1_length

        p2_length = ac.length
        p2_normal = ac / p2_length

        # https://blender.stackexchange.com/a/53808
        # https://blender.stackexchange.com/questions/53709/bmesh-how-to-map-vertex-based-uv-coordinates-to-loops
        # https://blenderartists.org/t/solved-how-to-uv-unwrap-and-scale-uvs-with-python-while-in-object-mode/1115953/2

        # DISTANCE BETWEEN POINT AND PLANE
        # https://stackoverflow.com/a/3863777
        # float dist = dotProduct(p.normal, (vectorSubtract(point, p.point)));
        # https://mathinsight.org/distance_point_plane
        # absolute value of the dot product of the normal and
        # the length between the point and a point on the plane
        # TODO: UV PROJECT HERE
        uv_layer = bm.loops.layers.uv.verify()
        uvs = {}
        for i, loop in enumerate(face.loops):
            p = loop.vert.co.copy().freeze()
            if p not in uvs:
                du = p1_normal.dot(p - a) / p1_length
                dv = p2_normal.dot(p - c) / p2_length
                # - up_length to move uv to bottom left in blender
                uv = [du, -dv]
                uvs[p] = uv
            loop[uv_layer].uv = uvs[p]

    def __map_cylindrical(self, bm: BMesh, face: BMFace) -> None:
        assert self.parameters is not None
        assert len(self.parameters) == 4
        a = self.parameters[0]
        b = self.parameters[1]
        c = self.parameters[2]
        angle1 = self.parameters[3]

        up = a - b
        up_length = up.length
        front = (c - b).normalized()
        plane_1_normal = up / up_length
        plane_2_normal = front.cross(up).normalized()
        front_plane = mathutils.Vector(front.to_tuple() + (-front.dot(b),))
        up_length = up_length
        plane_1 = mathutils.Vector(plane_1_normal.to_tuple() + (-plane_1_normal.dot(b),))
        plane_2 = mathutils.Vector(plane_2_normal.to_tuple() + (-plane_2_normal.dot(b),))
        angle_1 = 360.0 / angle1

        uv_layer = bm.loops.layers.uv.verify()
        uvs = {}
        for i, loop in enumerate(face.loops):
            p = loop.vert.co.copy().freeze()
            if p not in uvs:
                # - up_length to move uv to bottom left in blender
                dot_plane_1 = mathutils.Vector((p[0], p[1] - up_length, p[2],) + (1.0,)).dot(plane_1)
                point_in_plane_1 = p - mathutils.Vector((plane_1[0], plane_1[1], plane_1[2],)) * dot_plane_1
                dot_front_plane = point_in_plane_1.dot(front_plane)
                dot_plane_2 = mathutils.Vector(point_in_plane_1.to_tuple() + (1.0,)).dot(plane_2)

                _angle_1 = math.atan2(dot_plane_2, dot_front_plane) / math.pi * angle_1
                du = helpers.clamp(0.5 + 0.5 * _angle_1, 0, 1)
                dv = dot_plane_1 / up_length
                uv = [du, -dv]
                uvs[p] = uv
            loop[uv_layer].uv = uvs[p]

    def __map_spherical(self, bm: BMesh, face: BMFace) -> None:
        assert self.parameters is not None
        assert len(self.parameters) == 5
        a = self.parameters[0]
        b = self.parameters[1]
        c = self.parameters[2]
        angle1 = self.parameters[3]
        angle2 = self.parameters[4]

        front = (b - a).normalized()
        plane_1_normal = front.cross(c - a).normalized()
        plane_2_normal = plane_1_normal.cross(front).normalized()
        front_plane = mathutils.Vector(front.to_tuple() + (-front.dot(a),))
        center = a
        plane_1 = mathutils.Vector(plane_1_normal.to_tuple() + (-plane_1_normal.dot(a),))
        plane_2 = mathutils.Vector(plane_2_normal.to_tuple() + (-plane_2_normal.dot(a),))
        angle_1 = 360.0 / angle1
        angle_2 = 180.0 / angle2

        uv_layer = bm.loops.layers.uv.verify()
        uvs = {}
        for i, loop in enumerate(face.loops):
            p = loop.vert.co.copy().freeze()
            if p not in uvs:
                vertex_direction = p - center

                dot_plane_1 = mathutils.Vector((p[0], p[1], p[2],) + (1.0,)).dot(plane_1)
                point_in_plane_1 = p - mathutils.Vector((plane_1[0], plane_1[1], plane_1[2],)) * dot_plane_1
                dot_front_plane = point_in_plane_1.dot(front_plane)
                dot_plane_2 = point_in_plane_1.dot(plane_2)

                _angle_1 = math.atan2(dot_plane_2, dot_front_plane) / math.pi * angle_1
                du = 0.5 + 0.5 * _angle_1
                _angle_2 = math.asin(dot_plane_1 / vertex_direction.length) / math.pi * angle_2
                # -0.5 instead of 0.5 to move uv to bottom left in blender
                dv = -0.5 - _angle_2

                uv = [du, -dv]
                uvs[p] = uv
            loop[uv_layer].uv = uvs[p]
