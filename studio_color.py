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
    NodeSocketVector,
    NodeSocketFloat,
    NodeSocketColor,
    NodeSocketFloatFactor,
    Node,
)

blender4_renames = {
    'Subsurface': 'Subsurface Weight',
    'Clearcoat': 'Coat Weight',
    'ClearcoatRoughness': 'Coat Roughness',
    'ClearcoatNormal': 'Coat Normal',
    'Transmission': 'Transmission Weight',
    'Sheen': 'Sheen Weight',
    'SheenTint': 'Sheen Tint',
    'Specular': 'Specular IOR Level',
    'SpecularTint': 'Specular Tint',
    'AnisotropicRotation': 'Anisotropic Rotation',
    'SubsurfaceRadius': 'Subsurface Radius',

    # Not sure these are accurate.
    'TransmissionRoughness': 'Roughness',
    'SubsurfaceColor': 'Base Color',
    'BaseColor': 'Base Color',
}

def load_xml(filepath: str) -> None:
    tree = ET.parse(filepath)
    process_xml(tree.getroot())

def process_xml(root: ET.Element) -> None:
    for material in root:
        if material.tag != 'material':
            continue

        for shader in material:
            if shader.tag != 'shader':
                continue

            process_material(material.attrib, shader)
            break

def extract_vector(elem: ET.Element) -> tuple:
    value = elem.get('value')
    if value is None:
        raise KeyError('value')
    return tuple(float(x) for x in value.split())

def process_material(material_attrib: dict[str, str], shader: Iterable[ET.Element]) -> None:
    material_name = material_attrib['name']
    material = bpy.data.materials.new(material_name)
    material.use_nodes = True

    group = material.node_tree
    assert group is not None
    group.nodes.clear()

    # input = group.nodes.new('NodeGroupInput')
    # input.name = 'Input'
    output = group.nodes.new('ShaderNodeOutputMaterial')
    output.name = 'Output'

    for elem in shader:
        process_node(group, elem)

def process_node(group: ShaderNodeTree, elem: ET.Element) -> None:
    if elem.tag == 'connect':
        from_node = group.nodes[elem.attrib['from_node']]
        from_socket_name = elem.attrib['from_socket']
        if from_socket_name in blender4_renames:
            from_socket_name = blender4_renames[from_socket_name]
        from_socket = from_node.outputs[from_socket_name]

        to_node = group.nodes[elem.attrib['to_node']]
        to_socket_name = elem.attrib['to_socket']
        if to_socket_name in blender4_renames:
            to_socket_name = blender4_renames[to_socket_name]
        to_socket = to_node.inputs[to_socket_name]

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
    }

    try:
        node: Node = group.nodes.new(node_types[elem.tag])
    except KeyError:
        print(elem)
        return

    node.name = elem.get('name', '')
    node.label = node.name

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

    elif isinstance(node, ShaderNodeBsdfTranslucent | ShaderNodeBsdfPrincipled | ShaderNodeEmission):
        for socket_elem in elem:
            assert socket_elem.tag == 'input'
            input_name = socket_elem.get('name', '')
            if input_name in blender4_renames:
                input_name = blender4_renames[input_name]

            socket = node.inputs[input_name]

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

    elif isinstance(node, ShaderNodeGroup):
        group_name = elem.get('group_name', '')            
        if group_name in bpy.data.node_groups:
            node.node_tree = bpy.data.node_groups[group_name] # type: ignore
            return
        
        subgroup = bpy.data.node_groups.new(group_name, cast(Any, 'ShaderNodeTree'))
        
        for socket_elem in elem:
            name = socket_elem.get('name', '')
            ty = socket_elem.get('type', '')
            match socket_elem.tag:
                case 'input':
                    subgroup.interface.new_socket(name, in_out='INPUT')
                case 'output':
                    subgroup.interface.new_socket(name, in_out='OUTPUT')

        node.node_tree = bpy.data.node_groups[group_name] # type: ignore

    elif isinstance(node, ShaderNodeValue):
        value_output = node.outputs['Value']
        assert isinstance(value_output, NodeSocketFloat)
        value_output.default_value = float(elem.get('value', ''))

    elif isinstance(node, ShaderNodeVectorTransform):
        node.convert_from = cast(Any, elem.attrib['convert_from'].upper())
        node.convert_to = cast(Any, elem.attrib['convert_to'].upper())
        node.vector_type = cast(Any, elem.attrib['type'].upper())

    elif isinstance(node, ShaderNodeTexCoord):
        pass

    else:
        print(node)
