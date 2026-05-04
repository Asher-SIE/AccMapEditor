import wx


EVT_TYPE_MAP_DATA = wx.NewEventType()
EVT_MAP_DATA = wx.PyEventBinder(EVT_TYPE_MAP_DATA, 1)


class MapDataEvent(wx.PyEvent):
    KIND_TILES_CHANGED = "tiles_changed"
    KIND_COLLISION_CHANGED = "collision_changed"
    KIND_OBJECT_ADDED = "object_added"
    KIND_OBJECT_REMOVED = "object_removed"
    KIND_OBJECT_MODIFIED = "object_modified"
    KIND_OBJECTS_CLEARED = "objects_cleared"
    KIND_MAP_LOADED = "map_loaded"
    KIND_MAP_CLEARED = "map_cleared"

    def __init__(self, kind, **data):
        super().__init__()
        self.SetEventType(EVT_TYPE_MAP_DATA)
        self.kind = kind
        self.data = data
