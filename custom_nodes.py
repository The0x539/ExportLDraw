import bpy
from typing import Any, cast, TypeVar, Type
from bpy.types import (
    ShaderNodeMath,
    ShaderNodeSeparateXYZ,
    ShaderNodeTexCoord,
    ShaderNodeCombineXYZ,
    ShaderNodeObjectInfo,
    ShaderNodeMix,
    ShaderNodeMixRGB,
    ShaderNodeMapRange,
    NodeSocketFloat,
    NodeSocketVector,
    NodeTreeInterfaceSocketInt,
    NodeGroupInput,
    NodeGroupOutput,
    Node,
    ShaderNodeTree,
)

from . import arrange

def uv_degradation() -> None:
    if 'UV Degradation' in bpy.data.node_groups:
        return

    group = bpy.data.node_groups.new('UV Degradation', cast(Any, 'ShaderNodeTree'))
    assert isinstance(group, ShaderNodeTree)

    for (name, ty) in (
        ('FromColor', 'Color'),
        ('ToColor', 'Color'),
        ('MinColorRatio', 'Float'),
        ('MaxColorRatio', 'Float'),
        ('MinRoughness', 'Float'),
        ('MaxRoughness', 'Float'),
        ('Strength', 'Float'),
        ('enable', 'Bool'), # TODO: respect this value
    ):
        group.interface.new_socket(name, in_out='INPUT', socket_type='NodeSocket' + ty)

    levels = group.interface.new_socket('Levels', in_out='INPUT', socket_type='NodeSocketInt')
    assert isinstance(levels, NodeTreeInterfaceSocketInt)
    levels.min_value = 1
    levels.default_value = 4
    levels.max_value = 10
    
    group.interface.new_socket('OutColor', in_out='OUTPUT', socket_type='NodeSocketColor')
    group.interface.new_socket('OutRoughness', in_out='OUTPUT', socket_type='NodeSocketFloat')

    input = new_node(group, NodeGroupInput)
    output = new_node(group, NodeGroupOutput)

    object_info = new_node(group, ShaderNodeObjectInfo)

    # step_1 = rand() * Levels
    step_1 = new_math(group, 'MULTIPLY')
    group.links.new(object_info.outputs['Random'], step_1.inputs[0])
    group.links.new(input.outputs['Levels'], step_1.inputs[1])

    # step_2 = floor(step_1)
    step_2 = new_math(group, 'FLOOR')
    group.links.new(step_1.outputs[0], step_2.inputs[0])

    # step_3 = Levels - 1
    step_3 = new_math(group, 'SUBTRACT')
    group.links.new(input.outputs['Levels'], step_3.inputs[0])
    assert isinstance(step_3.inputs[1], NodeSocketFloat)
    step_3.inputs[1].default_value = 1

    # t = clamp(step_2 / step_3, 0, 1)
    # the blender math node uses safe division, so if Levels = 1, t = 0 with no error
    t = new_math(group, 'DIVIDE', 't')
    t.use_clamp = True
    group.links.new(step_2.outputs[0], t.inputs[0])
    group.links.new(step_3.outputs[0], t.inputs[1])

    # color_ratio = map_range(t, 0:1, MinColorRatio:MaxColorRatio)
    color_ratio = new_node(group, ShaderNodeMapRange, 'ColorRatio')
    color_ratio.clamp = False
    group.links.new(t.outputs[0], color_ratio.inputs['Value'])
    group.links.new(input.outputs['MinColorRatio'], color_ratio.inputs['To Min'])
    group.links.new(input.outputs['MaxColorRatio'], color_ratio.inputs['To Max'])
    
    # color_t = color_ratio * Strength
    color_t = new_math(group, 'MULTIPLY', 'color_t')
    group.links.new(color_ratio.outputs[0], color_t.inputs[0])
    group.links.new(input.outputs['Strength'], color_t.inputs[1])

    input2 = new_node(group, NodeGroupInput, 'Group Input (Ranges)')

    # out_color = interp(from_color, to_color, color_t)
    out_color = new_node(group, ShaderNodeMix, 'OutColor')
    out_color.data_type = 'RGBA'
    group.links.new(color_t.outputs[0], out_color.inputs[0])
    group.links.new(input2.outputs['FromColor'], out_color.inputs['A'])
    group.links.new(input2.outputs['ToColor'], out_color.inputs['B'])

    # t_strength = t * strength
    t_strength = new_math(group, 'MULTIPLY', 't * Strength')
    group.links.new(t.outputs[0], t_strength.inputs[0])
    group.links.new(input.outputs['Strength'], t_strength.inputs[1])

    # out_roughness = map_range(t_strength, 0:1, MinRoughness:MaxRoughness)
    out_roughness = new_node(group, ShaderNodeMapRange, 'OutRoughness')
    out_roughness.clamp = False
    group.links.new(t_strength.outputs[0], out_roughness.inputs['Value'])
    group.links.new(input2.outputs['MinRoughness'], out_roughness.inputs['To Min'])
    group.links.new(input2.outputs['MaxRoughness'], out_roughness.inputs['To Max'])

    input3 = new_node(group, NodeGroupInput, 'Group Input (Toggles)')

    toggle_out_color = new_node(group, ShaderNodeMix, 'Color Toggle')
    toggle_out_color.data_type = 'RGBA'
    group.links.new(input3.outputs['enable'], toggle_out_color.inputs[0])
    group.links.new(input3.outputs['FromColor'], toggle_out_color.inputs['A'])
    group.links.new(out_color.outputs['Result'], toggle_out_color.inputs['B'])

    toggle_out_roughness = new_node(group, ShaderNodeMix, 'Roughness Toggle')
    toggle_out_roughness.data_type = 'FLOAT'
    group.links.new(input3.outputs['enable'], toggle_out_roughness.inputs[0])
    group.links.new(input3.outputs['MinRoughness'], toggle_out_roughness.inputs['A'])
    group.links.new(out_roughness.outputs[0], toggle_out_roughness.inputs['B'])

    group.links.new(toggle_out_color.outputs['Result'], output.inputs['OutColor'])
    group.links.new(toggle_out_roughness.outputs['Result'], output.inputs['OutRoughness'])

    arrange.nodes_iterate(group)


def project_to_axis_planes() -> None:
    if 'Project to Axis Planes' in bpy.data.node_groups:
        return

    group = bpy.data.node_groups.new('Project to Axis Planes', cast(Any, 'ShaderNodeTree'))
    assert isinstance(group, ShaderNodeTree)

    group.interface.new_socket('In', in_out='INPUT', socket_type='NodeSocketVector')
    group.interface.new_socket('Out', in_out='OUTPUT', socket_type='NodeSocketVector')

    input = group.nodes.new('NodeGroupInput')
    output = group.nodes.new('NodeGroupOutput')

    tex_coord = new_node(group, ShaderNodeTexCoord)

    split_normal = new_node(group, ShaderNodeSeparateXYZ, 'Split Normal')
    group.links.new(tex_coord.outputs['Normal'], split_normal.inputs[0])

    abs_x = new_math(group, 'ABSOLUTE', 'Abs(X)')
    group.links.new(split_normal.outputs['X'], abs_x.inputs[0])
    
    abs_y = new_math(group, 'ABSOLUTE', 'Abs(Y)')
    group.links.new(split_normal.outputs['Y'], abs_y.inputs[0])

    facing_x = new_math(group, 'GREATER_THAN', 'Facing X')
    group.links.new(abs_x.outputs[0], facing_x.inputs[0])
    assert isinstance(facing_x.inputs[1], NodeSocketFloat)
    facing_x.inputs[1].default_value = 0.5

    facing_y = new_math(group, 'GREATER_THAN', 'Facing Y')
    group.links.new(abs_y.outputs[0], facing_y.inputs[0])
    assert isinstance(facing_y.inputs[1], NodeSocketFloat)
    facing_y.inputs[1].default_value = 0.5

    split_pos = new_node(group, ShaderNodeSeparateXYZ, 'Split Position')
    group.links.new(input.outputs[0], split_pos.inputs[0])

    [x, y, z] = split_pos.outputs

    xzy = new_node(group, ShaderNodeCombineXYZ, 'XZY')
    group.links.new(x, xzy.inputs[0])
    group.links.new(z, xzy.inputs[1])
    group.links.new(y, xzy.inputs[2])

    yzx = new_node(group, ShaderNodeCombineXYZ, 'YZX')
    group.links.new(y, yzx.inputs[0])
    group.links.new(z, yzx.inputs[1])
    group.links.new(x, yzx.inputs[2])

    if_facing_y = new_node(group, ShaderNodeMix, 'if facing Y')
    if_facing_y.data_type = 'VECTOR'

    elif_facing_x = new_node(group, ShaderNodeMix, 'elseif facing X')
    elif_facing_x.data_type = 'VECTOR'

    group.links.new(facing_y.outputs[0], if_facing_y.inputs['Factor'])
    group.links.new(elif_facing_x.outputs['Result'], if_facing_y.inputs['A'])
    group.links.new(xzy.outputs[0], if_facing_y.inputs['B'])

    group.links.new(facing_x.outputs[0], elif_facing_x.inputs['Factor'])
    group.links.new(input.outputs[0], elif_facing_x.inputs['A'])
    group.links.new(yzx.outputs[0], elif_facing_x.inputs['B'])

    group.links.new(if_facing_y.outputs['Result'], output.inputs[0])

    arrange.nodes_iterate(group)

N = TypeVar('N', bound=Node)

def new_node(group: ShaderNodeTree, cls: Type[N], label: str | None = None) -> N:
    node = group.nodes.new(cls.__name__)
    assert isinstance(node, cls)
    if label:
        node.name = node.label = label
    return node

def new_math(group: ShaderNodeTree, operation: Any, label: str | None = None) -> ShaderNodeMath:
    node = new_node(group, ShaderNodeMath, label)
    node.operation = operation
    return node
