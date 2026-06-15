import wx

from map_data import EVT_MAP_DATA
from dialogs.object_dialog import ObjectDialog

import TTS


class ObjectManagerDialog(wx.Frame):
    TILE_SIZE = 32

    def __init__(self, parent, data_manager):
        super().__init__(parent, title="对象管理器", size=(620, 420))
        self.parent = parent
        self.data_manager = data_manager
        self._editing = False
        self._closed = False

        panel = wx.Panel(self)
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        self.obj_list = wx.ListCtrl(panel, style=wx.LC_REPORT | wx.LC_SINGLE_SEL)
        self.obj_list.InsertColumn(0, "ID", width=50)
        self.obj_list.InsertColumn(1, "名称", width=140)
        self.obj_list.InsertColumn(2, "类型", width=100)
        self.obj_list.InsertColumn(3, "坐标", width=70)
        self.obj_list.InsertColumn(4, "属性数量", width=80)
        main_sizer.Add(self.obj_list, 1, wx.EXPAND | wx.ALL, 5)

        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.btn_jump = wx.Button(panel, label="跳转 &J")
        self.btn_edit = wx.Button(panel, label="编辑 &E")
        self.btn_delete = wx.Button(panel, label="删除 &D")
        self.btn_close = wx.Button(panel, label="关闭 &C")
        for btn in (self.btn_jump, self.btn_edit, self.btn_delete, self.btn_close):
            btn_sizer.Add(btn, 1, wx.RIGHT, 5)
        main_sizer.Add(btn_sizer, 0, wx.EXPAND | wx.ALL, 10)

        panel.SetSizer(main_sizer)
        self.populate_list()
        self.obj_list.SetFocus()

        self.obj_list.Bind(wx.EVT_LIST_ITEM_SELECTED, self.on_selection_changed)
        self.obj_list.Bind(wx.EVT_KEY_DOWN, self.on_list_keydown)
        self.btn_jump.Bind(wx.EVT_BUTTON, self.on_jump)
        self.btn_edit.Bind(wx.EVT_BUTTON, self.on_edit)
        self.btn_delete.Bind(wx.EVT_BUTTON, self.on_delete)
        self.btn_close.Bind(wx.EVT_BUTTON, self.on_close)
        self.Bind(wx.EVT_CLOSE, self.on_close)

        self.data_manager.Bind(EVT_MAP_DATA, self.on_data_changed)

        self.Show()

    def on_data_changed(self, event):
        if self._closed:
            return
        kind = event.kind
        if kind in (
            "object_added",
            "object_removed",
            "object_modified",
            "objects_cleared",
            "map_loaded",
            "map_cleared",
            "map_resized",
        ):
            self.refresh_list()
        event.Skip()

    def populate_list(self):
        self.obj_list.DeleteAllItems()
        for obj in self.data_manager.get_active_objects():
            tile_x = obj.get("x", 0) // self.TILE_SIZE
            tile_y = obj.get("y", 0) // self.TILE_SIZE
            idx = self.obj_list.InsertItem(
                self.obj_list.GetItemCount(), str(obj.get("id", ""))
            )
            self.obj_list.SetItem(idx, 1, obj.get("name", ""))
            self.obj_list.SetItem(idx, 2, obj.get("type", ""))
            self.obj_list.SetItem(idx, 3, f"{tile_x},{tile_y}")
            self.obj_list.SetItem(idx, 4, str(len(obj.get("properties", {}))))

    def refresh_list(self, select_id=None):
        self.populate_list()
        if select_id is not None:
            for i in range(self.obj_list.GetItemCount()):
                if self.obj_list.GetItemText(i, 0) == str(select_id):
                    self.obj_list.Select(i)
                    self.obj_list.EnsureVisible(i)
                    break

    def _get_selected_obj(self):
        idx = self.obj_list.GetFirstSelected()
        if idx == -1:
            return None
        try:
            obj_id = int(self.obj_list.GetItemText(idx, 0))
        except ValueError:
            return None
        return self.data_manager.find_object_by_id(obj_id)

    def on_selection_changed(self, event):
        event.Skip()

    def on_list_keydown(self, event):
        key = event.GetKeyCode()
        if key == wx.WXK_RETURN:
            self.on_jump(None)
        elif key == wx.WXK_DELETE:
            self.on_delete(None)
        elif key in (ord("E"), ord("e")):
            self.on_edit(None)
        else:
            event.Skip()

    def on_jump(self, event):
        obj = self._get_selected_obj()
        if not obj:
            wx.MessageBox("请先选择一个对象！", "提示", wx.OK | wx.ICON_WARNING)
            return
        col = obj.get("x", 0) // self.TILE_SIZE
        row = obj.get("y", 0) // self.TILE_SIZE
        p = self.parent
        if row >= p.data_manager.height or col >= p.data_manager.width:
            TTS.cancel()
            TTS.speak("对象坐标超出地图范围")
            return
        p.cursor_x = col
        p.cursor_y = row
        p.grid.SetGridCursor(row, col)
        p.grid.SelectBlock(row, col, row, col)
        p.grid.MakeCellVisible(row, col)
        p.update_status()
        p.Raise()

    def on_edit(self, event):
        obj = self._get_selected_obj()
        if not obj:
            wx.MessageBox("请先选择一个对象！", "提示", wx.OK | wx.ICON_WARNING)
            return
        if self._editing:
            return
        self._editing = True
        try:
            obj_id = obj.get("id")
            dlg = ObjectDialog(
                self, obj_data=obj, is_edit=True, next_id=self.data_manager.next_object_id
            )
            if dlg.ShowModal() == wx.ID_OK:
                new_data = dlg.get_object_data()
                self.data_manager.modify_object(obj_id, new_data)
                TTS.cancel()
                TTS.speak(f"已编辑对象：{new_data.get('name', '')}")
            dlg.Destroy()
        finally:
            self._editing = False

    def on_delete(self, event):
        obj = self._get_selected_obj()
        if not obj:
            wx.MessageBox("请先选择一个对象！", "提示", wx.OK | wx.ICON_WARNING)
            return
        result = wx.MessageBox(
            f'确定要删除对象 "{obj.get("name", "")}" 吗？',
            "确认",
            wx.YES_NO | wx.ICON_QUESTION,
        )
        if int(result) == 2:
            self.data_manager.remove_object(obj.get("id"))
            TTS.cancel()
            TTS.speak("已删除对象")

    def on_close(self, event):
        self._closed = True
        self.parent.object_manager_dlg = None
        self.Destroy()
