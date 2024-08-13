import bpy
import itertools
import os.path

from xml.etree import ElementTree as ET
from typing import Iterable, Literal, Any, cast
from mathutils import Color, Vector

from . import custom_nodes

from bpy.types import (
    ShaderNodeRGB,
    ShaderNodeAddShader,
    ShaderNodeMixShader,
    ShaderNodeValue,
    ShaderNodeVectorTransform,
    ShaderNodeGroup,
    ShaderNodeTree,
    ShaderNodeBevel,
    ShaderNodeMath,
    ShaderNodeVectorMath,
    ShaderNodeTexVoronoi,
    ShaderNodeValToRGB,
    ShaderNodeRGBCurve,
    ShaderNodeBsdfPrincipled,
    ShaderNodeBsdfAnisotropic,
    ShaderNodeTexImage,
    NodeSocketVector,
    NodeSocketFloat,
    NodeSocketColor,
    NodeSocketFloatFactor,
    NodeSocketInt,
    NodeSocketBool,
    NodeGroupInput,
    NodeGroupOutput,
    Node,
    NodeSocket,
    NodeTreeInterfaceSocket,
    NodeTree,
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
    'SubsurfaceColor': 'Subsurface Radius',
    'BaseColor': 'Base Color',
    'Color': 'Base Color',
}

node_types = {
    'value': 'ShaderNodeValue',
    'color': 'ShaderNodeRGB',
    'vector': 'ShaderNodeRGB', # TODO: Custom node group with a three-number panel or whatever

    'translucent_bsdf': 'ShaderNodeBsdfTranslucent',
    'principled_bsdf': 'ShaderNodeBsdfPrincipled',
    'transparent_bsdf': 'ShaderNodeBsdfTransparent',

    'mix_value': 'ShaderNodeMix',
    'mix': 'ShaderNodeMixRGB',
    'mix_closure': 'ShaderNodeMixShader',

    # In modern blender, mix can act as switch when the input is boolean
    'switch_float': 'ShaderNodeMix',
    'switch_closure': 'ShaderNodeMixShader', 
    'glossy_bsdf': 'ShaderNodeBsdfAnisotropic', # unsure

    'noise_texture': 'ShaderNodeTexNoise',
    'image_texture': 'ShaderNodeTexImage',
    'voronoi_texture': 'ShaderNodeTexVoronoi',

    'group_input': 'NodeGroupInput',
    'group_output': 'NodeGroupOutput',
    'group': 'ShaderNodeGroup',

    'add_closure': 'ShaderNodeAddShader',
    'emission': 'ShaderNodeEmission',
    'texture_coordinate': 'ShaderNodeTexCoord',
    'vector_transform': 'ShaderNodeVectorTransform',
    'bump': 'ShaderNodeBump',
    'rounding_edge_normal': 'ShaderNodeBevel',
    'math': 'ShaderNodeMath',
    'mapping': 'ShaderNodeMapping',
    'rgb_ramp': 'ShaderNodeValToRGB',
    'object_info': 'ShaderNodeObjectInfo',
    'diffuse_bsdf': 'ShaderNodeBsdfDiffuse',
    'normal_map': 'ShaderNodeNormalMap',
    'vector_math': 'ShaderNodeVectorMath',
    'brightness_contrast': 'ShaderNodeBrightContrast',
    'uvmap': 'ShaderNodeUVMap',
    'rgb_curves': 'ShaderNodeRGBCurve',
    'geometry': 'ShaderNodeNewGeometry',
    'absorption_volume': 'ShaderNodeVolumeAbsorption',
    'layer_weight': 'ShaderNodeLayerWeight',
}

socket_types = {
    'color': 'NodeSocketColor',
    'closure': 'NodeSocketShader',
    'vector': 'NodeSocketVector',
    'float': 'NodeSocketFloat',
    'int': 'NodeSocketInt',
    'boolean': 'NodeSocketBool',
}

passthroughs = {
    'Levels': 'NodeSocketInt',
    'MinColorRatio': 'NodeSocketFloat',
    'MaxColorRatio': 'NodeSocketFloat',
    'enable': 'NodeSocketBool',
}

custom_node_groups = {
    'uv_degradation': 'UV Degradation',
    'project_to_axis_plane': 'Project to Axis Planes',
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
    process_xml(tree.getroot(), os.path.dirname(filepath))

def process_xml(root: ET.Element, dir: str) -> None:
    custom_nodes.uv_degradation()
    custom_nodes.project_to_axis_planes()
    
    for thing in root:
        if thing.tag == 'material':
            assert len(thing) == 1
            shader = thing[0]
            assert shader.tag == 'shader'
            process_material(thing.attrib, shader, dir)

        elif thing.tag == 'group':
            assert len(thing) == 1
            shader = thing[0]
            assert shader.tag == 'shader'
            process_group(thing.attrib, shader, dir)

def extract_vector(elem: ET.Element) -> tuple:
    value = elem.get('value')
    if value is None:
        raise KeyError('value')
    value = value.replace(', ', ' ') # I have no words
    return tuple(float(x) for x in value.split())

def process_material(material_attrib: dict[str, str], shader: Iterable[ET.Element], dir: str) -> None:
    material_name = material_attrib['name']
    material = bpy.data.materials.new(material_name)
    material.use_nodes = True

    group = material.node_tree
    assert group is not None
    group.nodes.clear()

    output = group.nodes.new('ShaderNodeOutputMaterial')
    output.name = 'Output'

    for elem in shader:
        process_node(group, elem, dir)

def process_group(group_attrib: dict[str, str], nodes: Iterable[ET.Element], dir: str) -> None:
    group_name = group_attrib['name']
    group = bpy.data.node_groups.new(group_name, cast(Any, 'ShaderNodeTree'))
    assert isinstance(group, ShaderNodeTree)

    for elem in nodes:
        process_node(group, elem, dir)

def process_node(group: ShaderNodeTree, elem: ET.Element, dir) -> None:
    if elem.tag == 'connect':
        process_connect(group, elem)
        return
    elif elem.tag == 'group':
        process_group_node(group, elem)
        return

    node: Node
    if elem.tag in custom_node_groups:
        # The node is one of a handful that either were either removed from Blender or custom to Eyesight
        # Emulate it using a custom node group
        node = group.nodes.new('ShaderNodeGroup')
        assert isinstance(node, ShaderNodeGroup)
        tree = bpy.data.node_groups[custom_node_groups[elem.tag]]
        assert isinstance(tree, ShaderNodeTree)
        node.node_tree = tree
    else:
        try:
            node_type = node_types[elem.tag]
        except KeyError:
            print(elem)
            return
        node = group.nodes.new(node_type)

    node.name = elem.get('name', '')
    node.label = node.name

    if elem.tag == 'switch_float':
        node.inputs[0].name = 'ValueEnable'
        node.inputs[1].name = 'ValueDisable'

    if isinstance(node, ShaderNodeRGB):
        color_output = node.outputs['Color']
        assert isinstance(color_output, NodeSocketColor)
        color_output.default_value = extract_vector(elem) + (0.0,)
        if elem.tag == 'vector':
            node.outputs['Color'].name = 'Vector'

    elif isinstance(node, ShaderNodeAddShader):
        node.inputs[0].name = 'Shader1'
        node.inputs[1].name = 'Shader2'

    elif isinstance(node, ShaderNodeMixShader):
        node.inputs[1].name = 'Shader1'
        node.inputs[2].name = 'Shader2'

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

    elif isinstance(node, ShaderNodeValToRGB):
        original_elements = node.color_ramp.elements[:]
        
        interpolate = bool(elem.attrib['interpolate'])
        node.color_ramp.interpolation = 'LINEAR' if interpolate else 'CONSTANT'
        
        samples = [float(x) for x in elem.attrib['ramp'].split()]
        colors = list(Color(x) for x in zip(samples[::3], samples[1::3], samples[2::3]))

        for i, color in enumerate(colors):
            if can_skip(colors, i, interpolate):
                continue

            position = i / (len(colors) - 1)
            stop = node.color_ramp.elements.new(position)
            stop.color = (color.r, color.g, color.b, 1.0)

        for e in original_elements:
            node.color_ramp.elements.remove(e)

    # This might be incorrect, because I don't understand the data.
    elif isinstance(node, ShaderNodeRGBCurve):
        node.mapping.white_level = Color((1.0, 1.0, 1.0))
        
        samples = [float(x) for x in elem.attrib['curves'].split()]
        colors = list(Color(x) for x in zip(samples[::3], samples[1::3], samples[2::3]))

        for i, color in enumerate(colors):
            position = i / (len(colors) - 1)
            node.mapping.curves[0].points.new(position, color.r)
            node.mapping.curves[1].points.new(position, color.g)
            node.mapping.curves[2].points.new(position, color.b)
            node.mapping.curves[3].points.new(position, 1.0)

    elif isinstance(node, ShaderNodeBsdfPrincipled):
        if subsurface_method := elem.get('subsurface_method'):
            node.subsurface_method = cast(Any, subsurface_method.upper())

        if distribution := elem.get('distribution'):
            node.distribution = cast(Any, distribution.upper())

    elif isinstance(node, ShaderNodeBsdfAnisotropic):
        if distribution := elem.get('distribution'):
            node.distribution = cast(Any, distribution.upper())

    elif isinstance(node, ShaderNodeTexImage):
        node.extension = cast(Any, elem.attrib['extension'].upper())

        if filename := elem.get('filename'):
            image_path = os.path.join(dir, filename)
            node.image = bpy.data.images.load(image_path, check_existing=True)

    else:
        # print the element if there are any element-specific attributes we should care about missing
        for key in elem.attrib.keys():
            if key != 'name':
                print(elem.tag, str(elem.attrib))
                break

    for socket_elem in elem:
        if not isinstance(node, ShaderNodeGroup):
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
        elif isinstance(socket, NodeSocketInt):
            socket.default_value = int(socket_elem.get('value', ''))
        elif isinstance(socket, NodeSocketBool):
            socket.default_value = bool(socket_elem.get('value', ''))
        else:
            print('Unrecognized socket:', socket)

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
        name = socket_elem.attrib['name']
        socket_type = socket_types[socket_elem.attrib['type']]

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

# Eliminate redundant RGB ramp stops because the XML always has 255 equally-spaced stops,
# but Blender has a limit of 32 and allows specifying position
def can_skip(colors: list[Color], i: int, interpolate: bool) -> bool:
    try:
        prev = colors[i - 1]
        cur = colors[i]
        next = colors[i + 1]
    except IndexError:
        return False

    if prev == cur and cur == next:
        return True

    if interpolate:
        mid = (prev + next) / 2
        diff = cur - mid
        if max(abs(diff.r), abs(diff.g), abs(diff.b)) < 0.0001:
            return True

    return False
