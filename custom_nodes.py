import bpy
from typing import Any, cast

def uv_degradation() -> None:
    if 'UV Degradation' in bpy.data.node_groups:
        return

    group = bpy.data.node_groups.new('UV Degradation', cast(Any, 'ShaderNodeTree'))

    for (name, ty) in (
        ('FromColor', 'Color'),
        ('ToColor', 'Color'),
        ('Levels', 'Int'),
        ('MinColorRatio', 'Float'),
        ('MaxColorRatio', 'Float'),
        ('MinRoughness', 'Float'),
        ('MaxRoughness', 'Float'),
        ('Strength', 'Float'),
        ('enable', 'Bool'),
    ):
        group.interface.new_socket(name, in_out='INPUT', socket_type='NodeSocket' + ty)

    group.interface.new_socket('OutColor', in_out='OUTPUT', socket_type='NodeSocketColor')
    group.interface.new_socket('OutRoughness', in_out='OUTPUT', socket_type='NodeSocketFloat')

    input = group.nodes.new('NodeGroupInput')
    output = group.nodes.new('NodeGroupOutput')

    # temporary
    group.links.new(input.outputs['FromColor'], output.inputs['OutColor'])
