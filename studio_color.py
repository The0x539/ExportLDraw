import itertools
import os.path
from typing import Any, Iterable, Literal, Type, cast
from xml.etree import ElementTree as ET

import bpy
from bpy.types import (
    Node,
    NodeGroupInput,
    NodeGroupOutput,
    NodeSocket,
    NodeSocketBool,
    NodeSocketColor,
    NodeSocketFloat,
    NodeSocketFloatFactor,
    NodeSocketInt,
    NodeSocketVector,
    NodeSocketVectorEuler,
    NodeSocketVectorTranslation,
    NodeSocketVectorXYZ,
    NodeTreeInterfaceSocket,
    ShaderNodeAddShader,
    ShaderNodeBevel,
    ShaderNodeBsdfAnisotropic,
    ShaderNodeBsdfPrincipled,
    ShaderNodeBump,
    ShaderNodeGroup,
    ShaderNodeMath,
    ShaderNodeMapping,
    ShaderNodeMix,
    ShaderNodeMixShader,
    ShaderNodeNormalMap,
    ShaderNodeOutputMaterial,
    ShaderNodeRGB,
    ShaderNodeRGBCurve,
    ShaderNodeTexImage,
    ShaderNodeTexNoise,
    ShaderNodeTexVoronoi,
    ShaderNodeTree,
    ShaderNodeUVMap,
    ShaderNodeValToRGB,
    ShaderNodeValue,
    ShaderNodeVectorMath,
    ShaderNodeVectorTransform,
)

from mathutils import Color, Vector

from . import arrange, custom_nodes
from .helpers import new_node, new_node_group, new_socket, assert_type
from .studio_lookups import (
    custom_node_groups,
    input_aliases,
    node_types,
    output_aliases,
    passthroughs,
    socket_types,
)

def get_socket(
    node: Node,
    key: str,
    sockets: bpy.types.NodeInputs | bpy.types.NodeOutputs,
    aliases: dict[type[Node], dict[str, str | int]],
) -> NodeSocket:
    candidates: list[str | int] = [key]

    if aliases_for_node := aliases.get(type(node)):
        if key in aliases_for_node:
            candidates.append(aliases_for_node[key])

    for k in candidates:
        if isinstance(k, int) and k < len(sockets):
            return sockets[k]
        elif k in sockets.keys():
            try:
                return sockets[k]
            except:
                pass
        else:
            i = sockets.find(key)
            if i >= 0:
                return sockets[i]

    print('could not find socket', key)
    print('in', ', '.join(sockets.keys()))
    print('for', node)
    print('tried', candidates)
    print(sockets)
    raise KeyError(key)

def get_input(node: Node, key: str) -> NodeSocket:
    return get_socket(node, key, node.inputs, input_aliases)

def get_output(node: Node, key: str) -> NodeSocket:
    return get_socket(node, key, node.outputs, output_aliases)

def load_xml(filepath: str) -> None:
    tree = ET.parse(filepath)
    process_xml(tree.getroot(), os.path.dirname(filepath))

def process_xml(root: ET.Element, dir: str) -> None:
    custom_nodes.uv_degradation()
    custom_nodes.project_to_axis_planes()
    
    for thing in root:
        if thing.tag not in ('material', 'group'):
            print('unknown thing-type:', thing.tag)
            continue

        assert len(thing) == 1
        shader = thing[0]
        assert shader.tag == 'shader'

        if thing.tag == 'material':
            process_material(thing.attrib, shader, dir)

        elif thing.tag == 'group':
            process_group(thing.attrib, shader, dir)

def extract_vector(elem: ET.Element, attrib: str = 'value') -> tuple:
    value = elem.get(attrib)
    if value is None:
        raise KeyError(attrib)
    value = value.replace(', ', ' ') # I have no words
    return tuple(float(x) for x in value.split())

def process_material(material_attrib: dict[str, str], shader: Iterable[ET.Element], dir: str) -> None:
    material_name = material_attrib['name']
    material = bpy.data.materials.new(material_name)
    material.use_nodes = True

    group = material.node_tree
    assert group is not None
    group.nodes.clear()

    output = new_node(group, ShaderNodeOutputMaterial, 'Output')

    for elem in shader:
        process_node(group, elem, dir)

    arrange.nodes_iterate(group)

def process_group(group_attrib: dict[str, str], nodes: Iterable[ET.Element], dir: str) -> None:
    group_name = group_attrib['name']
    group = new_node_group(group_name, ShaderNodeTree)

    for elem in nodes:
        process_node(group, elem, dir)

    arrange.nodes_iterate(group)

def process_node(group: ShaderNodeTree, elem: ET.Element, dir) -> None:
    if elem.tag == 'connect':
        try:
            process_connect(group, elem)
        except Exception as exc:
            print(f'{elem.tag} {elem.attrib}')
            raise exc from None
        return

    node: Node
    if elem.tag in custom_node_groups:
        # The node is one of a handful that either were either removed from Blender or custom to Eyesight
        # Emulate it using a custom node group
        node = new_node(group, ShaderNodeGroup)
        tree = bpy.data.node_groups[custom_node_groups[elem.tag]]
        assert isinstance(tree, ShaderNodeTree)
        node.node_tree = tree
    else:
        try:
            node_type = node_types[elem.tag]
        except KeyError:
            print(elem)
            return
        node = group.nodes.new(node_type.__name__)

    node.label = node.name = elem.get('name', '')

    if elem.tag.startswith('switch'):
        if enable := elem.get('enable'):
            assert isinstance(node.inputs[0], NodeSocketFloat | NodeSocketFloatFactor)
            node.inputs[0].default_value = float(enable.lower() == 'true')

    if isinstance(node, ShaderNodeGroup) and elem.tag == 'group':
        process_group_node(node, elem)
        
    elif isinstance(node, ShaderNodeRGB):
        color_output = node.outputs['Color']
        assert isinstance(color_output, NodeSocketColor)
        color_output.default_value = extract_vector(elem) + (0.0,)
        # TODO: Remove when vector constants have their own node
        if elem.tag == 'vector':
            color_output.name = 'Vector'

    elif isinstance(node, ShaderNodeMix):
        if elem.tag == 'mix':
            node.data_type = 'RGBA'

        enum_attr(node, elem, 'blend_type', 'type')

        if use_clamp := elem.get('use_clamp'):
            node.clamp_factor = node.clamp_result = use_clamp.lower() == 'true'

    elif isinstance(node, ShaderNodeMixShader):
        pass

    elif isinstance(node, ShaderNodeBump):
        if enable := elem.get('enable'):
            node.mute = enable.lower() != 'true'
        if invert := elem.get('invert'):
            node.invert = invert.lower() == 'true'

    elif isinstance(node, ShaderNodeValue):
        value_output = node.outputs['Value']
        assert isinstance(value_output, NodeSocketFloat)
        value_output.default_value = float(elem.get('value', ''))

    elif isinstance(node, ShaderNodeVectorTransform):
        enum_attr(node, elem, 'convert_from', required=True)
        enum_attr(node, elem, 'convert_to', required=True)
        enum_attr(node, elem, 'vector_type', 'type', required=True)

    elif isinstance(node, ShaderNodeMath):
        enum_attr(node, elem, 'operation', 'type', required=True)
        if use_clamp := elem.get('use_clamp'):
            node.use_clamp = use_clamp.lower() == 'true'

    elif isinstance(node, ShaderNodeVectorMath):
        operation = elem.attrib['type'].upper()
        if operation == 'AVERAGE':
            # todo
            operation = 'ADD'
        node.operation = cast(Any, operation)

    elif isinstance(node, ShaderNodeValToRGB):
        original_elements = node.color_ramp.elements[:]
        
        interpolate = elem.attrib['interpolate'].lower() == 'true'
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
        enum_attr(node, elem, 'subsurface_method')
        enum_attr(node, elem, 'distribution')

    elif isinstance(node, ShaderNodeBsdfAnisotropic):
        enum_attr(node, elem, 'distribution')

    elif isinstance(node, ShaderNodeTexImage):
        enum_attr(node, elem, 'extension')

        if filename := elem.get('filename'):
            image_path = os.path.join(dir, filename)
            node.image = bpy.data.images.load(image_path, check_existing=True)
        else:
            img = bpy.data.images.new('blank', 1, 1, alpha=True)
            img.pixels = (0.0, 0.0, 0.0, 0.0) # type: ignore
            img.update()
            node.image = img

    elif isinstance(node, ShaderNodeTexVoronoi):
        if coloring := elem.get('coloring'):
            coloring = coloring.lower()
            if coloring == 'cells':
                pass
            elif coloring == 'intensity':
                # TODO: This will require a pow(2.2) function to produce the right imported value
                raise NotImplementedError()
            else:
                raise ValueError(f'Unrecognized coloring method: "{coloring}"')

    elif isinstance(node, ShaderNodeTexNoise):
        if rotation := elem.get('tex_mapping.rotation'):
            node.texture_mapping.rotation = [float(n) for n in rotation.split()]

        if scale := elem.get('tex_mapping.scale'):
            node.texture_mapping.scale = [float(n) for n in scale.split()]

        if translation := elem.get('tex_mapping.translation'):
            node.texture_mapping.translation = [float(n) for n in translation.split()]

        enum_attr(node.texture_mapping, elem, 'vector_type', 'tex_mapping.type')
        enum_attr(node.texture_mapping, elem, 'mapping_x', 'tex_mapping.x_mapping')
        enum_attr(node.texture_mapping, elem, 'mapping_y', 'tex_mapping.y_mapping')
        enum_attr(node.texture_mapping, elem, 'mapping_z', 'tex_mapping.z_mapping')

    elif isinstance(node, ShaderNodeUVMap):
        if from_instancer := elem.get('from_dupli'):
            node.from_instancer = from_instancer.lower() == 'true'

        if uv_map := elem.get('attribute'):
            node.uv_map = uv_map

    elif isinstance(node, ShaderNodeNormalMap):
        enum_attr(node, elem, 'space')

        if uv_map := elem.get('attribute'):
            node.uv_map = uv_map

    elif isinstance(node, ShaderNodeBevel):
        if enabled := elem.get('enabled'):
            assert enabled == 'true' # Why would this be false instead of just omitting the node?

    elif isinstance(node, ShaderNodeMapping):
        if rotation := elem.get('tex_mapping.rotation'):
            rotation_input = assert_type(node.inputs[2], NodeSocketVectorEuler)
            rotation_input.default_value = [float(n) for n in rotation.split()]

        if scale := elem.get('tex_mapping.scale'):
            scale_input = assert_type(node.inputs[3], NodeSocketVectorXYZ)
            scale_input.default_value = [float(n) for n in scale.split()]

        if translation := elem.get('tex_mapping.translation'):
            location_input = assert_type(node.inputs[1], NodeSocketVectorTranslation)
            location_input.default_value = [float(n) for n in translation.split()]

        enum_attr(node, elem, 'vector_type', 'tex_mapping.type')

        if use_minmax := elem.get('tex_mapping.use_minmax'):
            assert use_minmax == 'False' # Not sure what this expresses.
        
    else:
        # print the element if there are any element-specific attributes we should care about missing
        for key in elem.attrib.keys():
            if key != 'name':
                print(elem.tag, str(elem.attrib))
                break

    for socket_elem in elem:
        socket_name = socket_elem.get('name', '')

        if isinstance(node, ShaderNodeBevel) and socket_name == 'Samples':
            node.samples = int(socket_elem.get('value', ''))
            continue

        if socket_elem.tag != 'input':
            assert socket_elem.tag == 'output'
            assert isinstance(node, ShaderNodeGroup)
            continue

        socket = get_input(node, socket_name)

        value = socket_elem.get('value')
        if value is None:
            continue

        if isinstance(socket, NodeSocketVector | NodeSocketColor):
            # this is awful
            v = extract_vector(socket_elem)
            while len(v) < len(socket.default_value):
                v += (0.0,)
            socket.default_value = v
        elif isinstance(socket, NodeSocketFloat | NodeSocketFloatFactor):
            socket.default_value = float(value)
        elif isinstance(socket, NodeSocketInt):
            socket.default_value = int(value)
        elif isinstance(socket, NodeSocketBool):
            socket.default_value = value.lower() == 'true'
        else:
            print('Unrecognized socket:', socket)

# TODO: this probably has more in common with the other nodes than I thought,
# once defining all the groups ahead of time is taken care of
def process_group_node(node: ShaderNodeGroup, elem: ET.Element) -> None:
    group_name = elem.get('group_name', '')
    if group_name in bpy.data.node_groups:
        subgroup = bpy.data.node_groups[group_name]
        assert isinstance(subgroup, ShaderNodeTree)
        node.node_tree = subgroup
    else:
        print(f'{elem.tag} {elem.attrib}')
        print('missing group:', group_name)
        subgroup = new_node_group(group_name, ShaderNodeTree)

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
                (socket.bl_socket_idname, socket_type) == ('NodeSocketFloat', NodeSocketColor)
            )
            assert socket.bl_socket_idname == socket_type.__name__ or weird_scenario, f'expected {socket_type.__name__}, got {socket.bl_socket_idname}'

            # successfully found a matching socket definition
            # skip the else block
            break
        else:
            print(f'missing socket: {group_name}::{in_out} / {name} {socket_type.__name__}')
            subgroup.interface.new_socket(name, in_out=in_out, socket_type=socket_type.__name__)

    node.node_tree = bpy.data.node_groups[group_name] # type: ignore

def process_connect(group: ShaderNodeTree, elem: ET.Element) -> None:
    from_node = group.nodes[elem.attrib['from_node']]
    from_socket_name = elem.attrib['from_socket']
    to_node = group.nodes[elem.attrib['to_node']]
    to_socket_name = elem.attrib['to_socket']

    socket_type: Type[NodeSocket]

    if isinstance(from_node, NodeGroupInput) and from_node.outputs.find(from_socket_name) < 0:
        if isinstance(to_node, NodeGroupOutput):
            # awful hack for an awful piece of data
            # a group with connections directly from its input to its output,
            # such that datatypes can only be inferred later when the group is used by a larger node graph
            socket_type = passthroughs[from_socket_name]
        elif from_socket_name == 'enable':
            socket_type = NodeSocketBool
        else:
            to_socket = get_input(to_node, to_socket_name)
            socket_type = type(to_socket)

        new_socket(group, 'INPUT', from_socket_name, socket_type)

    from_socket = get_output(from_node, from_socket_name)

    if isinstance(to_node, NodeGroupOutput) and to_node.inputs.find(to_socket_name) < 0:
        socket_type = type(from_socket)
        new_socket(group, 'OUTPUT', to_socket_name, socket_type)

    to_socket = get_input(to_node, to_socket_name)

    if to_socket.is_linked and to_socket.type == 'SHADER' and from_socket.type == 'SHADER':
        implicit_add = new_node(group, ShaderNodeAddShader)
        previous_link = to_socket.links[0]
        previous_from_socket = previous_link.from_socket
        group.links.remove(previous_link)
        group.links.new(previous_from_socket, implicit_add.inputs[0])
        group.links.new(from_socket, implicit_add.inputs[1])
        from_socket = implicit_add.outputs[0]

    group.links.new(from_socket, to_socket)

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

def enum_attr(node: object, elem: ET.Element, attr: str, alias: str | None = None, required: bool = False) -> None:
    if value := elem.get(alias or attr):
        value = value.upper()
        setattr(node, attr, value)
    elif required:
        raise KeyError(attr or alias)
