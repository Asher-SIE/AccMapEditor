import copy

import wx

from dialogs.object_dialog import PropertyListPanel


class ConfigView(wx.Panel):
    """配置文件视图：对整个顶层对象用 PropertyListPanel 编辑。"""

    def __init__(self, parent, manager):
        super().__init__(parent)
        self.manager = manager
        self.file_id = None
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

    def load(self, file_id):
        self.file_id = file_id
        if not isinstance(self.manager.data, dict):
            self.title.SetLabel(f"{file_id}（顶层非对象）")
            self.prop_panel.set_properties({})
            self._loaded = False
            return
        self.title.SetLabel(f"{file_id}（共 {len(self.manager.data)} 个顶层字段）")
        self.prop_panel.set_properties(copy.deepcopy(self.manager.data))
        self._loaded = True

    def commit(self):
        if not self._loaded:
            return
        new_data = self.prop_panel.get_properties()
        if self.manager.data == new_data:
            return
        self.manager.push_snapshot()
        self.manager.data = new_data

    def on_apply(self, event):
        self.commit()
        wx.MessageBox("已应用（未保存到文件，按 Ctrl+S 写入）", "提示", wx.OK)
