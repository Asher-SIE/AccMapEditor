import copy

import wx

from dialogs.object_dialog import StructuredValueDialog, format_property_value


def _node_summary(value):
    return format_property_value(value)


class JsonBrowserPanel(wx.Panel):
    """统一递归 JSON 浏览器：面包屑 + 当前层列表 + 增删改/重命名/调序。

    适配任意结构：dict 列键值对、list 列索引项、标量直接显示。
    所有变更直接写 manager.data，提交前 push_snapshot。
    """

    def __init__(self, parent, manager, on_dirty_change=None):
        super().__init__(parent)
        self.manager = manager
        self.on_dirty_change = on_dirty_change
        self.path = []
        self._keys = []
        self.file_id = ""

        top = wx.BoxSizer(wx.VERTICAL)

        crumb_box = wx.BoxSizer(wx.HORIZONTAL)
        self.btn_up = wx.Button(self, label="↑ 上级", size=(80, -1))
        self.crumb_panel = wx.Panel(self)
        self.crumb_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.crumb_panel.SetSizer(self.crumb_sizer)
        crumb_box.Add(self.btn_up, 0, wx.RIGHT, 6)
        crumb_box.Add(self.crumb_panel, 1, wx.EXPAND)
        top.Add(crumb_box, 0, wx.EXPAND | wx.ALL, 6)

        self.title = wx.StaticText(self, label="")
        top.Add(self.title, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 6)

        filter_box = wx.BoxSizer(wx.HORIZONTAL)
        filter_box.Add(wx.StaticText(self, label="筛选:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4)
        self.filter_input = wx.TextCtrl(self, style=wx.TE_PROCESS_ENTER)
        filter_box.Add(self.filter_input, 1, wx.EXPAND)
        top.Add(filter_box, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 6)

        self.list = wx.ListCtrl(self, style=wx.LC_REPORT | wx.LC_SINGLE_SEL)
        self.list.InsertColumn(0, "键 / 索引", width=200)
        self.list.InsertColumn(1, "值", width=420)
        top.Add(self.list, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 6)

        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.btn_add = wx.Button(self, label="新增")
        self.btn_edit = wx.Button(self, label="编辑值")
        self.btn_rename = wx.Button(self, label="重命名")
        self.btn_del = wx.Button(self, label="删除")
        self.btn_up_item = wx.Button(self, label="↑ 上移")
        self.btn_down_item = wx.Button(self, label="↓ 下移")
        btn_sizer.Add(self.btn_add, 0, wx.RIGHT, 4)
        btn_sizer.Add(self.btn_edit, 0, wx.RIGHT, 4)
        btn_sizer.Add(self.btn_rename, 0, wx.RIGHT, 4)
        btn_sizer.Add(self.btn_del, 0, wx.RIGHT, 4)
        btn_sizer.Add(self.btn_up_item, 0, wx.RIGHT, 4)
        btn_sizer.Add(self.btn_down_item, 0, wx.RIGHT, 4)
        top.Add(btn_sizer, 0, wx.ALL, 6)

        self.SetSizer(top)

        self.btn_up.Bind(wx.EVT_BUTTON, self.on_go_up)
        self.btn_add.Bind(wx.EVT_BUTTON, self.on_add)
        self.btn_edit.Bind(wx.EVT_BUTTON, self.on_edit)
        self.btn_rename.Bind(wx.EVT_BUTTON, self.on_rename)
        self.btn_del.Bind(wx.EVT_BUTTON, self.on_delete)
        self.btn_up_item.Bind(wx.EVT_BUTTON, lambda e: self.on_move(-1))
        self.btn_down_item.Bind(wx.EVT_BUTTON, lambda e: self.on_move(1))
        self.list.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self.on_activate)
        self.filter_input.Bind(wx.EVT_TEXT, self._on_filter)
        self.filter_input.Bind(wx.EVT_KEY_DOWN, self._on_filter_key)

    def open_root(self, file_id=""):
        self.file_id = file_id
        self.path = []
        self.filter_input.SetValue("")
        self.refresh()

    def navigate_to(self, path):
        self.path = list(path)
        self.filter_input.SetValue("")
        self.refresh()

    def _current_node(self):
        node = self.manager.data
        for seg in self.path:
            try:
                if isinstance(node, dict):
                    node = node.get(seg)
                elif isinstance(node, list):
                    node = node[seg]
                else:
                    return None
            except Exception:
                return None
        return node

    def refresh(self):
        self._rebuild_breadcrumb()
        node = self._current_node()
        self.list.DeleteAllItems()
        self._keys = []

        if node is None:
            self.title.SetLabel("（节点不存在）")
            self._set_buttons(False, False, False, False, False)
            return

        is_dict = isinstance(node, dict)
        is_list = isinstance(node, list)

        if is_dict:
            self.title.SetLabel(f"对象（{len(node)} 个字段）")
            items = list(node.items())
        elif is_list:
            self.title.SetLabel(f"数组（{len(node)} 项）")
            items = list(enumerate(node))
        else:
            self.title.SetLabel(f"标量值：{_node_summary(node)}")
            self._set_buttons(False, False, False, False, False)
            return

        filt = self.filter_input.GetValue().strip().lower()
        for k, v in items:
            label = str(k)
            if filt and filt not in label.lower():
                if not (isinstance(v, dict) and filt in str(v.get("name", "")).lower()):
                    continue
            idx = self.list.InsertItem(self.list.GetItemCount(), label)
            self.list.SetItem(idx, 1, _node_summary(v))
            self._keys.append(k)

        self._set_buttons(
            add=True,
            edit=(self.list.GetItemCount() > 0),
            rename=is_dict and (self.list.GetItemCount() > 0),
            delete=(self.list.GetItemCount() > 0),
            reorder=is_list and (self.list.GetItemCount() > 0),
        )

    def _set_buttons(self, add, edit, rename, delete, reorder):
        self.btn_add.Enable(add)
        self.btn_edit.Enable(edit)
        self.btn_rename.Enable(rename)
        self.btn_del.Enable(delete)
        self.btn_up_item.Enable(reorder)
        self.btn_down_item.Enable(reorder)

    def _rebuild_breadcrumb(self):
        for child in self.crumb_panel.GetChildren():
            child.Destroy()
        self.crumb_sizer.Clear(delete_windows=False)

        root_btn = wx.Button(self.crumb_panel, label=self.file_id or "root", style=wx.BU_EXACTFIT)
        self.crumb_sizer.Add(root_btn, 0, wx.RIGHT, 4)
        root_btn.Bind(wx.EVT_BUTTON, lambda e: self.navigate_to([]))

        for i, seg in enumerate(self.path):
            sep = wx.StaticText(self.crumb_panel, label="›")
            self.crumb_sizer.Add(sep, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4)
            btn = wx.Button(self.crumb_panel, label=str(seg), style=wx.BU_EXACTFIT)
            self.crumb_sizer.Add(btn, 0, wx.RIGHT, 4)
            btn.Bind(wx.EVT_BUTTON, lambda e, p=i + 1: self.navigate_to(self.path[:p]))

        self.btn_up.Enable(len(self.path) > 0)
        self.crumb_panel.Layout()
        self.Layout()

    def _selected_key(self):
        idx = self.list.GetFirstSelected()
        if idx == -1 or idx >= len(self._keys):
            return None
        return self._keys[idx]

    def _notify_dirty(self):
        if self.on_dirty_change:
            self.on_dirty_change()

    def on_activate(self, event):
        key = self._selected_key()
        if key is None:
            return
        node = self._current_node()
        if isinstance(node, dict):
            value = node.get(key)
        elif isinstance(node, list):
            value = node[key]
        else:
            return
        if isinstance(value, (dict, list)):
            self.path.append(key)
            self.filter_input.SetValue("")
            self.refresh()
        else:
            self._edit_value(key)

    def on_go_up(self, event):
        if self.path:
            self.path.pop()
            self.refresh()

    def _edit_value(self, key):
        node = self._current_node()
        value = node.get(key) if isinstance(node, dict) else node[key]
        dlg = StructuredValueDialog(self, "编辑值", value=value, name=str(key), require_name=False)
        if dlg.ShowModal() == wx.ID_OK:
            new_val = dlg.get_value()
            self.manager.push_snapshot()
            if isinstance(node, dict):
                node[key] = new_val
            else:
                node[key] = new_val
            self.refresh()
            self._notify_dirty()
        dlg.Destroy()

    def on_edit(self, event):
        key = self._selected_key()
        if key is None:
            wx.MessageBox("请先选择一项", "提示", wx.OK | wx.ICON_WARNING)
            return
        self._edit_value(key)

    def on_add(self, event):
        node = self._current_node()
        if isinstance(node, dict):
            name = wx.GetTextFromUser("输入新键名：", "新增字段", "", self)
            name = name.strip()
            if not name:
                return
            if name in node:
                wx.MessageBox("键名已存在", "提示", wx.OK | wx.ICON_WARNING)
                return
            dlg = StructuredValueDialog(self, "初始值", value="", require_name=False)
            if dlg.ShowModal() != wx.ID_OK:
                dlg.Destroy()
                return
            self.manager.push_snapshot()
            node[name] = dlg.get_value()
            dlg.Destroy()
            self.filter_input.SetValue("")
            self.refresh()
            self._select_key(name)
            self._notify_dirty()
        elif isinstance(node, list):
            dlg = StructuredValueDialog(self, "新增项", value="", require_name=False)
            if dlg.ShowModal() == wx.ID_OK:
                self.manager.push_snapshot()
                node.append(dlg.get_value())
                dlg.Destroy()
                self.filter_input.SetValue("")
                self.refresh()
                self._select_index(len(node) - 1)
                self._notify_dirty()
            else:
                dlg.Destroy()

    def on_rename(self, event):
        key = self._selected_key()
        if key is None:
            wx.MessageBox("请先选择要重命名的字段", "提示", wx.OK | wx.ICON_WARNING)
            return
        node = self._current_node()
        if not isinstance(node, dict):
            return
        new_name = wx.GetTextFromUser("新键名：", "重命名", str(key), self)
        new_name = new_name.strip()
        if not new_name or new_name == str(key):
            return
        if new_name in node:
            wx.MessageBox("键名已存在", "提示", wx.OK | wx.ICON_WARNING)
            return
        self.manager.push_snapshot()
        preserve = list(node.items())
        node.clear()
        for k, v in preserve:
            node[new_name if k == key else k] = v
        self.refresh()
        self._select_key(new_name)
        self._notify_dirty()

    def on_delete(self, event):
        key = self._selected_key()
        if key is None:
            wx.MessageBox("请先选择要删除的项", "提示", wx.OK | wx.ICON_WARNING)
            return
        if wx.MessageBox(f"确定删除 \"{key}\"？", "确认", wx.YES_NO | wx.ICON_QUESTION) != wx.YES:
            return
        node = self._current_node()
        self.manager.push_snapshot()
        if isinstance(node, dict):
            del node[key]
        elif isinstance(node, list):
            del node[key]
        self.refresh()
        self._notify_dirty()

    def on_move(self, direction):
        key = self._selected_key()
        if key is None:
            return
        node = self._current_node()
        if not isinstance(node, list):
            return
        idx = key
        new_idx = idx + direction
        if new_idx < 0 or new_idx >= len(node):
            return
        self.manager.push_snapshot()
        node[idx], node[new_idx] = node[new_idx], node[idx]
        self.refresh()
        self._select_index(new_idx)
        self._notify_dirty()

    def _select_key(self, key):
        if key in self._keys:
            self._select_index(self._keys.index(key))

    def _select_index(self, idx):
        if 0 <= idx < self.list.GetItemCount():
            self.list.Select(idx)
            self.list.EnsureVisible(idx)

    def _on_filter(self, event):
        self.refresh()

    def _on_filter_key(self, event):
        if event.GetKeyCode() == wx.WXK_RETURN:
            self.list.SetFocus()
            if self.list.GetItemCount() > 0:
                self.list.Select(0)
            return
        event.Skip()
