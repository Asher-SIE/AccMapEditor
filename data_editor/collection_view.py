import wx

from dialogs.object_dialog import format_property_value


class CollectionView(wx.Panel):
    """实体集合视图：ListCtrl + 新增/复制/删除。

    直接操作 JsonDataManager 的 data[root_key] dict。
    """

    def __init__(self, parent, manager, on_open_entity=None):
        super().__init__(parent)
        self.manager = manager
        self.file_id = None
        self.root_key = None
        self.on_open_entity = on_open_entity
        self._ids = []

        sizer = wx.BoxSizer(wx.VERTICAL)

        self.title = wx.StaticText(self, label="")
        sizer.Add(self.title, 0, wx.ALL, 8)

        self.list = wx.ListCtrl(self, style=wx.LC_REPORT | wx.LC_SINGLE_SEL)
        self.list.InsertColumn(0, "ID", width=180)
        self.list.InsertColumn(1, "名称", width=140)
        self.list.InsertColumn(2, "字段数", width=60)
        sizer.Add(self.list, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 8)

        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.btn_open = wx.Button(self, label="打开")
        self.btn_add = wx.Button(self, label="新增")
        self.btn_dup = wx.Button(self, label="复制")
        self.btn_del = wx.Button(self, label="删除")
        btn_sizer.Add(self.btn_open, 1, wx.RIGHT, 5)
        btn_sizer.Add(self.btn_add, 1, wx.RIGHT, 5)
        btn_sizer.Add(self.btn_dup, 1, wx.RIGHT, 5)
        btn_sizer.Add(self.btn_del, 1)
        sizer.Add(btn_sizer, 0, wx.EXPAND | wx.ALL, 8)

        self.SetSizer(sizer)

        self.btn_open.Bind(wx.EVT_BUTTON, self.on_open)
        self.btn_add.Bind(wx.EVT_BUTTON, self.on_add)
        self.btn_dup.Bind(wx.EVT_BUTTON, self.on_dup)
        self.btn_del.Bind(wx.EVT_BUTTON, self.on_del)
        self.list.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self.on_open)
        self.list.Bind(wx.EVT_KEY_DOWN, self.on_key)

    def load(self, file_id, root_key):
        self.file_id = file_id
        self.root_key = root_key
        count = len(self._entities())
        self.title.SetLabel(f"{file_id} / {root_key}（共 {count} 个实体）")
        self.refresh_list()

    def _entities(self):
        if (
            self.manager.data is None
            or self.root_key is None
            or not isinstance(self.manager.data.get(self.root_key), dict)
        ):
            return {}
        return self.manager.data[self.root_key]

    def refresh_list(self):
        self.list.DeleteAllItems()
        self._ids = []
        ents = self._entities()
        for eid, edata in ents.items():
            name = ""
            if isinstance(edata, dict):
                name = edata.get("name") or edata.get("name_key") or ""
            field_count = len(edata) if isinstance(edata, dict) else 0
            idx = self.list.InsertItem(self.list.GetItemCount(), str(eid))
            self.list.SetItem(idx, 1, str(name))
            self.list.SetItem(idx, 2, str(field_count))
            self._ids.append(eid)

    def _selected_id(self):
        idx = self.list.GetFirstSelected()
        if idx == -1:
            return None
        if idx < len(self._ids):
            return self._ids[idx]
        return None

    def on_open(self, event):
        eid = self._selected_id()
        if eid is None:
            wx.MessageBox("请先选择一个实体", "提示", wx.OK | wx.ICON_WARNING)
            return
        if self.on_open_entity:
            self.on_open_entity(self.file_id, self.root_key, eid)

    def on_add(self, event):
        ents = self._entities()
        eid = wx.GetTextFromUser("输入新实体 ID：", "新增实体", "", self)
        eid = eid.strip()
        if not eid:
            return
        if eid in ents:
            wx.MessageBox("ID 已存在", "提示", wx.OK | wx.ICON_WARNING)
            return
        self.manager.push_snapshot()
        ents[eid] = {"id": eid}
        self.refresh_list()
        self._select_by_id(eid)

    def on_dup(self, event):
        src_id = self._selected_id()
        if src_id is None:
            wx.MessageBox("请先选择要复制的实体", "提示", wx.OK | wx.ICON_WARNING)
            return
        ents = self._entities()
        default_id = f"{src_id}_copy"
        eid = wx.GetTextFromUser("复制为新 ID：", "复制实体", default_id, self)
        eid = eid.strip()
        if not eid or eid in ents:
            if eid:
                wx.MessageBox("ID 已存在", "提示", wx.OK | wx.ICON_WARNING)
            return
        import copy as _copy

        self.manager.push_snapshot()
        ents[eid] = _copy.deepcopy(ents[src_id])
        if isinstance(ents[eid], dict):
            ents[eid]["id"] = eid
        self.refresh_list()
        self._select_by_id(eid)

    def on_del(self, event):
        eid = self._selected_id()
        if eid is None:
            wx.MessageBox("请先选择要删除的实体", "提示", wx.OK | wx.ICON_WARNING)
            return
        if wx.MessageBox(f"确定删除实体 {eid}？", "确认", wx.YES_NO | wx.ICON_QUESTION) != wx.YES:
            return
        ents = self._entities()
        self.manager.push_snapshot()
        del ents[eid]
        self.refresh_list()

    def on_key(self, event):
        key = event.GetKeyCode()
        if key == wx.WXK_RETURN:
            self.on_open(None)
        elif key == wx.WXK_DELETE:
            self.on_del(None)
        else:
            event.Skip()

    def _select_by_id(self, eid):
        if eid in self._ids:
            idx = self._ids.index(eid)
            self.list.Select(idx)
            self.list.EnsureVisible(idx)
