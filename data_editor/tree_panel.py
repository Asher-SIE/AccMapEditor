import os

import wx


class TreePanel(wx.Panel):
    """左侧导航树。两个固定根：地图编辑器 / 数据配置。只到文件层，
    实体钻取交给右侧 JsonBrowserPanel。纯文本，无图标装饰。"""

    def __init__(self, parent, on_select=None):
        super().__init__(parent)
        self.on_select = on_select
        self.editor_config = None

        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(wx.StaticText(self, label="导航"), 0, wx.LEFT | wx.TOP, 8)
        self.tree = wx.TreeCtrl(
            self,
            style=wx.TR_DEFAULT_STYLE | wx.TR_HIDE_ROOT | wx.TR_LINES_AT_ROOT
            | wx.TR_TWIST_BUTTONS,
        )
        sizer.Add(self.tree, 1, wx.EXPAND | wx.ALL, 4)
        self.SetSizer(sizer)

        self.tree.Bind(wx.EVT_TREE_SEL_CHANGED, self._on_sel_changed)

    def populate(self, editor_config):
        self.editor_config = editor_config
        self.tree.DeleteAllItems()

        root_item = self.tree.AddRoot("Root")

        map_root = self.tree.AppendItem(root_item, "地图编辑器")
        self.tree.SetItemData(map_root, {"kind": "map_root"})
        self._populate_maps(map_root, editor_config)

        data_root = self.tree.AppendItem(root_item, "数据配置")
        self.tree.SetItemData(data_root, {"kind": "data_root"})
        self._populate_data(data_root, editor_config)

        self.tree.Expand(map_root)
        if self.tree.GetChildrenCount(data_root) > 0:
            self.tree.Expand(data_root)

    def _populate_maps(self, map_root, editor_config):
        map_dir = editor_config.get("map_dir", "")
        if not map_dir or not os.path.isdir(map_dir):
            self.tree.AppendItem(map_root, "(未配置地图目录)")
            return
        files = sorted(f for f in os.listdir(map_dir) if f.lower().endswith(".json"))
        if not files:
            self.tree.AppendItem(map_root, "(无地图文件)")
            return
        for fname in files:
            item = self.tree.AppendItem(map_root, fname)
            self.tree.SetItemData(
                item,
                {"kind": "map_file", "path": os.path.join(map_dir, fname)},
            )

    def _populate_data(self, data_root, editor_config):
        data_dir = editor_config.get("data_dir", "")
        listed = set()

        for entry in editor_config.get("entity_files", []) + editor_config.get("config_files", []):
            fid = entry["id"]
            listed.add(fid + ".json")
            path = os.path.join(data_dir, fid + ".json")
            item = self.tree.AppendItem(data_root, entry["display"])
            self.tree.SetItemData(
                item,
                {"kind": "data_file", "file_id": fid, "path": path},
            )

        if data_dir and os.path.isdir(data_dir):
            others = sorted(
                f
                for f in os.listdir(data_dir)
                if f.lower().endswith(".json") and f not in listed
            )
            if others:
                other_root = self.tree.AppendItem(data_root, "其他")
                self.tree.SetItemData(other_root, {"kind": "other_root"})
                for fname in others:
                    fid = fname[:-5]
                    item = self.tree.AppendItem(other_root, fname)
                    self.tree.SetItemData(
                        item,
                        {"kind": "data_file", "file_id": fid, "path": os.path.join(data_dir, fname)},
                    )

    def _on_sel_changed(self, event):
        item = event.GetItem()
        info = self.tree.GetItemData(item)
        if info and self.on_select:
            self.on_select(info)
        event.Skip()

    def select_first_map(self):
        root_item = self.tree.GetRootItem()
        if not root_item.IsOk():
            return
        map_root, _ = self.tree.GetFirstChild(root_item)
        if map_root.IsOk():
            child, _ = self.tree.GetFirstChild(map_root)
            if child.IsOk():
                self.tree.SelectItem(child)

    def select_map_root(self):
        root_item = self.tree.GetRootItem()
        if not root_item.IsOk():
            return
        map_root, _ = self.tree.GetFirstChild(root_item)
        if map_root.IsOk():
            self.tree.SelectItem(map_root)
