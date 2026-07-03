import json
import os

import wx


def _load_json(filepath):
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _entity_display(entity_id, entity_data):
    if isinstance(entity_data, dict):
        name = entity_data.get("name") or entity_data.get("name_key") or ""
        if name:
            return f"{name} ({entity_id})"
    return str(entity_id)


def _collect_entity_roots(file_data):
    """探测 JSON 顶层中作为"实体集合根"的键。

    判定：值为 dict，且其子值中存在 dict（实体）。
    返回 [(root_key, {entity_id: entity_data}, is_homogeneous), ...]
    is_homogeneous 表示该 dict 的值"全部"是 dict（典型实体集合）。
    """
    roots = []
    if not isinstance(file_data, dict):
        return roots
    for key, value in file_data.items():
        if not isinstance(value, dict) or not value:
            continue
        child_dicts = sum(1 for v in value.values() if isinstance(v, dict))
        if child_dicts == 0:
            continue
        roots.append((key, value, child_dicts == len(value)))
    return roots


class TreePanel(wx.Panel):
    """左侧导航树。两个固定根：地图编辑器 / 数据配置。纯文本，无图标装饰。"""

    def __init__(self, parent, on_select=None):
        super().__init__(parent)
        self.on_select = on_select
        self.editor_config = None
        self._loaded_entity_files = set()

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
        self.tree.Bind(wx.EVT_TREE_ITEM_EXPANDING, self._on_expanding)

    def populate(self, editor_config):
        self.editor_config = editor_config
        self.tree.DeleteAllItems()
        self._loaded_entity_files.clear()

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
        files = sorted(
            f for f in os.listdir(map_dir) if f.lower().endswith(".json")
        )
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

        for entry in editor_config.get("entity_files", []):
            fid = entry["id"]
            listed.add(fid + ".json")
            path = os.path.join(data_dir, fid + ".json")
            item = self.tree.AppendItem(data_root, entry["display"])
            self.tree.SetItemData(
                item,
                {"kind": "entity_file", "file_id": fid, "path": path},
            )
            # 懒加载占位：有子项才显示展开标记
            if os.path.exists(path):
                self.tree.AppendItem(item, "loading...")

        for entry in editor_config.get("config_files", []):
            fid = entry["id"]
            listed.add(fid + ".json")
            path = os.path.join(data_dir, fid + ".json")
            item = self.tree.AppendItem(data_root, entry["display"])
            self.tree.SetItemData(
                item,
                {"kind": "config_file", "file_id": fid, "path": path},
            )

        # 自动发现未列出的 .json，归到"其他"
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
                        {
                            "kind": "entity_file",
                            "file_id": fid,
                            "path": os.path.join(data_dir, fname),
                        },
                    )
                    self.tree.AppendItem(item, "loading...")

    def _on_expanding(self, event):
        item = event.GetItem()
        info = self.tree.GetItemData(item)
        if not info or info.get("kind") != "entity_file":
            event.Skip()
            return
        path = info.get("path", "")
        if path in self._loaded_entity_files:
            event.Skip()
            return
        self._loaded_entity_files.add(path)
        # 清掉 loading 占位
        child, _ = self.tree.GetFirstChild(item)
        if child.IsOk() and self.tree.GetItemText(child) == "loading...":
            self.tree.Delete(child)

        data = _load_json(path)
        if data is None:
            self.tree.AppendItem(item, "(读取失败)")
            event.Skip()
            return
        roots = _collect_entity_roots(data)
        info["roots"] = [(k, homogeneous) for (k, _v, homogeneous) in roots]
        if not roots:
            self.tree.AppendItem(item, "(无实体集合)")
            event.Skip()
            return
        file_id = info.get("file_id", "")
        # 多根：分组；单根：直接平铺
        if len(roots) == 1:
            root_key, entities, _homo = roots[0]
            self._append_entities(item, file_id, root_key, entities, path)
        else:
            for root_key, entities, _homo in roots:
                group = self.tree.AppendItem(item, f"[{root_key}] ({len(entities)})")
                self.tree.SetItemData(group, {"kind": "entity_group"})
                self._append_entities(group, file_id, root_key, entities, path)
        event.Skip()

    def _append_entities(self, parent_item, file_id, root_key, entities, path):
        for eid, edata in entities.items():
            label = _entity_display(eid, edata)
            node = self.tree.AppendItem(parent_item, label)
            self.tree.SetItemData(
                node,
                {
                    "kind": "entity",
                    "file_id": file_id,
                    "root_key": root_key,
                    "entity_id": eid,
                    "path": path,
                },
            )

    def _on_sel_changed(self, event):
        item = event.GetItem()
        info = self.tree.GetItemData(item)
        if info and self.on_select:
            self.on_select(info)
        event.Skip()

    def select_first_map(self):
        """默认选中地图编辑器根下的第一个地图（若无则选根）。"""
        root_item = self.tree.GetRootItem()
        if not root_item.IsOk():
            return
        map_root, _ = self.tree.GetFirstChild(root_item)
        if map_root.IsOk():
            child, _ = self.tree.GetFirstChild(map_root)
            if child.IsOk():
                self.tree.SelectItem(child)
