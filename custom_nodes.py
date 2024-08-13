import bpy
from typing import Any, cast
from bpy.types import (
    ShaderNodeMath,
    ShaderNodeSeparateXYZ,
    ShaderNodeCombineXYZ,
    NodeSocketFloat,
    NodeSocketVector,
)

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

def project_to_axis_planes() -> None:
    if 'Project to Axis Planes' in bpy.data.node_groups:
        return

    group = bpy.data.node_groups.new('Project to Axis Planes', cast(Any, 'ShaderNodeTree'))

    group.interface.new_socket('In', in_out='INPUT', socket_type='NodeSocketVector')
    group.interface.new_socket('Out', in_out='OUTPUT', socket_type='NodeSocketVector')

    input = group.nodes.new('NodeGroupInput')
    output = group.nodes.new('NodeGroupOutput')

    split = group.nodes.new('ShaderNodeSeparateXYZ')
    split.name = split.label = 'Split'
    group.links.new(input.outputs[0], split.inputs[0])

    [x, y, z] = split.outputs

    facing_x = group.nodes.new('ShaderNodeMath')
    assert isinstance(facing_x, ShaderNodeMath)
    facing_x.name = facing_x.label = 'Facing X'
    facing_x.operation = 'GREATER_THAN'
    group.links.new(x, facing_x.inputs[0])
    assert isinstance(facing_x.inputs[1], NodeSocketFloat)
    facing_x.inputs[1].default_value = 0.5

    facing_y = group.nodes.new('ShaderNodeMath')
    assert isinstance(facing_y, ShaderNodeMath)
    facing_y.name = facing_y.label = 'Facing Y'
    facing_y.operation = 'GREATER_THAN'
    group.links.new(y, facing_y.inputs[0])
    assert isinstance(facing_y.inputs[1], NodeSocketFloat)
    facing_y.inputs[1].default_value = 0.5

    xzy = group.nodes.new('ShaderNodeCombineXYZ')
    xzy.name = xzy.label = 'XZY'
    group.links.new(x, xzy.inputs[0])
    group.links.new(z, xzy.inputs[1])
    group.links.new(y, xzy.inputs[2])

    yzx = group.nodes.new('ShaderNodeCombineXYZ')
    yzx.name = yzx.label = 'YZX'
    group.links.new(y, yzx.inputs[0])
    group.links.new(z, yzx.inputs[1])
    group.links.new(x, yzx.inputs[2])

    if_facing_y = group.nodes.new('ShaderNodeMixRGB')
    if_facing_y.name = if_facing_y.label = 'If'
    group.links.new(facing_y.outputs[0], if_facing_y.inputs[0])

    elif_facing_x = group.nodes.new('ShaderNodeMixRGB')
    elif_facing_x.name = elif_facing_x.label = 'Else'
    group.links.new(facing_x.outputs[0], elif_facing_x.inputs[0])

    group.links.new(xzy.outputs[0], if_facing_y.inputs[1])
    group.links.new(elif_facing_x.outputs[0], if_facing_y.inputs[2])
    group.links.new(yzx.outputs[0], elif_facing_x.inputs[1])
    group.links.new(input.outputs[0], elif_facing_x.inputs[2])

    group.links.new(if_facing_y.outputs[0], output.inputs[0])
