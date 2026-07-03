import copy

import wx

from dialogs.object_dialog import PropertyListPanel


class EntityView(wx.Panel):
    """单实体字段编辑：顶部摘要 + PropertyListPanel。

    commit() 将面板当前内容写回 manager.data[root_key][entity_id]，
    并压入撤销快照。切换实体前由容器调用 commit。
    """

    def __init__(self, parent, manager):
        super().__init__(parent)
        self.manager = manager
        self.file_id = None
        self.root_key = None
        self.entity_id = None
        self._loaded = False

        sizer = wx.BoxSizer(wx.VERTICAL)

        self.title = wx.StaticText(self, label="")
        sizer.Add(self.title, 0, wx.ALL, 8)

        self.prop_panel = PropertyListPanel(self, properties={}, label="字段：")
        sizer.Add(self.prop_panel, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 8)

        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.btn_apply = wx.Button(self, label="应用更改")
        btn_sizer.Add(self.btn_apply, 0, wx.ALL, 4)
        sizer.Add(btn_sizer, 0, wx.ALIGN_RIGHT | wx.RIGHT | wx.BOTTOM, 4)

        self.SetSizer(sizer)

        self.btn_apply.Bind(wx.EVT_BUTTON, self.on_apply)

    def _entity(self):
        ents = self.manager.data.get(self.root_key, {})
        return ents.get(self.entity_id)

    def load(self, file_id, root_key, entity_id):
        self.file_id = file_id
        self.root_key = root_key
        self.entity_id = entity_id
        ent = self._entity()
        if ent is None:
            self.title.SetLabel(f"实体不存在：{entity_id}")
            self.prop_panel.set_properties({})
            self._loaded = False
            return
        if not isinstance(ent, dict):
            self.title.SetLabel(f"{entity_id}（非对象类型，无法用字段编辑）")
            self.prop_panel.set_properties({})
            self._loaded = False
            return
        name = ent.get("name") or ent.get("name_key") or ""
        label = f"{name} ({entity_id})" if name else str(entity_id)
        self.title.SetLabel(label)
        self.prop_panel.set_properties(copy.deepcopy(ent))
        self._loaded = True

    def commit(self):
        if not self._loaded or self.entity_id is None:
            return
        if not isinstance(self.manager.data, dict):
            self._loaded = False
            return
        ents = self.manager.data.get(self.root_key)
        if not isinstance(ents, dict) or self.entity_id not in ents:
            self._loaded = False
            return
        new_data = self.prop_panel.get_properties()
        if ents.get(self.entity_id) == new_data:
            return
        self.manager.push_snapshot()
        ents[self.entity_id] = new_data

    def on_apply(self, event):
        self.commit()
        wx.MessageBox("已应用（未保存到文件，按 Ctrl+S 写入）", "提示", wx.OK)
