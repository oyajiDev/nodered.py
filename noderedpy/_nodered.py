# -*- coding: utf-8 -*-
import os, sys, subprocess, shutil, json, traceback
from types import MethodType
from typing import List
from glob import glob
from .templates import package_json, node_html, node_js
from ._property import Property
from . import __path__


class RED:
    """
    Node-RED manager class
    """
    registered_nodes:List["Node"] = []

    def __init__(self, user_dir:str, node_red_dir:str = None, admin_root:str = "/node-red-py", port:int = 1880, show_default_category:bool = True, editor_theme:dict = {}, auths:List[dict] = []):
        """
        Set configs of Node-RED and setup

        Parameters
        ----------
        user_dir: str, required
            userDir of Node-RED settings
        node_red_dir: str, default None
            directory for Node-RED starter
        admin_root: str, default "node-red-py"
            httpAdminRoot of Node-RED settings
        port: int, default 1880
            port of Node-RED server
        show_default_category: bool, default True
            show default categories of Node-RED or not
        editor_theme: dict, default {}
            editorTheme of Node-RED server (for detail information, see https://github.com/node-red/node-red/wiki/Design:-Editor-Themes)
        auths: List[dict], default []
            auth list for Node-RED
        """
        self.user_dir, self.admin_root, self.port, self.show_default_category, self.editor_theme =\
            user_dir, admin_root, port, show_default_category, self.__default_editor_theme(editor_theme)
        
        self.node_auths = self.__default_node_auth(auths)
        
        # set node_red_dir
        if node_red_dir is None:
            self.node_red_dir = os.path.join(__path__[0], "node-red-starter")
        else:
            self.node_red_dir = node_red_dir = os.path.realpath(node_red_dir)
            if os.path.exists(node_red_dir):
                if not { "index.js", "package.json" }.issubset(set(os.listdir(node_red_dir))):
                    raise RuntimeError("Target `node_red_dir` is not Node-RED dir format!")
            else:
                os.mkdir(node_red_dir)
                shutil.copyfile(os.path.join(__path__[0], "node-red-starter", "index.js"), os.path.join(node_red_dir, "index.js"))
                shutil.copyfile(os.path.join(__path__[0], "node-red-starter", "package.json"), os.path.join(node_red_dir, "package.json"))

        # setup Node-RED starter
        subprocess.call(
            [ "npm", "install" ],
            stdout = subprocess.DEVNULL,
            cwd = self.node_red_dir
        )

    # create default editor_theme
    def __default_editor_theme(self, editor_theme:dict):
        page_theme = editor_theme.pop("page", {})
        page_theme.update({
            "title": page_theme.pop("title", "Node-RED.py"),
            "favicon": page_theme.pop("favicon", os.path.join(__path__[0], "assets", "python-logo.png"))
        })
        header_theme = editor_theme.pop("header", {})
        header_theme.update({
            "title": "Node-RED.py",
            "image": None
        })
        menu_theme = editor_theme.pop("menu", {})
        menu_theme.update({
            "menu-item-palette": False
        })
        project_feature = editor_theme.pop("projects", {})
        project_feature.update({
            "enabled": project_feature.pop("enabled", False)
        })

        editor_theme.update({
            "page": page_theme,
            "header": header_theme,
            "menu": menu_theme,
            "userMenu": editor_theme.pop("userMenu", True),
            "projects": project_feature
        })

        return editor_theme
    
    # fill empty auth in auths
    def __default_node_auth(self, node_auths:List[dict]) -> List[dict]:
        new_node_auths = []
        for node_auth in node_auths:
            if ("username" in node_auth.keys() and not node_auth["username"] in ( None, "" )) and ("password" in node_auth.keys() and not node_auth["password"] in ( None, "" )):
                new_node_auths.append({
                    "username": node_auth["username"],
                    "password": node_auth["password"],
                    "permissions": node_auth.pop("permissions", "*")
                })

        return new_node_auths
    
    def register(self, node_func:MethodType, name:str, category:str = "nodered_py", version:str = "1.0.0", description:str = "", author:str = "nodered.py", keywords:List[str] = [], icon:str = "function.png", properties:List[Property] = []):
        """
        Function to register Node function

        Parameters
        ----------
        node_func: MethodType, required
            Node function to register
        name: str, required
            name of Node to register
        category: str, default nodered_py
            category of Node
        version: str, default 1.0.0
            version of Node
        description: str, default ""
            description of Node
        author: str, default nodered.py
            author of Node
        keywords: List[str], default []
            extra keywords of Node
        icon: str, default function.png
            icon of Node(html)
        properties: List[noderedpy._property.Property]
            propertis of Node
        """
        RED.registered_nodes.append(
            Node(
                name, category,
                version, description, author, keywords,
                icon, properties, node_func
            )
        )

    # check input and run node
    def __check_input_from_node(self):
        input_file, output_file = os.path.join(self.__cache_dir, "input.json"), os.path.join(self.__cache_dir, "output.json")

        while True:
            if os.path.exists(input_file):
                # read input file
                while True:
                    # if cannot read file or read during file writing, read file until can read
                    try:
                        with open(input_file, "r", encoding = "utf-8") as ifr:
                            input_data = json.load(ifr)
                        
                        os.remove(input_file)
                        break
                    except json.JSONDecodeError:
                        pass

                node = list(filter(lambda n: n.name == input_data["name"], RED.registered_nodes))[0]

                with open(output_file, "w", encoding = "utf-8") as ofw:
                    json.dump(node.run(input_data["props"], input_data["msg"]), ofw, indent = 4)

    def start(self, debug:bool = True, callback:MethodType = None):
        """
        Start Node-RED server

        Parameters
        ----------
        debug: bool, default True
            show outputs on console or not
        callback: MethodType, default None
            callback when Node-RED server started
        """

        # setup user_dir
        self.__start_for_ready()

        # set started flag file
        self.__started_file = os.path.join(self.node_red_dir, "started")
        # kill if process listen on port
        self.stop()

        # set cache_dir
        self.__cache_dir = os.path.join(self.user_dir, ".cache")
        if os.path.exists(self.__cache_dir):
            shutil.rmtree(self.__cache_dir)

        os.mkdir(self.__cache_dir)

        # save configs
        with open(os.path.join(self.node_red_dir, "config.json"), "w", encoding = "utf-8") as cfw:
            json.dump({
                "userDir": self.user_dir,
                "adminRoot": self.admin_root,
                "port": self.port,
                "showDefaultCategory": self.show_default_category,
                "userCategory": list(set([ node.category for node in RED.registered_nodes ])),
                "editorTheme": self.editor_theme,
                "adminAuth": self.node_auths
            }, cfw, indent = 4)

        # # save editor_theme
        # with open(os.path.join(self.node_red_dir, "editorTheme.json"), "w", encoding = "utf-8") as tjw:
        #     json.dump(self.editor_theme, tjw, indent = 4)

        # remove existing nodes
        for node_dir in glob(os.path.join(self.user_dir, "node_modules", "nodered-py-*")):
            shutil.rmtree(node_dir)

        # create custom nodes
        for node in RED.registered_nodes:
            node.create(self.user_dir, self.__cache_dir)

        # run Node-RED server
        subprocess.Popen([
            "node",
            "index.js"
        ], shell = False, stdout = sys.stdout if debug else subprocess.DEVNULL, cwd = self.node_red_dir)

        while True:
            if os.path.exists(self.__started_file):
                if callback:
                    callback()

                break

        try:
            self.__check_input_from_node()
        except KeyboardInterrupt:
            self.stop()

    def __start_for_ready(self):
        """
        Start Node-RED for setup default userDir
        """
        import time

        self.__started_file = os.path.join(self.node_red_dir, "started")
        if os.path.exists(self.__started_file):
            os.remove(self.__started_file)

        # save configs
        with open(os.path.join(self.node_red_dir, "config.json"), "w", encoding = "utf-8") as cfw:
            json.dump({
                "userDir": self.user_dir,
                "adminRoot": self.admin_root,
                "port": self.port,
                "showDefaultCategory": self.show_default_category,
                "userCategory": list(set([ node.category for node in RED.registered_nodes ])),
                "editorTheme": self.editor_theme,
                "adminAuth": []
            }, cfw, indent = 4)

        subprocess.Popen([
            "node",
            "index.js"
        ], shell = False, stdout = subprocess.DEVNULL, cwd = self.node_red_dir)

        while True:
            if os.path.exists(self.__started_file):
                self.stop()
                break

        time.sleep(1)

    def stop(self):
        """
        Stop Node-RED server
        """
        import psutil, signal

        if os.path.exists(self.__started_file):
            os.remove(self.__started_file)

        killed = False
        for process in psutil.process_iter():
            try:
                for conns in process.connections(kind = "inet"):
                    if conns.laddr.port == self.port:
                        process.send_signal(signal.SIGTERM)
                        killed = True
                        break
            except ( psutil.AccessDenied, psutil.ZombieProcess ):
                pass

            if killed:
                break

class Node:
    def __init__(self, name:str, category:str, version:str, description:str, author:str, keywords:List[str], icon:str, properties:List[Property], node_func:MethodType):
        # name of node cannot contain spaces
        if " " in name.strip():
            raise NameError("Node name cannot contain spaces!")
        
        # category of node cannot contain - or ,
        if "-" in category.strip() or "," in category.strip():
            raise NameError("Category cannot contain '-' or ','!")
        
        # remove default keyword in extra keywords
        self.keywords = [
            keyword
            for keyword in keywords
            if not keyword in ( "node-red", )
        ]

        self.name, self.category, self.version, self.description, self.author, self.icon, self.properties =\
            name, category, version, description, author, icon, properties
        
        self.__node_func = node_func

    def create(self, node_red_user_dir:str, node_red_user_cache_dir:str):
        node_dir = os.path.join(node_red_user_dir, "node_modules", self.name if self.name.startswith("nodered-py-") else f"nodered-py-{self.name}")
        os.makedirs(os.path.join(node_dir, "lib"))

        with open(os.path.join(node_dir, "package.json"), "w", encoding = "utf-8") as pjw:
            pjw.write(package_json(self))

        with open(os.path.join(node_dir, "lib", f"{self.name}.html"), "w", encoding = "utf-8") as nhw:
            nhw.write(node_html(self))

        with open(os.path.join(node_dir, "lib", f"{self.name}.js"), "w", encoding = "utf-8") as njw:
            njw.write(node_js(self, node_red_user_cache_dir))

    def run(self, props:dict, msg:dict) -> dict:
        print(f"\n{self.name} started\n===================================")
        try:
            resp = self.__node_func(props, msg)
            print("============================= ended\n")

            resp.update({ "state": "success" })

            return resp
        except:
            print("============================= error\n")
            return { "state": "fail", "message": traceback.format_exc() }
