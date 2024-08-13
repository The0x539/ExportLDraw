import bpy
from typing import Any, cast, TypeVar, Type
from bpy.types import (
    ShaderNodeMath,
    ShaderNodeSeparateXYZ,
    ShaderNodeCombineXYZ,
    ShaderNodeMix,
    ShaderNodeMixRGB,
    NodeSocketFloat,
    NodeSocketVector,
    NodeTreeInterfaceSocketInt,
    Node,
    ShaderNodeTree,
)

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
        ('enable', 'Bool'),
    ):
        group.interface.new_socket(name, in_out='INPUT', socket_type='NodeSocket' + ty)

    levels = group.interface.new_socket('Levels', in_out='INPUT', socket_type='NodeSocketInt')
    assert isinstance(levels, NodeTreeInterfaceSocketInt)
    levels.min_value = 1
    levels.default_value = 4
    levels.max_value = 10
    
    group.interface.new_socket('OutColor', in_out='OUTPUT', socket_type='NodeSocketColor')
    group.interface.new_socket('OutRoughness', in_out='OUTPUT', socket_type='NodeSocketFloat')

    input = group.nodes.new('NodeGroupInput')
    output = group.nodes.new('NodeGroupOutput')

    # TODO: I think this needs an input in order to do its job properly
    rand = group.nodes.new('ShaderNodeTexWhiteNoise')

    # levels_gt_1 = levels > 1
    levels_gt_1 = new_math(group, 'GREATER_THAN', 'Levels > 1')
    group.links.new(input.outputs['Levels'], levels_gt_1.inputs[0])
    assert isinstance(levels_gt_1.inputs[1], NodeSocketFloat)
    levels_gt_1.inputs[1].default_value = 1

    # step_1 = rand() * levels_gt_1
    step_1 = new_math(group, 'MULTIPLY')
    group.links.new(rand.outputs['Value'], step_1.inputs[0])
    group.links.new(levels_gt_1.outputs[0], step_1.inputs[1])

    # step_2 = floor(step_1)
    step_2 = new_math(group, 'FLOOR')
    group.links.new(step_1.outputs[0], step_2.inputs[0])

    # step_3 = Levels - 1
    step_3 = new_math(group, 'SUBTRACT')
    group.links.new(input.outputs['Levels'], step_3.inputs[0])
    assert isinstance(step_3.inputs[1], NodeSocketFloat)
    step_3.inputs[1].default_value = 1

    # step_4 = clamp(step_2 / step_3, 0, 1)
    step_4 = new_math(group, 'DIVIDE')
    step_4.use_clamp = True
    group.links.new(step_2.outputs[0], step_4.inputs[0])
    group.links.new(step_3.outputs[0], step_4.inputs[1])

    # t = step_4 if levels > 1 else 0
    t = new_node(group, ShaderNodeMix, 't')
    t.data_type = 'FLOAT'
    group.links.new(levels_gt_1.outputs[0], t.inputs[0])
    assert isinstance(t.inputs[1], NodeSocketVector)
    t.inputs[1].default_value = (0.0, 0.0, 0.0)
    group.links.new(step_4.outputs[0], t.inputs[2])

    # ratio_range = MaxColorRatio - MinColorRatio
    ratio_range = new_math(group, 'SUBTRACT', 'ratio_range')
    group.links.new(input.outputs['MaxColorRatio'], ratio_range.inputs[0])
    group.links.new(input.outputs['MinColorRatio'], ratio_range.inputs[1])

    # ratio = t * ratio_range + MinColorRatio
    ratio = new_math(group, 'MULTIPLY_ADD', 'ratio')
    group.links.new(t.outputs[0], ratio.inputs[0])
    group.links.new(ratio_range.outputs[0], ratio.inputs[1])
    group.links.new(input.outputs['MinColorRatio'], ratio.inputs[2])

    # color_t = ratio * Strength
    color_t = new_math(group, 'MULTIPLY', 'color_t')
    group.links.new(ratio.outputs[0], color_t.inputs[0])
    group.links.new(input.outputs['Strength'], color_t.inputs[1])

    # out_color = interp(from_color, to_color, color_t)
    out_color = new_node(group, ShaderNodeMixRGB, 'OutColor')
    group.links.new(color_t.outputs[0], out_color.inputs[0])
    group.links.new(input.outputs['FromColor'], out_color.inputs[1])
    group.links.new(input.outputs['ToColor'], out_color.inputs[2])

    # roughness_range = MaxRoughness - MinRoughness
    roughness_range = new_math(group, 'SUBTRACT', 'roughness_range')
    group.links.new(input.outputs['MaxRoughness'], roughness_range.inputs[0])
    group.links.new(input.outputs['MinRoughness'], roughness_range.inputs[1])

    # t_strength = t * strength
    t_strength = new_math(group, 'MULTIPLY', 't * Strength')
    group.links.new(t.outputs[0], t_strength.inputs[0])
    group.links.new(input.outputs['Strength'], t_strength.inputs[1])

    # out_roughness = t_strength * roughness_range + MinRoughness
    out_roughness = new_math(group, 'MULTIPLY_ADD', 'OutRoughness')
    group.links.new(t_strength.outputs[0], out_roughness.inputs[0])
    group.links.new(roughness_range.outputs[0], out_roughness.inputs[1])
    group.links.new(input.outputs['MinRoughness'], out_roughness.inputs[2])

    group.links.new(out_color.outputs[0], output.inputs['OutColor'])
    group.links.new(out_roughness.outputs[0], output.inputs['OutRoughness'])

def project_to_axis_planes() -> None:
    if 'Project to Axis Planes' in bpy.data.node_groups:
        return

    group = bpy.data.node_groups.new('Project to Axis Planes', cast(Any, 'ShaderNodeTree'))
    assert isinstance(group, ShaderNodeTree)

    group.interface.new_socket('In', in_out='INPUT', socket_type='NodeSocketVector')
    group.interface.new_socket('Out', in_out='OUTPUT', socket_type='NodeSocketVector')

    input = group.nodes.new('NodeGroupInput')
    output = group.nodes.new('NodeGroupOutput')

    split = new_node(group, ShaderNodeSeparateXYZ, 'Split')
    group.links.new(input.outputs[0], split.inputs[0])

    [x, y, z] = split.outputs

    facing_x = new_math(group, 'GREATER_THAN', 'Facing X')
    group.links.new(x, facing_x.inputs[0])
    assert isinstance(facing_x.inputs[1], NodeSocketFloat)
    facing_x.inputs[1].default_value = 0.5

    facing_y = new_math(group, 'GREATER_THAN', 'Facing Y')
    group.links.new(y, facing_y.inputs[0])
    assert isinstance(facing_y.inputs[1], NodeSocketFloat)
    facing_y.inputs[1].default_value = 0.5

    xzy = new_node(group, ShaderNodeCombineXYZ, 'XZY')
    group.links.new(x, xzy.inputs[0])
    group.links.new(z, xzy.inputs[1])
    group.links.new(y, xzy.inputs[2])

    yzx = new_node(group, ShaderNodeCombineXYZ, 'YZX')
    group.links.new(y, yzx.inputs[0])
    group.links.new(z, yzx.inputs[1])
    group.links.new(x, yzx.inputs[2])

    if_facing_y = new_node(group, ShaderNodeMixRGB, 'If')

    elif_facing_x = new_node(group, ShaderNodeMixRGB, 'Else')

    group.links.new(facing_y.outputs[0], if_facing_y.inputs[0])
    group.links.new(elif_facing_x.outputs[0], if_facing_y.inputs[1])
    group.links.new(xzy.outputs[0], if_facing_y.inputs[2])

    group.links.new(facing_x.outputs[0], elif_facing_x.inputs[0])
    group.links.new(input.outputs[0], elif_facing_x.inputs[1])
    group.links.new(yzx.outputs[0], elif_facing_x.inputs[2])

    group.links.new(if_facing_y.outputs[0], output.inputs[0])

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
