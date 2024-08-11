import mathutils


class PETexInfo:
    def __init__(self, point_min=None, point_max=None, point_diff=None, box_extents=None, matrix=None, matrix_inverse=None, image=None):
        self.point_min = point_min  # bottom corner of bounding box
        self.point_max = point_max  # top corner of bounding box
        self.point_diff = point_diff  # center of bounding box
        self.box_extents = box_extents
        self.matrix = matrix
        self.matrix_inverse = matrix_inverse
        self.image = image


class PETexmap:
    def __init__(self):
        self.texture = None
        self.uvs = []

    def uv_unwrap_face(self, bm, face):
        uv_layer = bm.loops.layers.uv.verify()
        uvs = {}
        for i, loop in enumerate(face.loops):
            p = loop.vert.co.copy().freeze()
            if p not in uvs:
                uvs[p] = self.uvs[i]
            loop[uv_layer].uv = uvs[p]

    @staticmethod
    def build_pe_texmap(ldraw_node, child_node, vertices):
        # child_node is a 3 or 4 line
        _params = child_node.line.split()[2:]

        pe_texmap = None
        for p in ldraw_node.pe_tex_info:
            point_min = p.point_min or mathutils.Vector((0, 0))
            point_max = p.point_max or mathutils.Vector((1, 1))
            point_diff = p.point_diff or point_max - point_min

            # if we have uv data and a pe_tex_info, otherwise pass
            # # custom minifig head > 3626tex.dat (has no pe_tex) > 3626texpole.dat (has no uv data)
            if len(_params) == 15:  # use uvs provided in file
                pe_texmap = PETexmap()
                pe_texmap.texture = p.image

                uv_params = _params[len(vertices) * 3:]
                for i in range(len(vertices)):
                    x = round(float(uv_params[i * 2]), 3)
                    y = round(float(uv_params[i * 2 + 1]), 3)
                    uv = mathutils.Vector((x, y))
                    pe_texmap.uvs.append(uv)

            else:
                # calculate uvs
                pe_texmap = PETexmap()
                pe_texmap.texture = p.image

                face_normal = (vertices[1] - vertices[0]).cross(vertices[2] - vertices[1])
                face_normal.normalize()

                texture_normal = mathutils.Vector((0.0, -1, 0.0))
                normal_dot = face_normal.dot(texture_normal)
                face_normal_within_texture_normal = abs(normal_dot) >= 1.0 / 1000.0

                for vert in vertices:
                    # if face is within p.boundingbox
                    # is_intersecting = (p.matrix @ p.bounding_box).interects(vert)

                    # TODO: only add uvs for faces that actually have the texture
                    uv = mathutils.Vector((0, 0))
                    if face_normal_within_texture_normal:  # and is_intersecting:
                        uv.x = (vert.x - point_min.x) / point_diff.x
                        uv.y = (vert.z - point_min.y) / point_diff.y
                        if normal_dot > 0:
                            uv.y = 1 - uv.y
                    pe_texmap.uvs.append(uv)

        return pe_texmap
