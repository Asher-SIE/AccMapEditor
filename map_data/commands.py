from abc import ABC, abstractmethod
import copy

TILE_SIZE = 32


class Command(ABC):
    @abstractmethod
    def execute(self, manager):
        pass

    @abstractmethod
    def undo(self, manager):
        pass


class SetTileCommand(Command):
    def __init__(self, x, y, new_value):
        self.x = x
        self.y = y
        self.new_value = new_value
        self.old_value = None

    def execute(self, manager):
        self.old_value = manager.map_data[self.y][self.x]
        manager.map_data[self.y][self.x] = self.new_value
        manager._notify("tiles_changed", cells=[(self.x, self.y)])

    def undo(self, manager):
        manager.map_data[self.y][self.x] = self.old_value
        manager._notify("tiles_changed", cells=[(self.x, self.y)])


class BulkSetTilesCommand(Command):
    def __init__(self, changes):
        self.changes = changes
        self.old_values = None

    def execute(self, manager):
        self.old_values = []
        cells = []
        for x, y, new_val in self.changes:
            self.old_values.append((x, y, manager.map_data[y][x]))
            manager.map_data[y][x] = new_val
            cells.append((x, y))
        manager._notify("tiles_changed", cells=cells)

    def undo(self, manager):
        cells = []
        for x, y, old_val in self.old_values:
            manager.map_data[y][x] = old_val
            cells.append((x, y))
        manager._notify("tiles_changed", cells=cells)


class AddObjectCommand(Command):
    def __init__(self, layer_idx, obj_data):
        self.layer_idx = layer_idx
        self.obj_data = copy.deepcopy(obj_data)

    def execute(self, manager):
        manager.object_layers[self.layer_idx]["objects"].append(self.obj_data)
        if self.obj_data.get("id", 0) >= manager.next_object_id:
            manager.next_object_id = self.obj_data["id"] + 1
        manager._notify("object_added", layer=self.layer_idx, object=self.obj_data)

    def undo(self, manager):
        objects = manager.object_layers[self.layer_idx]["objects"]
        for i, obj in enumerate(objects):
            if obj.get("id") == self.obj_data.get("id"):
                objects.pop(i)
                break
        manager._notify("object_removed", layer=self.layer_idx, object=self.obj_data)


class RemoveObjectCommand(Command):
    def __init__(self, layer_idx, obj_id):
        self.layer_idx = layer_idx
        self.obj_id = obj_id
        self.removed_obj = None

    def execute(self, manager):
        objects = manager.object_layers[self.layer_idx]["objects"]
        for i, obj in enumerate(objects):
            if obj.get("id") == self.obj_id:
                self.removed_obj = copy.deepcopy(obj)
                objects.pop(i)
                break
        manager._notify("object_removed", layer=self.layer_idx, object=self.removed_obj)

    def undo(self, manager):
        if self.removed_obj:
            manager.object_layers[self.layer_idx]["objects"].append(self.removed_obj)
            manager._notify("object_added", layer=self.layer_idx, object=self.removed_obj)


class ModifyObjectCommand(Command):
    def __init__(self, layer_idx, obj_id, new_data):
        self.layer_idx = layer_idx
        self.obj_id = obj_id
        self.new_data = copy.deepcopy(new_data)
        self.old_data = None

    def execute(self, manager):
        objects = manager.object_layers[self.layer_idx]["objects"]
        for i, obj in enumerate(objects):
            if obj.get("id") == self.obj_id:
                self.old_data = copy.deepcopy(obj)
                objects[i] = self.new_data
                break
        manager._notify(
            "object_modified",
            layer=self.layer_idx,
            old_object=self.old_data,
            new_object=self.new_data,
        )

    def undo(self, manager):
        objects = manager.object_layers[self.layer_idx]["objects"]
        current_id = self.new_data.get("id")
        for i, obj in enumerate(objects):
            if obj.get("id") == current_id:
                objects[i] = self.old_data
                break
        manager._notify(
            "object_modified",
            layer=self.layer_idx,
            old_object=self.new_data,
            new_object=self.old_data,
        )


class SetCollisionCommand(Command):
    def __init__(self, changes):
        self.changes = changes
        self.old_states = None

    def execute(self, manager):
        self.old_states = []
        cells = []
        for x, y, new_state in self.changes:
            old_state = (x, y) in manager.collision_set
            self.old_states.append((x, y, old_state))
            if new_state:
                manager.collision_set.add((x, y))
            else:
                manager.collision_set.discard((x, y))
            cells.append((x, y))
        manager._notify("collision_changed", cells=cells)

    def undo(self, manager):
        cells = []
        for x, y, old_state in self.old_states:
            if old_state:
                manager.collision_set.add((x, y))
            else:
                manager.collision_set.discard((x, y))
            cells.append((x, y))
        manager._notify("collision_changed", cells=cells)


class ClearObjectsCommand(Command):
    def __init__(self, layer_idx):
        self.layer_idx = layer_idx
        self.old_objects = None

    def execute(self, manager):
        self.old_objects = copy.deepcopy(
            manager.object_layers[self.layer_idx]["objects"]
        )
        manager.object_layers[self.layer_idx]["objects"] = []
        manager._notify("objects_cleared", layer=self.layer_idx)

    def undo(self, manager):
        manager.object_layers[self.layer_idx]["objects"] = self.old_objects
        manager._notify("objects_cleared", layer=self.layer_idx)


class CompositeCommand(Command):
    def __init__(self, commands):
        self.commands = commands

    def execute(self, manager):
        for cmd in self.commands:
            cmd.execute(manager)

    def undo(self, manager):
        for cmd in reversed(self.commands):
            cmd.undo(manager)


class ResizeMapCommand(Command):
    def __init__(self, new_width, new_height):
        self.new_width = new_width
        self.new_height = new_height
        self.old_width = None
        self.old_height = None
        self.old_data = None
        self.old_collision = None
        self.old_object_layers = None

    def execute(self, manager):
        self.old_width = manager.width
        self.old_height = manager.height
        self.old_data = copy.deepcopy(manager.map_data)
        self.old_collision = copy.deepcopy(manager.collision_set)
        self.old_object_layers = copy.deepcopy(manager.object_layers)

        new_data = [[0] * self.new_width for _ in range(self.new_height)]
        for y in range(min(self.old_height, self.new_height)):
            for x in range(min(self.old_width, self.new_width)):
                new_data[y][x] = manager.map_data[y][x]

        manager.map_data = new_data
        manager.width = self.new_width
        manager.height = self.new_height
        manager.collision_set = {
            (x, y)
            for x, y in manager.collision_set
            if x < self.new_width and y < self.new_height
        }

        new_pixel_w = self.new_width * TILE_SIZE
        new_pixel_h = self.new_height * TILE_SIZE
        for layer in manager.object_layers:
            layer["objects"] = [
                obj
                for obj in layer.get("objects", [])
                if obj.get("x", 0) < new_pixel_w and obj.get("y", 0) < new_pixel_h
            ]
        manager._notify("map_resized")

    def undo(self, manager):
        manager.map_data = self.old_data
        manager.width = self.old_width
        manager.height = self.old_height
        manager.collision_set = self.old_collision
        manager.object_layers = self.old_object_layers
        manager._notify("map_resized")


class UndoManager:
    def __init__(self, max_history=100):
        self.undo_stack = []
        self.redo_stack = []
        self.max_history = max_history

    def execute(self, manager, command):
        command.execute(manager)
        self.undo_stack.append(command)
        self.redo_stack.clear()
        if len(self.undo_stack) > self.max_history:
            self.undo_stack.pop(0)

    def undo(self, manager):
        if not self.undo_stack:
            return False
        command = self.undo_stack.pop()
        command.undo(manager)
        self.redo_stack.append(command)
        return True

    def redo(self, manager):
        if not self.redo_stack:
            return False
        command = self.redo_stack.pop()
        command.execute(manager)
        self.undo_stack.append(command)
        return True

    def can_undo(self):
        return len(self.undo_stack) > 0

    def can_redo(self):
        return len(self.redo_stack) > 0

    def clear(self):
        self.undo_stack.clear()
        self.redo_stack.clear()
