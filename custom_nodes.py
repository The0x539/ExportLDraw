import bpy
from typing import Any, cast, TypeVar, Type
from bpy.types import (
    ShaderNode,
    ShaderNodeMath,
    ShaderNodeSeparateXYZ,
    ShaderNodeTexCoord,
    ShaderNodeCombineXYZ,
    ShaderNodeObjectInfo,
    ShaderNodeMix,
    ShaderNodeMixRGB,
    ShaderNodeMapRange,
    NodeSocket,
    NodeFrame,
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
    link(group, step_1, {
        0: object_info.outputs['Random'],
        1: input.outputs['Levels'],
    })

    # step_2 = floor(step_1)
    step_2 = new_math(group, 'FLOOR')
    link(group, step_2, step_1.outputs[0])

    # step_3 = Levels - 1
    step_3 = new_math(group, 'SUBTRACT')
    link(group, step_3, input.outputs['Levels'])
    assert isinstance(step_3.inputs[1], NodeSocketFloat)
    step_3.inputs[1].default_value = 1

    # t = clamp(step_2 / step_3, 0, 1)
    # the blender math node uses safe division, so if Levels = 1, t = 0 with no error
    t = new_math(group, 'DIVIDE', 't')
    t.use_clamp = True
    link(group, t, {
        0: step_2.outputs[0],
        1: step_3.outputs[0],
    })

    input2 = new_node(group, NodeGroupInput, 'Group Input (Strength)')

    # color_ratio = map_range(t, 0:1, MinColorRatio:MaxColorRatio)
    color_ratio = new_node(group, ShaderNodeMapRange, 'ColorRatio')
    color_ratio.clamp = False
    link(group, color_ratio, {
        'Value': t.outputs[0],
        'To Min': input2.outputs['MinColorRatio'],
        'To Max': input2.outputs['MaxColorRatio'],
    })
    
    # color_t = color_ratio * Strength
    color_t = new_math(group, 'MULTIPLY', 'color_t')
    link(group, color_t, {
        0: color_ratio.outputs[0],
        1: input2.outputs['Strength'],
    })

    # t_strength = t * strength
    t_strength = new_math(group, 'MULTIPLY', 't * Strength')
    link(group, t_strength, {
        0: t.outputs[0],
        1: input2.outputs['Strength'],
    })

    input3 = new_node(group, NodeGroupInput, 'Group Input (Ranges)')

    # out_color = interp(from_color, to_color, color_t)
    out_color = new_node(group, ShaderNodeMix, 'OutColor')
    out_color.data_type = 'RGBA'
    link(group, out_color, {
        0: color_t.outputs[0],
        'A': input3.outputs['FromColor'],
        'B': input3.outputs['ToColor'],
    })

    # out_roughness = map_range(t_strength, 0:1, MinRoughness:MaxRoughness)
    out_roughness = new_node(group, ShaderNodeMapRange, 'OutRoughness')
    out_roughness.clamp = False
    link(group, out_roughness, {
        'Value': t_strength.outputs[0],
        'To Min': input3.outputs['MinRoughness'],
        'To Max': input3.outputs['MaxRoughness'],
    })

    input4 = new_node(group, NodeGroupInput, 'Group Input (Toggles)')

    toggle_out_color = new_node(group, ShaderNodeMix, 'Color Toggle')
    toggle_out_color.data_type = 'RGBA'
    link(group, toggle_out_color, {
        0: input4.outputs['enable'],
        'A': input4.outputs['FromColor'],
        'B': out_color.outputs['Result'],
    })

    toggle_out_roughness = new_node(group, ShaderNodeMix, 'Roughness Toggle')
    toggle_out_roughness.data_type = 'FLOAT'
    link(group, toggle_out_roughness, {
        0: input4.outputs['enable'],
        'A': input4.outputs['MinRoughness'],
        'B': out_roughness.outputs[0],
    })

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
    link(group, split_normal, tex_coord.outputs['Normal'])

    abs_x = new_math(group, 'ABSOLUTE', 'Abs(X)')
    link(group, abs_x, split_normal.outputs['X'])
    
    abs_y = new_math(group, 'ABSOLUTE', 'Abs(Y)')
    link(group, abs_y, split_normal.outputs['Y'])

    facing_x = new_math(group, 'GREATER_THAN', 'Facing X')
    link(group, facing_x, abs_x.outputs[0])
    assert isinstance(facing_x.inputs[1], NodeSocketFloat)
    facing_x.inputs[1].default_value = 0.5

    facing_y = new_math(group, 'GREATER_THAN', 'Facing Y')
    link(group, facing_y, abs_y.outputs[0])
    assert isinstance(facing_y.inputs[1], NodeSocketFloat)
    facing_y.inputs[1].default_value = 0.5

    split_pos = new_node(group, ShaderNodeSeparateXYZ, 'Split Position')
    link(group, split_pos, input.outputs[0])

    xzy = new_node(group, ShaderNodeCombineXYZ, 'XZY')
    link(group, xzy, {
        0: split_pos.outputs['X'],
        1: split_pos.outputs['Z'],
        2: split_pos.outputs['Y'],
    })

    yzx = new_node(group, ShaderNodeCombineXYZ, 'YZX')
    link(group, yzx, {
        0: split_pos.outputs['Y'],
        1: split_pos.outputs['Z'],
        2: split_pos.outputs['X'],
    })

    if_facing_y = new_node(group, ShaderNodeMix, 'if facing Y')
    if_facing_y.data_type = 'VECTOR'

    elif_facing_x = new_node(group, ShaderNodeMix, 'elseif facing X')
    elif_facing_x.data_type = 'VECTOR'

    link(group, if_facing_y, {
        'Factor': facing_y.outputs[0],        # if facing y
        'B': xzy.outputs[0],                  # then xzy
        'A': elif_facing_x.outputs['Result'], # elif facing x...
    })

    link(group, elif_facing_x, {
        'Factor': facing_x.outputs[0], # if facing x
        'B': yzx.outputs[0],           # then yzx
        'A': input.outputs[0],         # else xyz
    })

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

def link(
    group: ShaderNodeTree,
    node: ShaderNode,
    inputs: NodeSocket | dict[str | int, NodeSocket],
):
    if isinstance(inputs, NodeSocket):
        group.links.new(inputs, node.inputs[0])
    else:
        for (dst, src) in inputs.items():
            group.links.new(src, node.inputs[dst])
