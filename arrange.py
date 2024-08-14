import bpy
import random
from collections import OrderedDict
from itertools import repeat
from bpy.types import Node, NodeTree

class values:
    average_y = 0.0
    x_last = 0.0
    mat_name = ''

def nodes_iterate(ntree: NodeTree, arrange: bool = True) -> None:
    nodeoutput = outputnode_search(ntree)
    if nodeoutput is None:
        return

    a: list[list[Node]] = []
    a.append([])
    for n in nodeoutput:
        a[0].append(n)

    level = 0

    while a[level]:
        a.append([])
        for node in a[level]:
            inputlist = [i for i in node.inputs if i.is_linked]
            for input in inputlist:
                for nlinks in input.links:
                    node1 = nlinks.from_node
                    a[level + 1].append(node1)
        level += 1
    del a[level]
    level -= 1

    for i in range(len(a)):
        a[i] = list(OrderedDict(zip(a[i], repeat(None))))

    #remove duplicate nodes in all levels, last wins
    top = level
    for row1 in range(top, 1, -1):
        for col1 in a[row1]:
            for row2 in range(row1-1, 0, -1):
                for col2 in a[row2]:
                    if col1 == col2:
                        a[row2].remove(col2)
                        break

    if not arrange:
        nodelist = [j for i in a for j in i]
        nodes_odd(ntree, nodelist=nodelist)
        return

    levelmax = level + 1
    level = 0
    values.x_last = 0

    while level < levelmax:
        values.average_y = 0
        nodes = [x for x in a[level]]
        nodes_arrange(nodes, level)
        level += 1

def outputnode_search(ntree: NodeTree) -> list[Node] | None:
    outputnodes = []
    for node in ntree.nodes:
        if not node.outputs:
            for input in node.inputs:
                if input.is_linked:
                    outputnodes.append(node)
                    break

    if not outputnodes:
        print("No output node found")
        return None

    return outputnodes


def nodes_odd(ntree: NodeTree, nodelist: list[Node]) -> None:
    for node in ntree.nodes:
        node.select = node not in nodelist


def nodes_arrange(nodelist: list[Node], level: int) -> None:
    parents = []
    for node in nodelist:
        parents.append(node.parent)
        node.parent = None

    widthmax = max([x.dimensions.x for x in nodelist])
    xpos = values.x_last - (widthmax + 200) if level != 0 else 0
    values.x_last = xpos

    x = 0.0
    y = 0.0

    for node in nodelist:
        # unfortunately, dimensions are 0 when we try to run this,
        # but this is still better than nothing
        if node.hide:
            hidey = (node.dimensions.y / 2) - 8
            y -= hidey
        else:
            hidey = 0

        node.location.y = y
        y -= 225.0 + node.dimensions.y - hidey

        node.location.x = xpos #if node.type != "FRAME" else xpos + 1200

    y += 225.0

    center = (0 + y) / 2
    values.average_y = center - values.average_y

    for i, node in enumerate(nodelist):
        node.parent =  parents[i]