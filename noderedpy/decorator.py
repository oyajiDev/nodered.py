# -*- coding: utf-8 -*-
from typing import List
from types import MethodType
from ._nodered import Node, NodeProperty
from ._server import Server


def register(name:str, category:str = "nodered_py", properties:List[NodeProperty] = []) -> MethodType:
    """
    Decorator to register Node function

    Parameters
    ----------
    name: str, required
        name of Node to register
    category: str, default nodered_py
        category of Node
    properties: List[noderedpy._nodered.NodeProperty]
        propertis of Node
    """
    def decorator(node_func:MethodType):
        node = Node(name if name.startswith("nodered-py") else f"nodered-py-{name}", category, properties, node_func)
        Server.registered_nodes.append(node)

        return node_func
    
    return decorator
