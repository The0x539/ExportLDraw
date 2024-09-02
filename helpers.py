import csv
import io
import re
import codecs
import json
from pathlib import Path
import os

from typing import TypeVar, Any, Literal, overload

import bpy
from bpy.types import (
    NodeTree,
    ShaderNodeMath,
    Node,
    NodeSocket,
    NodeSocketInt,
    NodeSocketVector,
    NodeSocketColor,
    NodeSocketFloat,
    NodeSocketFloatFactor,
    NodeTreeInterfaceSocket,
    NodeTreeInterfaceSocketInt,
    NodeTreeInterfaceSocketVector,
    NodeTreeInterfaceSocketColor,
    NodeTreeInterfaceSocketFloat,
)

from .definitions import APP_ROOT


# remove multiple spaces
def clean_line(line):
    return " ".join(line.split())


# assumes cleaned line being passed
def get_params(clean_line, lowercase=False):
    parts = clean_line.split()
    if lowercase:
        return [x.lower() for x in parts]
    return parts


def parse_csv_line(line, min_params=0):
    try:
        parts = list(csv.reader(io.StringIO(line), delimiter=' ', quotechar='"', skipinitialspace=True))
    except csv.Error as e:
        print(e)
        import traceback
        print(traceback.format_exc())
        parts = [re.split(r"\s+", line)]

    if len(parts) == 0:
        return None

    _params = parts[0]

    if len(_params) == 0:
        return None

    while len(_params) < min_params:
        _params.append("")
    return _params


def fix_string_encoding(string):
    new_string = string
    if type(string) is str:
        new_string = bytes(string.encode())
    for codec in [codecs.BOM_UTF8, codecs.BOM_UTF16, codecs.BOM_UTF32]:
        new_string = new_string.replace(codec, b'')
    new_string = new_string.decode()
    return new_string


def write_json(filepath, obj, indent=None, do_print=False):
    try:
        full_path = os.path.join(APP_ROOT, filepath)
        Path(os.path.dirname(full_path)).mkdir(parents=True, exist_ok=True)
        with open(full_path, 'w', encoding='utf-8', newline="\n") as file:
            j = json.dumps(obj, indent=indent, ensure_ascii=False)
            if do_print:
                print(j)
            file.write(j)
    except Exception as e:
        print(e)
        import traceback
        print(traceback.format_exc())


def read_json(filepath, default=None):
    try:
        full_path = os.path.join(APP_ROOT, filepath)
        with open(full_path, 'r', encoding='utf-8') as file:
            return json.load(file)
    except Exception as e:
        print(e)
        import traceback
        print(traceback.format_exc())
        return default


def clamp(num, min_value, max_value):
    return max(min(num, max_value), min_value)


def ensure_bmesh(bm):
    bm.faces.ensure_lookup_table()
    bm.verts.ensure_lookup_table()
    bm.edges.ensure_lookup_table()


def finish_bmesh(bm, mesh):
    bm.to_mesh(mesh)
    bm.clear()
    bm.free()


def finish_mesh(mesh):
    mesh.validate()
    mesh.update(calc_edges=True)


def hide_obj(obj):
    obj.hide_viewport = True
    obj.hide_render = True


def show_obj(obj):
    obj.hide_viewport = False
    obj.hide_render = False

T = TypeVar('T')

def assert_type(value: object, ty: type[T]) -> T:
    assert isinstance(value, ty), f'Expected {ty}, got {type(value)}'
    return value

G = TypeVar('G', bound=NodeTree)

def new_node_group(name: str, ty: type[G]) -> G:
    # workaround for bug in bpy type annotations
    type_name: Literal['DUMMY'] = ty.__name__ # type: ignore
    group = bpy.data.node_groups.new(name, type_name)
    assert isinstance(group, ty)
    return group

N = TypeVar('N', bound=Node)

def new_node(node_tree: NodeTree, cls: type[N], label: str | None = None) -> N:
    node = node_tree.nodes.new(cls.__name__)
    assert isinstance(node, cls)
    if label is not None:
        node.name = node.label = label
    return node

def new_math_node(
    node_tree: NodeTree,
    operation: Literal[
        'ADD',
        'SUBTRACT',
        'MULTIPLY',
        'DIVIDE',
        'FLOOR',
        'CEIL',
        'GREATER_THAN',
        'LESS_THAN',
        'ABSOLUTE',
    ],
    label: str | None = None,
) -> ShaderNodeMath:
    node = new_node(node_tree, ShaderNodeMath, label)
    node.operation = operation
    return node

InOut = Literal['INPUT', 'OUTPUT']

@overload
def new_socket(node_tree: NodeTree, in_out: InOut, name: str, ty: type[NodeSocketInt]) -> NodeTreeInterfaceSocketInt: ...

@overload
def new_socket(node_tree: NodeTree, in_out: InOut, name: str, ty: type[NodeSocketVector]) -> NodeTreeInterfaceSocketVector: ...

@overload
def new_socket(node_tree: NodeTree, in_out: InOut, name: str, ty: type[NodeSocketColor]) -> NodeTreeInterfaceSocketColor: ...

@overload
def new_socket(node_tree: NodeTree, in_out: InOut, name: str, ty: type[NodeSocketFloat]) -> NodeTreeInterfaceSocketFloat: ...

# fallback case
@overload
def new_socket(node_tree: NodeTree, in_out: InOut, name: str, ty: type[NodeSocket]) -> NodeTreeInterfaceSocket: ...

def new_socket(node_tree: NodeTree, in_out: InOut, name: str, ty: type[NodeSocket]) -> NodeTreeInterfaceSocket:
    if ty is NodeSocketFloatFactor:
        ty = NodeSocketFloat
    socket = node_tree.interface.new_socket(name, in_out=in_out, socket_type=ty.__name__) 
    return socket
