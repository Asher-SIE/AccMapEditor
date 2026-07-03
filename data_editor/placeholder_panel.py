import json

import wx


class DataPlaceholderPanel(wx.Panel):
    """P1 占位：只读展示当前选中的数据节点。P2 将替换为可编辑视图。"""

    def __init__(self, parent):
        super().__init__(parent)
        sizer = wx.BoxSizer(wx.VERTICAL)
        self.info_label = wx.StaticText(self, label="（未选择数据节点）")
        sizer.Add(self.info_label, 0, wx.ALL, 8)

        self.list = wx.ListBox(self, style=wx.LB_SINGLE)
        sizer.Add(self.list, 1, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)
        self.SetSizer(sizer)

    def show_info(self, info, data_loader=None):
        kind = info.get("kind")
        self.list.Clear()

        if kind in ("data_root", "map_root", "entity_group", "other_root"):
            self.info_label.SetLabel("请选择具体文件或实体。")
            return

        if kind == "config_file":
            self.info_label.SetLabel(
                f"配置文件：{info.get('file_id', '')} （P2 启用编辑）"
            )
            return

        if kind == "entity_file":
            self.info_label.SetLabel(
                f"实体集合：{info.get('file_id', '')} （P2 启用编辑）"
            )
            if data_loader:
                entities = data_loader(info.get("path", ""))
                if isinstance(entities, dict):
                    roots = [
                        k
                        for k, v in entities.items()
                        if isinstance(v, dict) and v and any(isinstance(x, dict) for x in v.values())
                    ]
                    for root_key in roots:
                        for eid, edata in entities[root_key].items():
                            name = ""
                            if isinstance(edata, dict):
                                name = edata.get("name") or edata.get("name_key") or ""
                            label = f"{name} ({eid})" if name else str(eid)
                            self.list.Append(label)
            return

        if kind == "entity":
            self.info_label.SetLabel(
                f"实体：{info.get('entity_id', '')} @ {info.get('file_id', '')}"
            )
            return

        self.info_label.SetLabel("")

    def reset(self):
        self.info_label.SetLabel("（未选择数据节点）")
        self.list.Clear()
