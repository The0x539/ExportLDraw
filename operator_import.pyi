import bpy
from typing import Literal

class IMPORT_OT_do_ldraw_import(bpy.types.Operator):
    filename_ext: str
    filter_glob: str
    filepath: str
    ldraw_path: str
    studio_ldraw_path: str
    studio_custom_parts_path: str
    prefer_studio: bool
    case_sensitive_filesystem: bool
    prefer_unofficial: bool
    resolution: Literal['Low', 'Standard', 'High']
    use_alt_colors: bool
    remove_doubles: bool
    merge_distance: float
    shade_smooth: bool
    display_logo: bool
    chosen_logo: Literal['logo', 'logo2', 'logo3', 'logo4', 'logo5', 'high-contrast']
    smooth_type: Literal['edge_smooth', 'auto_smooth', 'bmesh_split']
    no_studs: bool
    parent_to_empty: bool
    scale_strategy: Literal['mesh', 'object']
    import_scale: float
    make_gaps: bool
    gap_scale: float
    meta_bfc: bool
    meta_texmap: bool
    meta_print_write: bool
    meta_group: bool
    meta_step: bool
    meta_step_groups: bool
    meta_clear: bool
    meta_pause: bool
    meta_save: bool
    set_end_frame: bool
    frames_per_step: int
    starting_step_frame: int
    set_timeline_markers: bool
    import_edges: bool
    use_freestyle_edges: bool
    treat_shortcut_as_model: bool
    recalculate_normals: bool
    triangulate: bool
    profile: bool
    bevel_edges: bool
    bevel_weight: float
    bevel_width: float
    bevel_segments: int


def build_import_menu(self, context):
    ...

def register():
    ...

def unregister():
    ...
