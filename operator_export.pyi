import bpy
from bpy_extras.io_utils import ExportHelper
from typing import Literal

class EXPORT_OT_do_ldraw_export(bpy.types.Operator, ExportHelper):
    filename_ext: Literal['.dat', '.ldr']
    filter_glob: str
    ldraw_path: str
    studio_ldraw_path: str
    studio_custom_parts_path: str
    use_alt_colors: bool
    selection_only: bool
    recalculate_normals: bool
    triangulate: bool
    remove_doubles: bool
    merge_distance: float
    ngon_handling: Literal['skip', 'triangulate']


def build_export_menu(self, context):
    ...

def register() -> None:
    ...

def unregister() -> None:
    ...
