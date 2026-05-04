import copy
import json
import os
import wx

from .events import EVT_TYPE_MAP_DATA, EVT_MAP_DATA, MapDataEvent
from .commands import (
    UndoManager,
    AddObjectCommand,
    RemoveObjectCommand,
    ModifyObjectCommand,
    SetTileCommand,
    BulkSetTilesCommand,
    SetCollisionCommand,
    ClearObjectsCommand,
    ResizeMapCommand,
    TILE_SIZE,
)


class MapDataManager(wx.EvtHandler):
    def __init__(self):
        super().__init__()
        self.width = 200
        self.height = 200
        self.map_data = [[0] * self.width for _ in range(self.height)]
        self.object_layers = [
            {"type": "objectgroup", "name": "Object Layer 1", "objects": []}
        ]
        self.collision_set = set()
        self.map_properties = {"name": "Ground", "bgm": ""}
        self.next_object_id = 1
        self.tile_definitions = {}

        self.undo_manager = UndoManager()

    def _notify(self, kind, **data):
        event = MapDataEvent(kind, **data)
        self.ProcessEvent(event)

    def execute(self, command):
        self.undo_manager.execute(self, command)

    def undo(self):
        return self.undo_manager.undo(self)

    def redo(self):
        return self.undo_manager.redo(self)

    def can_undo(self):
        return self.undo_manager.can_undo()

    def can_redo(self):
        return self.undo_manager.can_redo()

    def load_from_dict(self, data):
        new_width = data.get("width", 0)
        new_height = data.get("height", 0)
        if new_width == 0 or new_height == 0:
            return False

        layers = data.get("layers", [])
        if not layers:
            return False

        self.width = new_width
        self.height = new_height
        self.map_data = []
        self.object_layers = []
        self.next_object_id = 1

        for layer in layers:
            layer_type = layer.get("type", "")
            if layer_type == "tilelayer":
                layer_data = layer.get("data", [])
                self.map_data = []
                for y in range(new_height):
                    row = []
                    for x in range(new_width):
                        idx = y * new_width + x
                        row.append(layer_data[idx] if idx < len(layer_data) else 0)
                    self.map_data.append(row)

            elif layer_type == "objectgroup":
                if "name" not in layer:
                    layer["name"] = f"Object Layer {len(self.object_layers) + 1}"
                for obj in layer.get("objects", []):
                    obj_id = obj.get("id", 0)
                    if obj_id >= self.next_object_id:
                        self.next_object_id = obj_id + 1
                self.object_layers.append(layer)

        if not self.map_data:
            self.map_data = [[0] * new_width for _ in range(new_height)]

        if not self.object_layers:
            self.object_layers = [
                {"type": "objectgroup", "name": "Object Layer 1", "objects": []}
            ]

        self.map_properties = data.get("map_properties", {"name": "Ground", "bgm": ""})
        self.collision_set = set()
        for coord in data.get("collision", {}).get("impassable", []):
            if isinstance(coord, list) and len(coord) == 2:
                self.collision_set.add((coord[0], coord[1]))

        self.undo_manager.clear()
        self._notify("map_loaded")
        return True

    def clear(self, width=200, height=200):
        self.width = width
        self.height = height
        self.map_data = [[0] * width for _ in range(height)]
        self.object_layers = [
            {"type": "objectgroup", "name": "Object Layer 1", "objects": []}
        ]
        self.collision_set = set()
        self.map_properties = {"name": "Ground", "bgm": ""}
        self.next_object_id = 1
        self.undo_manager.clear()
        self._notify("map_cleared")

    def to_dict(self, tile_definitions=None):
        data = []
        for y in range(self.height):
            for x in range(self.width):
                data.append(self.map_data[y][x])

        tiled_json = {
            "width": self.width,
            "height": self.height,
            "tilewidth": TILE_SIZE,
            "collision": {
                "impassable": sorted([x, y] for x, y in self.collision_set)
            },
            "layers": [
                {
                    "data": data,
                    "width": self.width,
                    "height": self.height,
                    "opacity": 1,
                    "type": "tilelayer",
                    "visible": True,
                }
            ]
            + self.object_layers,
            "map_properties": self.map_properties,
            "orientation": "orthogonal",
            "infinite": False,
            "renderorder": "right-down",
            "version": "1.9",
        }
        if tile_definitions is not None:
            export_defs = copy.deepcopy(tile_definitions)
            for tile_info in export_defs.values():
                if isinstance(tile_info, dict):
                    tile_info.get("properties", {}).pop("passable", None)
            tiled_json["tile_definitions"] = export_defs
        return tiled_json

    def set_tile(self, x, y, value):
        self.execute(SetTileCommand(x, y, value))

    def set_tiles_bulk(self, changes):
        self.execute(BulkSetTilesCommand(changes))

    def add_object(self, obj_data):
        obj_data["id"] = self.next_object_id
        self.next_object_id += 1
        self.execute(AddObjectCommand(0, obj_data))

    def remove_object(self, obj_id):
        obj = self.find_object_by_id(obj_id)
        if obj is None:
            return False
        self.execute(RemoveObjectCommand(0, obj_id))
        return True

    def modify_object(self, obj_id, new_data):
        new_data["id"] = obj_id
        self.execute(ModifyObjectCommand(0, obj_id, new_data))

    def clear_objects(self):
        self.execute(ClearObjectsCommand(0))

    def set_collision(self, x, y, state):
        self.execute(SetCollisionCommand([(x, y, state)]))

    def toggle_collision(self, x, y):
        state = (x, y) not in self.collision_set
        self.set_collision(x, y, state)
        return state

    def resize(self, new_width, new_height):
        self.execute(ResizeMapCommand(new_width, new_height))

    def find_object_at(self, tile_x, tile_y):
        for layer_idx, layer in enumerate(self.object_layers):
            for obj in layer.get("objects", []):
                obj_tx = obj.get("x", 0) // TILE_SIZE
                obj_ty = obj.get("y", 0) // TILE_SIZE
                obj_tw = max(1, obj.get("width", TILE_SIZE) // TILE_SIZE)
                obj_th = max(1, obj.get("height", TILE_SIZE) // TILE_SIZE)
                if (
                    obj_tx <= tile_x < obj_tx + obj_tw
                    and obj_ty <= tile_y < obj_ty + obj_th
                ):
                    return layer_idx, obj
        return None, None

    def find_object_by_id(self, obj_id, layer_idx=None):
        if layer_idx is not None:
            for obj in self.object_layers[layer_idx].get("objects", []):
                if obj.get("id") == obj_id:
                    return obj
        else:
            for layer in self.object_layers:
                for obj in layer.get("objects", []):
                    if obj.get("id") == obj_id:
                        return obj
        return None

    def get_object_display_text(self, tile_x, tile_y):
        _, obj = self.find_object_at(tile_x, tile_y)
        if obj:
            name = obj.get("name", "")
            obj_type = obj.get("type", "")
            return f"[{name}:{obj_type}]"
        return None

    def get_cell_display(self, x, y):
        val = self.map_data[y][x]
        tile_value = "" if val in (0, "0") else str(val)
        collision_marker = "[C]" if (x, y) in self.collision_set else ""
        obj_text = self.get_object_display_text(x, y)
        parts = [p for p in [tile_value, collision_marker, obj_text] if p]
        return " ".join(parts)

    def get_active_layer(self):
        return self.object_layers[0]

    def get_active_objects(self):
        return self.object_layers[0].get("objects", [])

    def is_modified(self):
        if self.width != 200 or self.height != 200:
            return True
        for row in self.map_data:
            for cell in row:
                if cell not in (0, "0"):
                    return True
        for layer in self.object_layers:
            if layer.get("objects"):
                return True
        if self.collision_set:
            return True
        return False

    def get_object_tile_rect(self, obj):
        tx = obj.get("x", 0) // TILE_SIZE
        ty = obj.get("y", 0) // TILE_SIZE
        tw = max(1, obj.get("width", TILE_SIZE) // TILE_SIZE)
        th = max(1, obj.get("height", TILE_SIZE) // TILE_SIZE)
        return tx, ty, tw, th
