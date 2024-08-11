class FaceData:
    """
    Raw vertex information
    """

    def __init__(self, vertices, color_code, texmap=None, pe_texmap=None):
        self.vertices = vertices
        self.color_code = color_code
        self.texmap = texmap
        self.pe_texmap = pe_texmap

    # https://github.com/rredford/LdrawToObj/blob/802924fb8d42145c4f07c10824e3a7f2292a6717/LdrawData/LdrawToData.cs#L219
    # https://github.com/rredford/LdrawToObj/blob/802924fb8d42145c4f07c10824e3a7f2292a6717/LdrawData/LdrawToData.cs#L260
    @staticmethod
    def handle_vertex_winding(child_node, matrix, winding):
        # matrix = matrix @ matrices.gap_scale_matrix

        vertices = [matrix @ v for v in child_node.vertices]

        if winding == "CW":
            vertices = vertices[::-1]

        if len(vertices) == 4:
            FaceData.__fix_bowties(vertices)

        return vertices

    # handle bowtie quadrilaterals - 6582.dat
    # https://github.com/TobyLobster/ImportLDraw/pull/65/commits/3d8cebee74bf6d0447b616660cc989e870f00085
    @staticmethod
    def __fix_bowties(vertices):
        nA = (vertices[1] - vertices[0]).cross(vertices[2] - vertices[0])
        nB = (vertices[2] - vertices[1]).cross(vertices[3] - vertices[1])
        nC = (vertices[3] - vertices[2]).cross(vertices[0] - vertices[2])
        if nA.dot(nB) < 0:
            vertices[2], vertices[3] = vertices[3], vertices[2]
        elif nB.dot(nC) < 0:
            vertices[2], vertices[1] = vertices[1], vertices[2]


class GeometryData:
    """
    Raw mesh data used to build the final mesh.
    """

    def __init__(self):
        self.key = None
        self.file = None
        self.bfc_certified = None
        self.edge_data = []
        self.face_data = []
        self.line_data = []

    def add_edge_data(self, vertices, color_code):
        self.edge_data.append(FaceData(
            vertices=vertices,
            color_code=color_code,
        ))

    def add_face_data(self, vertices, color_code, texmap=None, pe_texmap=None):
        self.face_data.append(FaceData(
            vertices=vertices,
            color_code=color_code,
            texmap=texmap,
            pe_texmap=pe_texmap,
        ))

    def add_line_data(self, vertices, color_code):
        self.line_data.append(FaceData(
            vertices=vertices,
            color_code=color_code,
        ))
