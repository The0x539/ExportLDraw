import bpy
from typing import Literal

def set_props(obj, ldraw_file, color_code):
    ...

def get_header_lines(obj, is_model=False):
    ...

class Object(bpy.types.Object):
    ldraw_props: LDrawProps

class LDrawProps(bpy.types.PropertyGroup):
    filename: str
    description: str
    name: str
    author: str
    part_type: Literal[
        'Model',
        'Unofficial_Model',
        'Part',
        'Unofficial_Part',
        'Shortcut',
        'Unofficial_Shortcut',
        'Subpart',
        'Unofficial_Subpart',
        'Primitive',
        'Unofficial_Primitive',
        'Unknown',
    ]
    actual_part_type: str
    optional_qualifier: str
    update_date: str
    license: str
    category:  str
    color_code: str
    invert_import_scale_matrix: bool
    invert_gap_scale_matrix: bool
    export_polygons: bool
    export_shade_smooth: bool
    export_precision: int


def register() -> None:
    ...

def unregister() -> None:
    ...
