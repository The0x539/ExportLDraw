import bpy

from xml.etree import ElementTree as ET
from typing import Iterable, Literal, Any, cast
from mathutils import Color, Vector

from bpy.types import (
    ShaderNodeRGB,
    ShaderNodeAddShader,
    ShaderNodeMixShader,
    ShaderNodeBsdfTranslucent,
    ShaderNodeBsdfPrincipled,
    ShaderNodeValue,
    ShaderNodeEmission,
    ShaderNodeTexCoord,
    ShaderNodeVectorTransform,
    ShaderNodeGroup,
    ShaderNodeTree,
    ShaderNodeBevel,
    ShaderNodeBump,
    ShaderNodeTexNoise,
    ShaderNodeMath,
    ShaderNodeMapping,
    ShaderNodeVectorMath,
    ShaderNodeBsdfDiffuse,
    ShaderNodeMix,
    ShaderNodeNormalMap,
    ShaderNodeBrightContrast,
    ShaderNodeBsdfTransparent,
    ShaderNodeBsdfAnisotropic,
    ShaderNodeRGBCurve,
    ShaderNodeTexVoronoi,
    ShaderNodeVolumeAbsorption,
    ShaderNodeLayerWeight,
    NodeSocketVector,
    NodeSocketFloat,
    NodeSocketColor,
    NodeSocketFloatFactor,
    NodeGroupInput,
    NodeGroupOutput,
    Node,
    NodeSocket,
    NodeTree,
    NodeTreeInterfaceSocket,
)

# TODO: get rid of this and just do it for all nodes
ConfigurableShaderNode = (
    ShaderNodeBsdfTranslucent
    | ShaderNodeBsdfPrincipled
    | ShaderNodeEmission
    | ShaderNodeBump
    | ShaderNodeBevel
    | ShaderNodeTexNoise
    | ShaderNodeMath
    | ShaderNodeMix
    | ShaderNodeNormalMap
    | ShaderNodeBrightContrast
    | ShaderNodeBsdfTransparent
    | ShaderNodeBsdfAnisotropic
    | ShaderNodeRGBCurve
    | ShaderNodeTexVoronoi
    | ShaderNodeVolumeAbsorption
    | ShaderNodeLayerWeight
)

blender4_renames = {
    'Subsurface': 'Subsurface Weight',
    'Clearcoat': 'Coat Weight',
    'ClearcoatRoughness': 'Coat Roughness',
    'Clearcoat Roughness': 'Coat Roughness',
    'ClearcoatNormal': 'Coat Normal',
    'Clearcoat Normal': 'Coat Normal',
    'Transmission': 'Transmission Weight',
    'Sheen': 'Sheen Weight',
    'SheenTint': 'Sheen Tint',
    'Specular': 'Specular IOR Level',
    'SpecularTint': 'Specular Tint',
    'AnisotropicRotation': 'Anisotropic Rotation',
    'SubsurfaceRadius': 'Subsurface Radius',
    'Fac': 'Factor',

    # Not sure these are accurate.
    'TransmissionRoughness': 'Roughness',
    'Transmission Roughness': 'Roughness',
    'SubsurfaceColor': 'Base Color',
    'BaseColor': 'Base Color',
    'Color': 'Base Color',
}

node_types = {
    'color': 'ShaderNodeRGB',
    'add_closure': 'ShaderNodeAddShader',
    'mix_closure': 'ShaderNodeMixShader',
    'translucent_bsdf': 'ShaderNodeBsdfTranslucent',
    'principled_bsdf': 'ShaderNodeBsdfPrincipled',
    'emission': 'ShaderNodeEmission',
    'group': 'ShaderNodeGroup',
    'value': 'ShaderNodeValue',
    'texture_coordinate': 'ShaderNodeTexCoord',
    'vector': 'ShaderNodeRGB',
    'vector_transform': 'ShaderNodeVectorTransform',
    'group_input': 'NodeGroupInput',
    'group_output': 'NodeGroupOutput',
    'bump': 'ShaderNodeBump',
    'noise_texture': 'ShaderNodeTexNoise',
    'rounding_edge_normal': 'ShaderNodeBevel',
    'switch_closure': 'ShaderNodeMixShader', # I am at wit's end
    'math': 'ShaderNodeMath',
    'mapping': 'ShaderNodeMapping',
    'rgb_ramp': 'ShaderNodeValToRGB',
    'project_to_axis_plane': 'ShaderNodeVectorMath', # I have no idea what this node was supposed to do.
    'object_info': 'ShaderNodeObjectInfo',
    'image_texture': 'ShaderNodeTexImage',
    'diffuse_bsdf': 'ShaderNodeBsdfDiffuse',
    'mix_value': 'ShaderNodeMix',
    'switch_float': 'ShaderNodeMix', # aaaaaaaaaaaaaaaaaaaa
    'normal_map': 'ShaderNodeNormalMap',
    'vector_math': 'ShaderNodeVectorMath',
    'brightness_contrast': 'ShaderNodeBrightContrast',
    'uvmap': 'ShaderNodeUVMap',
    'transparent_bsdf': 'ShaderNodeBsdfTransparent',
    'glossy_bsdf': 'ShaderNodeBsdfAnisotropic', # unsure
    'rgb_curves': 'ShaderNodeRGBCurve',
    'voronoi_texture': 'ShaderNodeTexVoronoi',
    'geometry': 'ShaderNodeNewGeometry',
    'absorption_volume': 'ShaderNodeVolumeAbsorption',
    'layer_weight': 'ShaderNodeLayerWeight',
}

socket_types = {
    'color': 'NodeSocketColor',
    'closure': 'NodeSocketShader',
    'vector': 'NodeSocketVector',
    'float': 'NodeSocketFloat',
}

passthroughs = {
    'Levels': 'NodeSocketInt',
    'MinColorRatio': 'NodeSocketFloat',
    'MaxColorRatio': 'NodeSocketFloat',
    'enable': 'NodeSocketBool',
}

def get_input(node: Node, key: str) -> NodeSocket:
    i = node.inputs.find(key)
    if i >= 0:
        return node.inputs[i]

    if key in blender4_renames:
        key = blender4_renames[key]

    if key == 'Size' and isinstance(node, ShaderNodeBevel):
        key = 'Radius'

    i = node.inputs.find(key)
    if i >= 0:
        return node.inputs[i]
    
    desperation: dict[str, Any] = {
        'ValueEnable': 0,
        'ValueDisable': 1,
        'Value1': 0,
        'Value2': 1,
        'Vector1': 0,
        'Vector2': 1,
        'Value': 0,
    }

    if key in desperation and desperation[key] < len(node.inputs):
        return node.inputs[desperation[key]]
    else:
        print('could not find input', key)
        print('in', ', '.join(node.inputs.keys()))
        print('for', node)
        raise KeyError(key)

def get_output(node: Node, key: str) -> NodeSocket:
    i = node.outputs.find(key)
    if i >= 0:
        return node.outputs[i]

    if key in blender4_renames:
        key = blender4_renames[key]

    if key == 'Factor' and isinstance(node, ShaderNodeTexVoronoi):
        key = 'Distance' # TODO: or 'Position'?

    i = node.outputs.find(key)
    if i >= 0:
        return node.outputs[i]
    
    desperation: dict[str, Any] = {
        'Value': 0,
        'ValueOut': 0,
    }

    if key in desperation and desperation[key] < len(node.outputs):
        return node.outputs[desperation[key]]
    else:
        print('could not find output', key)
        print('in', ', '.join(node.outputs.keys()))
        print('for', node)
        raise KeyError(key)

def load_xml(filepath: str) -> None:
    tree = ET.parse(filepath)
    process_xml(tree.getroot())

def process_xml(root: ET.Element) -> None:
    for thing in root:
        if thing.tag == 'material':
            assert len(thing) == 1
            shader = thing[0]
            assert shader.tag == 'shader'
            process_material(thing.attrib, shader)

        elif thing.tag == 'group':
            assert len(thing) == 1
            shader = thing[0]
            assert shader.tag == 'shader'
            process_group(thing.attrib, shader)

def extract_vector(elem: ET.Element) -> tuple:
    value = elem.get('value')
    if value is None:
        raise KeyError('value')
    value = value.replace(', ', ' ') # I have no words
    return tuple(float(x) for x in value.split())

def process_material(material_attrib: dict[str, str], shader: Iterable[ET.Element]) -> None:
    material_name = material_attrib['name']
    material = bpy.data.materials.new(material_name)
    material.use_nodes = True

    group = material.node_tree
    assert group is not None
    group.nodes.clear()

    output = group.nodes.new('ShaderNodeOutputMaterial')
    output.name = 'Output'

    for elem in shader:
        process_node(group, elem)

def process_group(group_attrib: dict[str, str], nodes: Iterable[ET.Element]) -> None:
    group_name = group_attrib['name']
    if group_name in (
        'UVGroup',
        'UVGroup2',
        'CHROME-ANTIQUE-GROUP',
        'UVTwoColorGroup',
    ):
        # TODO: figure out what a <uv_degradation /> is
        # and a <mix />
        return
    
    group = bpy.data.node_groups.new(group_name, cast(Any, 'ShaderNodeTree'))
    assert isinstance(group, ShaderNodeTree)

    for elem in nodes:
        process_node(group, elem)

def process_node(group: ShaderNodeTree, elem: ET.Element) -> None:
    if elem.tag == 'connect':
        process_connect(group, elem)
        return
    elif elem.tag == 'group':
        process_group_node(group, elem)
        return

    try:
        node: Node = group.nodes.new(node_types[elem.tag])
    except KeyError:
        print(elem)
        return

    node.name = elem.get('name', '')
    node.label = node.name

    if elem.tag == 'switch_float':
        node.inputs[0].name = 'ValueEnable'
        node.inputs[1].name = 'ValueDisable'

    if isinstance(node, ShaderNodeRGB):
        color_output = node.outputs['Color']
        assert isinstance(color_output, NodeSocketColor)
        color_output.default_value = extract_vector(elem) + (1.0,)
        if elem.tag == 'vector':
            node.outputs['Color'].name = 'Vector'

    elif isinstance(node, ShaderNodeAddShader):
        node.inputs[0].name = 'Shader1'
        node.inputs[1].name = 'Shader2'

    elif isinstance(node, ShaderNodeMixShader):
        node.inputs[1].name = 'Shader1'
        node.inputs[2].name = 'Shader2'

    elif isinstance(node, ConfigurableShaderNode):
        for socket_elem in elem:
            assert socket_elem.tag == 'input'
            input_name = socket_elem.get('name', '')

            if isinstance(node, ShaderNodeBevel) and input_name == 'Samples':
                node.samples = int(socket_elem.get('value', ''))
                continue

            socket = get_input(node, input_name)

            if isinstance(socket, NodeSocketVector | NodeSocketColor):
                # this is awful
                v = extract_vector(socket_elem)
                while len(v) < len(socket.default_value):
                    v += (0.0,)
                socket.default_value = v
            elif isinstance(socket, NodeSocketFloat | NodeSocketFloatFactor):
                socket.default_value = float(socket_elem.get('value', ''))
            else:
                print('Unrecognized socket:', socket)
    elif isinstance(node, ShaderNodeValue):
        value_output = node.outputs['Value']
        assert isinstance(value_output, NodeSocketFloat)
        value_output.default_value = float(elem.get('value', ''))

    elif isinstance(node, ShaderNodeVectorTransform):
        node.convert_from = cast(Any, elem.attrib['convert_from'].upper())
        node.convert_to = cast(Any, elem.attrib['convert_to'].upper())
        node.vector_type = cast(Any, elem.attrib['type'].upper())

    elif isinstance(node, ShaderNodeMath):
        node.operation = cast(Any, elem.attrib['type'].upper())
        node.use_clamp = bool(elem.attrib['use_clamp'])

    elif isinstance(node, ShaderNodeVectorMath):
        if elem.tag == 'project_to_axis_plane':
            node.inputs[0].name = 'In'
            node.outputs[0].name = 'Out'
        else:
            operation = elem.attrib['type'].upper()
            if operation == 'AVERAGE':
                # todo
                operation = 'ADD'
            node.operation = cast(Any, operation)

    else:
        pass
        # print(node)

# TODO: this probably has more in common with the other nodes than I thought,
# once defining all the groups ahead of time is taken care of
def process_group_node(group: ShaderNodeTree, elem: ET.Element) -> None:
    node = group.nodes.new('ShaderNodeGroup')
    assert isinstance(node, ShaderNodeGroup)

    node.name = elem.attrib['name']

    group_name = elem.get('group_name', '')            
    if group_name in bpy.data.node_groups:
        subgroup = cast(ShaderNodeTree, bpy.data.node_groups[group_name])
        node.node_tree = subgroup
    else:
        print('missing group:', group_name)
        subgroup = cast(ShaderNodeTree, bpy.data.node_groups.new(group_name, cast(Any, 'ShaderNodeTree')))

    assert isinstance(subgroup, ShaderNodeTree)

    for socket_elem in elem:
        name = socket_elem.get('name', '')
        socket_type: Any = socket_types[socket_elem.get('type', '')]

        in_out: Literal['INPUT', 'OUTPUT']
        match socket_elem.tag:
            case 'input': in_out = 'INPUT'
            case 'output': in_out = 'OUTPUT'
            case _:
                print('unrecognized child of group', socket_elem)
                continue

        for socket in subgroup.interface.items_tree:
            if not isinstance(socket, NodeTreeInterfaceSocket): continue 
            if socket.in_out != in_out: continue
            if socket.name != name: continue

            weird_scenario = (
                (group_name, in_out, name) == ('SPECKLE-GROUP', 'INPUT', 'XOffset')
                and
                (socket.bl_socket_idname, socket_type) == ('NodeSocketFloat', 'NodeSocketColor')
            )
            assert socket.bl_socket_idname == socket_type or weird_scenario
            break
        else:
            print(f'missing socket: {group_name}::{in_out} / {name} {socket_type}')
            subgroup.interface.new_socket(name, in_out=in_out, socket_type=socket_type)

    node.node_tree = bpy.data.node_groups[group_name] # type: ignore

def process_connect(group: ShaderNodeTree, elem: ET.Element) -> None:
    from_node = group.nodes[elem.attrib['from_node']]
    from_socket_name = elem.attrib['from_socket']
    to_node = group.nodes[elem.attrib['to_node']]
    to_socket_name = elem.attrib['to_socket']

    if isinstance(from_node, NodeGroupInput) and from_node.outputs.find(from_socket_name) < 0:
        if isinstance(to_node, NodeGroupOutput):
            # awful hack for an awful piece of data
            # a group with connections directly from its input to its output,
            # such that datatypes can only be inferred later when the group is used by a larger node graph
            socket_type = passthroughs[from_socket_name]
        else:
            to_socket = get_input(to_node, to_socket_name)
            socket_type = to_socket.bl_idname.replace('FloatFactor', 'Float')

        group.interface.new_socket(name=from_socket_name, in_out='INPUT', socket_type=socket_type)

    from_socket = get_output(from_node, from_socket_name)

    if isinstance(to_node, NodeGroupOutput) and to_node.inputs.find(to_socket_name) < 0:
        socket_type = from_socket.bl_idname.replace('FloatFactor', 'Float')
        group.interface.new_socket(name=to_socket_name, in_out='OUTPUT', socket_type=socket_type)

    to_socket = get_input(to_node, to_socket_name)

    if to_socket.is_linked and to_socket.type == 'SHADER' and from_socket.type == 'SHADER':
        implicit_add = group.nodes.new('ShaderNodeAddShader')
        previous_link = to_socket.links[0]
        previous_from_socket = previous_link.from_socket
        group.links.remove(previous_link)
        group.links.new(previous_from_socket, implicit_add.inputs[0])
        group.links.new(from_socket, implicit_add.inputs[1])
        from_socket = implicit_add.outputs[0]

    group.links.new(from_socket, to_socket)
    return
