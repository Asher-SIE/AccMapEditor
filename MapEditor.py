import copy
import ctypes
import json
import os
import re
import TTS
import wx
import wx.grid as gridlib

from map_data import MapDataManager, EVT_MAP_DATA, MapDataEvent, TILE_SIZE
from map_data.commands import TILE_SIZE as CMD_TILE_SIZE
from dialogs.object_dialog import ObjectDialog
from dialogs.object_manager import ObjectManagerDialog


TILE_DEFINITIONS = {}

CLIPBOARD = None


class TileSelectionDialog(wx.Dialog):
    def __init__(self, parent, tile_defs):
        super().__init__(parent, title="选择瓦片")
        sizer = wx.BoxSizer(wx.VERTICAL)
        choices = []
        for k, v in sorted(tile_defs.items(), key=lambda x: int(x[0])):
            if isinstance(v, dict):
                name = v.get("name", "")
                props = v.get("properties", {})
            else:
                name = v
                props = {}

            if props:
                prop_str = ", ".join(
                    [f"{p_k}={p_v}" for p_k, p_v in props.items()]
                )
                choices.append(f"{k}: {name} ({prop_str})")
            else:
                choices.append(f"{k}: {name}")
        self.listbox = wx.ListBox(self, choices=choices)
        self.listbox.SetSelection(0)
        sizer.Add(self.listbox, 1, wx.ALL | wx.EXPAND, 10)

        btn_sizer = self.CreateButtonSizer(wx.OK | wx.CANCEL)
        sizer.Add(btn_sizer, 0, wx.ALL | wx.EXPAND, 10)
        self.SetSizer(sizer)
        self.listbox.SetFocus()
        self.tile_keys = list(sorted(tile_defs.keys(), key=lambda x: int(x)))

    def GetSelectedTileId(self):
        sel = self.listbox.GetSelection()
        if sel != wx.NOT_FOUND:
            return self.tile_keys[sel]
        return 0


class ResizeDialog(wx.Dialog):
    def __init__(self, parent, current_w, current_h):
        super().__init__(parent, title="调整地图尺寸")
        sizer = wx.BoxSizer(wx.VERTICAL)

        w_sizer = wx.BoxSizer(wx.HORIZONTAL)
        w_sizer.Add(
            wx.StaticText(self, label="宽度:"),
            0,
            wx.ALIGN_CENTER_VERTICAL | wx.RIGHT,
            5,
        )
        self.width_ctrl = wx.SpinCtrl(
            self, value=str(current_w), min=1, max=1000
        )
        w_sizer.Add(self.width_ctrl, 0)
        sizer.Add(w_sizer, 0, wx.ALL, 5)

        h_sizer = wx.BoxSizer(wx.HORIZONTAL)
        h_sizer.Add(
            wx.StaticText(self, label="高度:"),
            0,
            wx.ALIGN_CENTER_VERTICAL | wx.RIGHT,
            5,
        )
        self.height_ctrl = wx.SpinCtrl(
            self, value=str(current_h), min=1, max=1000
        )
        h_sizer.Add(self.height_ctrl, 0)
        sizer.Add(h_sizer, 0, wx.ALL, 5)

        btn_sizer = self.CreateButtonSizer(wx.OK | wx.CANCEL)
        sizer.Add(btn_sizer, 0, wx.ALL | wx.EXPAND, 10)
        self.SetSizer(sizer)

    def get_size(self):
        return self.width_ctrl.GetValue(), self.height_ctrl.GetValue()


class TileInputDialog(wx.Dialog):
    def __init__(self, parent, tile_id="", tile_name="", is_edit=False):
        title = "编辑瓦片" if is_edit else "添加瓦片"
        super().__init__(parent, title=title)

        sizer = wx.BoxSizer(wx.VERTICAL)

        sizer.Add(wx.StaticText(self, label="瓦片ID："), 0, wx.ALL, 5)
        self.id_input = wx.TextCtrl(self, value=tile_id)
        sizer.Add(self.id_input, 0, wx.EXPAND | wx.ALL, 5)

        sizer.Add(wx.StaticText(self, label="瓦片名称："), 0, wx.ALL, 5)
        self.name_input = wx.TextCtrl(self, value=tile_name)
        sizer.Add(self.name_input, 0, wx.EXPAND | wx.ALL, 5)

        btn_sizer = self.CreateButtonSizer(wx.OK | wx.CANCEL)
        sizer.Add(btn_sizer, 0, wx.EXPAND | wx.ALL, 10)

        self.SetSizer(sizer)
        self.id_input.SetFocus()


class PropertyDialog(wx.Dialog):
    def __init__(self, parent, properties=None):
        super().__init__(parent, title="编辑属性")
        self.properties = properties if properties else {}

        sizer = wx.BoxSizer(wx.VERTICAL)

        sizer.Add(wx.StaticText(self, label="属性列表："), 0, wx.ALL, 5)

        self.prop_list = wx.ListBox(self, style=wx.LB_SINGLE)
        self.refresh_prop_list()
        sizer.Add(self.prop_list, 1, wx.EXPAND | wx.ALL, 5)

        input_sizer = wx.FlexGridSizer(rows=1, cols=2, hgap=5, vgap=5)
        self.name_input = wx.TextCtrl(self, value="属性名")
        self.value_input = wx.TextCtrl(self, value="属性值")
        input_sizer.Add(self.name_input, 1, wx.EXPAND)
        input_sizer.Add(self.value_input, 1, wx.EXPAND)
        sizer.Add(input_sizer, 0, wx.EXPAND | wx.ALL, 5)

        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        btn_add = wx.Button(self, label="添加属性")
        btn_del = wx.Button(self, label="删除")
        btn_ok = wx.Button(self, id=wx.ID_OK)

        btn_sizer.Add(btn_add, 1, wx.RIGHT, 5)
        btn_sizer.Add(btn_del, 1, wx.RIGHT, 5)
        btn_sizer.Add(btn_ok, 1)
        sizer.Add(btn_sizer, 0, wx.EXPAND | wx.ALL, 5)

        self.SetSizer(sizer)
        self.SetSize((400, 300))

        self.Bind(wx.EVT_BUTTON, self.on_add, btn_add)
        self.Bind(wx.EVT_BUTTON, self.on_delete, btn_del)

    def refresh_prop_list(self):
        self.prop_list.Clear()
        for name, value in self.properties.items():
            self.prop_list.Append(f"{name}={value}")

    def on_add(self, event):
        name = self.name_input.GetValue().strip()
        value = self.value_input.GetValue().strip()
        if not name:
            wx.MessageBox("请输入属性名！", "提示", wx.OK | wx.ICON_WARNING)
            return
        self.properties[name] = value
        self.name_input.SetValue("")
        self.value_input.SetValue("")
        self.refresh_prop_list()

    def on_delete(self, event):
        sel = self.prop_list.GetSelection()
        if sel == wx.NOT_FOUND:
            wx.MessageBox("请先选择要删除的属性！", "提示", wx.OK | wx.ICON_WARNING)
            return
        text = self.prop_list.GetString(sel)
        name = text.split("=")[0]
        del self.properties[name]
        self.refresh_prop_list()

    def get_properties(self):
        return self.properties


class MapPropertiesDialog(wx.Dialog):
    def __init__(self, parent, map_properties):
        super().__init__(parent, title="编辑地图属性")

        self.map_properties = map_properties.copy()

        sizer = wx.BoxSizer(wx.VERTICAL)

        sizer.Add(wx.StaticText(self, label="属性列表："), 0, wx.ALL, 5)

        self.prop_list = wx.ListBox(self, style=wx.LB_SINGLE, size=(-1, 120))
        self.refresh_prop_list()
        sizer.Add(self.prop_list, 1, wx.EXPAND | wx.ALL, 5)

        input_sizer = wx.FlexGridSizer(rows=2, cols=2, hgap=5, vgap=5)
        input_sizer.Add(wx.StaticText(self, label="名称:"))
        self.name_input = wx.TextCtrl(self)
        input_sizer.Add(self.name_input, 1, wx.EXPAND)
        input_sizer.Add(wx.StaticText(self, label="值:"))
        self.value_input = wx.TextCtrl(self)
        input_sizer.Add(self.value_input, 1, wx.EXPAND)
        sizer.Add(input_sizer, 0, wx.EXPAND | wx.ALL, 5)

        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        btn_add = wx.Button(self, label="添加/更新")
        btn_del = wx.Button(self, label="删除选中")
        btn_sizer.Add(btn_add, 1, wx.RIGHT, 5)
        btn_sizer.Add(btn_del, 1)
        sizer.Add(btn_sizer, 0, wx.EXPAND | wx.ALL, 5)

        btn_sizer2 = self.CreateButtonSizer(wx.OK | wx.CANCEL)
        sizer.Add(btn_sizer2, 0, wx.EXPAND | wx.ALL, 5)

        self.SetSizer(sizer)
        self.SetSize((400, 350))

        self.Bind(wx.EVT_BUTTON, self.on_add, btn_add)
        self.Bind(wx.EVT_BUTTON, self.on_delete, btn_del)
        self.Bind(wx.EVT_LISTBOX, self.on_select, self.prop_list)

    def refresh_prop_list(self):
        self.prop_list.Clear()
        for name, value in self.map_properties.items():
            self.prop_list.Append(f"{name} = {value}")

    def on_select(self, event):
        text = self.prop_list.GetString(self.prop_list.GetSelection())
        if " = " in text:
            name, value = text.split(" = ", 1)
            self.name_input.SetValue(name)
            self.value_input.SetValue(value)

    def on_add(self, event):
        name = self.name_input.GetValue().strip()
        value = self.value_input.GetValue().strip()
        if not name:
            wx.MessageBox("请输入属性名称！", "提示", wx.OK | wx.ICON_WARNING)
            return
        self.map_properties[name] = value
        self.refresh_prop_list()

    def on_delete(self, event):
        sel = self.prop_list.GetSelection()
        if sel == wx.NOT_FOUND:
            wx.MessageBox("请先选择要删除的属性！", "提示", wx.OK | wx.ICON_WARNING)
            return
        text = self.prop_list.GetString(sel)
        if " = " in text:
            name = text.split(" = ")[0]
            del self.map_properties[name]
            self.refresh_prop_list()

    def get_properties(self):
        return self.map_properties


class CustomTileDialog(wx.Frame):
    def __init__(self, parent, tile_defs):
        super().__init__(parent, title="编辑瓦片", size=(800, 600))
        self.tile_data = copy.deepcopy(tile_defs)
        self.parent = parent
        self.selected_tile_id = None

        self.Bind(wx.EVT_SHOW, self.on_show)
        self.Bind(wx.EVT_CLOSE, self.on_close)

        panel = wx.Panel(self)
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        main_sizer.Add(
            wx.StaticText(panel, label="瓦片列表（ID: 名称） &T"), 0, wx.ALL, 5
        )
        self.tile_list = wx.ListBox(panel, style=wx.LB_SINGLE)
        self.refresh_list()
        main_sizer.Add(self.tile_list, 1, wx.EXPAND | wx.ALL, 5)

        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.btn_edit = wx.Button(panel, label="编辑 &E")
        self.btn_add = wx.Button(panel, label="添加 &A")
        self.btn_del = wx.Button(panel, label="删除 &D")
        self.btn_prop = wx.Button(panel, label="属性 &P")
        self.btn_save = wx.Button(panel, label="保存并关闭 &S")

        btn_sizer.Add(self.btn_edit, 1, wx.RIGHT, 5)
        btn_sizer.Add(self.btn_add, 1, wx.RIGHT, 5)
        btn_sizer.Add(self.btn_del, 1, wx.RIGHT, 5)
        btn_sizer.Add(self.btn_prop, 1, wx.RIGHT, 5)
        btn_sizer.Add(self.btn_save, 1)
        main_sizer.Add(btn_sizer, 0, wx.EXPAND | wx.ALL, 10)

        panel.SetSizer(main_sizer)

        self.Bind(wx.EVT_BUTTON, self.on_edit, self.btn_edit)
        self.Bind(wx.EVT_BUTTON, self.on_add, self.btn_add)
        self.Bind(wx.EVT_BUTTON, self.on_delete, self.btn_del)
        self.Bind(wx.EVT_BUTTON, self.on_property, self.btn_prop)
        self.Bind(wx.EVT_BUTTON, self.on_save, self.btn_save)
        self.Bind(wx.EVT_LISTBOX, self.on_list_select, self.tile_list)

    def on_show(self, event):
        if event.IsShown():
            wx.CallAfter(self.tile_list.SetFocus)
        event.Skip()

    def refresh_list(self):
        self.tile_list.Clear()
        sorted_items = sorted(self.tile_data.items(), key=lambda x: int(x[0]))
        for tid, data in sorted_items:
            if isinstance(data, dict):
                name = data.get("name", "")
                props = data.get("properties", {})
            else:
                name = data
                props = {}

            if props:
                prop_str = ", ".join([f"{k}={v}" for k, v in props.items()])
                display = f"{tid}: {name} ({prop_str})"
            else:
                display = f"{tid}: {name}"

            self.tile_list.Append(display)

    def on_list_select(self, event):
        sel = self.tile_list.GetSelection()
        if sel != wx.NOT_FOUND:
            text = self.tile_list.GetString(sel)
            self.selected_tile_id = text.split(":")[0].strip()
        event.Skip()

    def on_edit(self, event):
        if not self.selected_tile_id:
            wx.MessageBox("请先选择要编辑的瓦片！", "提示", wx.OK | wx.ICON_WARNING)
            return

        tile_data = self.tile_data.get(self.selected_tile_id, {})
        if isinstance(tile_data, dict):
            tile_name = tile_data.get("name", "")
        else:
            tile_name = tile_data

        dlg = TileInputDialog(
            self, self.selected_tile_id, tile_name, is_edit=True
        )
        if dlg.ShowModal() == wx.ID_OK:
            new_id = dlg.id_input.GetValue().strip()
            new_name = dlg.name_input.GetValue().strip()
            if new_id and new_name:
                old_data = self.tile_data.pop(
                    self.selected_tile_id, {"name": "", "properties": {}}
                )
                if isinstance(old_data, str):
                    old_data = {"name": old_data, "properties": {}}
                properties = old_data.get("properties", {})
                self.tile_data[new_id] = {"name": new_name, "properties": properties}
                self.refresh_list()
        dlg.Destroy()

    def on_add(self, event):
        max_id = (
            max([int(k) for k in self.tile_data.keys()]) if self.tile_data else -1
        )
        next_id = str(max_id + 1)

        dlg = TileInputDialog(self, next_id, "", is_edit=False)
        if dlg.ShowModal() == wx.ID_OK:
            new_id = dlg.id_input.GetValue().strip()
            new_name = dlg.name_input.GetValue().strip()
            if new_id and new_name:
                self.tile_data[new_id] = {"name": new_name, "properties": {}}
                self.refresh_list()
        dlg.Destroy()

    def on_delete(self, event):
        if not self.selected_tile_id:
            wx.MessageBox("请先选择要删除的瓦片！", "提示", wx.OK | wx.ICON_WARNING)
            return

        del self.tile_data[self.selected_tile_id]
        self.selected_tile_id = None
        self.refresh_list()

    def on_property(self, event):
        if not self.selected_tile_id:
            wx.MessageBox(
                "请先选择要编辑属性的瓦片！", "提示", wx.OK | wx.ICON_WARNING
            )
            return

        tile_data = self.tile_data.get(self.selected_tile_id, {})
        if isinstance(tile_data, dict):
            properties = tile_data.get("properties", {}).copy()
        else:
            properties = {}

        dlg = PropertyDialog(self, properties)
        if dlg.ShowModal() == wx.ID_OK:
            new_properties = dlg.get_properties()
            if isinstance(tile_data, dict):
                tile_data["properties"] = new_properties
            else:
                self.tile_data[self.selected_tile_id] = {
                    "name": tile_data,
                    "properties": new_properties,
                }
            self.refresh_list()
        dlg.Destroy()

    def on_save(self, event):
        with open("./tile_definitions.json", "w", encoding="utf-8") as f:
            json.dump(self.tile_data, f, ensure_ascii=False, indent=4)
        wx.MessageBox("保存成功！", "提示", wx.OK)
        self.notify_parent()
        self.Destroy()

    def on_close(self, event):
        result = wx.MessageBox(
            "确定要退出吗？", "提示", wx.YES_NO | wx.ICON_QUESTION
        )
        if result == 8:
            return
        self.notify_parent()
        self.Destroy()

    def notify_parent(self):
        self.parent.enable_and_update(self.tile_data.copy())


class MapEditorFrame(wx.Frame):
    def __init__(self):
        style = wx.DEFAULT_FRAME_STYLE & ~wx.RESIZE_BORDER & ~wx.MAXIMIZE_BOX
        super().__init__(
            None, title="地图编辑器 V1.0", size=(1366, 768), style=style
        )

        try:
            hwnd = self.GetHandle()
            if hwnd:
                GWL_STYLE = -16
                WS_SYSMENU = 0x00080000
                current = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_STYLE)
                new_style = current & ~WS_SYSMENU
                ctypes.windll.user32.SetWindowLongW(hwnd, GWL_STYLE, new_style)
                ctypes.windll.user32.DrawMenuBar(hwnd)
        except Exception:
            pass

        self.data_manager = MapDataManager()

        self.cursor_x = 0
        self.cursor_y = 0
        self.current_file = None

        global TILE_DEFINITIONS
        TILE_DEFINITIONS = self.load_tiled_data()
        self.tile_definitions = TILE_DEFINITIONS.copy()
        self.data_manager.tile_definitions = self.tile_definitions

        self.selection_start = None
        self.selection_end = None

        self.object_manager_dlg = None
        self.object_clipboard = None

        self.init_ui()
        self.create_menu()
        self._subscribe_events()
        self.update_status()
        TTS.init_engine()
        TTS.speak("编辑器启动")

    def _subscribe_events(self):
        self.data_manager.Bind(EVT_MAP_DATA, self._on_map_data_changed)

    def _on_map_data_changed(self, event):
        kind = event.kind
        if kind in ("tiles_changed", "collision_changed"):
            for x, y in event.data.get("cells", []):
                self._refresh_cell(x, y)
        elif kind == "object_added":
            self._refresh_cells_for_object(event.data.get("object"))
        elif kind == "object_removed":
            self._refresh_cells_for_object(event.data.get("object"))
        elif kind == "object_modified":
            old = event.data.get("old_object")
            new = event.data.get("new_object")
            if old:
                self._refresh_cells_for_object(old)
            if new:
                self._refresh_cells_for_object(new)
        elif kind in ("objects_cleared", "map_loaded", "map_cleared"):
            self.rebuild_grid()

        if not getattr(self, "_silent_status", False):
            self.update_status()
        event.Skip()

    def _refresh_cell(self, x, y):
        dm = self.data_manager
        if 0 <= x < dm.width and 0 <= y < dm.height:
            self.grid.SetCellValue(y, x, dm.get_cell_display(x, y))

    def _refresh_cells_for_object(self, obj):
        if not obj:
            return
        dm = self.data_manager
        tx, ty, tw, th = dm.get_object_tile_rect(obj)
        for dy in range(th):
            for dx in range(tw):
                cx, cy = tx + dx, ty + dy
                if 0 <= cx < dm.width and 0 <= cy < dm.height:
                    self._refresh_cell(cx, cy)

    def load_tiled_data(self):
        config_file = "./tile_definitions.json"
        default_config = {
            "0": {"name": "空地", "properties": {}},
            "1": {"name": "墙壁", "properties": {}},
        }

        try:
            if not os.path.exists(config_file):
                print(f"配置文件不存在，创建新文件: {config_file}")
                with open(config_file, "w", encoding="utf-8") as f:
                    json.dump(default_config, f, ensure_ascii=False, indent=4)
                print("已创建默认配置文件")
                return default_config

            with open(config_file, "r", encoding="utf-8") as f:
                content = f.read()

                if not content.strip():
                    print("配置文件为空，创建默认配置")
                    with open(config_file, "w", encoding="utf-8") as f_write:
                        json.dump(default_config, f_write, ensure_ascii=False, indent=4)
                    print(" 已填充默认配置")
                    return default_config

                data = json.loads(content)

                if not isinstance(data, dict):
                    print("配置文件格式错误，重置为默认配置")
                    return default_config

                result = {}
                for k, v in data.items():
                    if isinstance(v, str):
                        result[str(k)] = {"name": v, "properties": {}}
                    else:
                        result[str(k)] = v

                return result

        except json.JSONDecodeError as e:
            print(f"JSON解析错误: {e}")
            return default_config
        except Exception as e:
            print(f"加载配置文件时发生错误: {e}")
            return default_config

    def init_ui(self):
        panel = wx.Panel(self)
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        self.status_label = wx.StaticText(panel, label="")
        main_sizer.Add(self.status_label, 0, wx.ALL, 5)

        self.grid = gridlib.Grid(panel)
        self.grid.CreateGrid(self.data_manager.height, self.data_manager.width)

        self.grid.EnableEditing(False)
        self.grid.SetDefaultCellAlignment(wx.ALIGN_CENTER, wx.ALIGN_CENTER)
        self.grid.SetRowLabelSize(40)
        self.grid.SetColLabelSize(30)

        self.grid.Bind(wx.EVT_KEY_DOWN, self.on_key_down)
        self.grid.Bind(gridlib.EVT_GRID_SELECT_CELL, self.on_grid_select)

        main_sizer.Add(self.grid, 1, wx.EXPAND | wx.ALL, 5)
        panel.SetSizer(main_sizer)
        self.grid.SetFocus()

    def create_menu(self):
        menubar = wx.MenuBar()

        file_menu = wx.Menu()
        open_item = file_menu.Append(wx.ID_OPEN, "打开...\tCtrl+O")
        close_item = file_menu.Append(wx.ID_ANY, "关闭当前文件\t&L")
        save_item = file_menu.Append(wx.ID_SAVE, "保存...\tCtrl+S")
        resize_item = file_menu.Append(wx.ID_ANY, "调整地图尺寸...\t&R")
        custom_tile_item = file_menu.Append(wx.ID_ANY, "编辑瓦片...\t&C")
        map_prop_item = file_menu.Append(wx.ID_ANY, "编辑地图属性...\t&M")
        file_menu.AppendSeparator()
        exit_item = file_menu.Append(wx.ID_EXIT, "退出\t&X")

        edit_menu = wx.Menu()
        undo_item = edit_menu.Append(wx.ID_UNDO, "撤销\tCtrl+Z")
        redo_item = edit_menu.Append(wx.ID_REDO, "重做\tCtrl+Y")
        edit_menu.AppendSeparator()
        goto_item = edit_menu.Append(wx.ID_ANY, "跳转单元格...\tCtrl+G")
        edit_menu.AppendSeparator()
        clear_item = edit_menu.Append(wx.ID_ANY, "清除选区\tEsc")
        delete_item = edit_menu.Append(wx.ID_ANY, "清除单元格\tBackspace")
        select_tile_item = edit_menu.Append(wx.ID_ANY, "选择瓦片\tEnter")
        selection_start_item = edit_menu.Append(
            wx.ID_ANY, "选区开始点\tShift+Enter"
        )
        selection_end_item = edit_menu.Append(
            wx.ID_ANY, "选区结束点\tCtrl+Enter"
        )
        fill_item = edit_menu.Append(wx.ID_ANY, "填充选区\tCtrl+F")
        edit_menu.AppendSeparator()
        copy_item = edit_menu.Append(wx.ID_ANY, "复制\tCtrl+C")
        cut_item = edit_menu.Append(wx.ID_ANY, "剪切\tCtrl+X")
        paste_item = edit_menu.Append(wx.ID_ANY, "粘贴\tCtrl+V")

        object_menu = wx.Menu()
        add_object_item = object_menu.Append(
            wx.ID_ANY, "添加对象...\tCtrl+Shift+A"
        )
        edit_object_item = object_menu.Append(wx.ID_ANY, "编辑对象...")
        delete_object_item = object_menu.Append(
            wx.ID_ANY, "删除对象...\tDelete"
        )
        object_menu.AppendSeparator()
        copy_object_item = object_menu.Append(
            wx.ID_ANY, "复制对象\tCtrl+Shift+C"
        )
        cut_object_item = object_menu.Append(
            wx.ID_ANY, "剪切对象\tCtrl+Shift+X"
        )
        paste_object_item = object_menu.Append(
            wx.ID_ANY, "粘贴对象\tCtrl+Shift+V"
        )
        object_menu.AppendSeparator()
        clear_all_objects_item = object_menu.Append(wx.ID_ANY, "清除所有对象")
        object_menu.AppendSeparator()
        object_manager_item = object_menu.Append(
            wx.ID_ANY, "对象管理器...\tCtrl+Shift+M"
        )

        menubar.Append(file_menu, "文件 &F")
        menubar.Append(edit_menu, "编辑 &E")
        menubar.Append(object_menu, "对象 &O")
        self.SetMenuBar(menubar)

        self.Bind(wx.EVT_MENU, self.on_open, open_item)
        self.Bind(wx.EVT_MENU, self.on_save, save_item)
        self.Bind(wx.EVT_MENU, self.on_resize, resize_item)
        self.Bind(wx.EVT_MENU, self.on_custom_tiles, custom_tile_item)
        self.Bind(wx.EVT_MENU, self.on_edit_map_properties, map_prop_item)
        self.Bind(wx.EVT_MENU, self.on_close_file, close_item)
        self.Bind(wx.EVT_MENU, self.on_exit, exit_item)
        self.Bind(wx.EVT_MENU, self.on_undo, undo_item)
        self.Bind(wx.EVT_MENU, self.on_redo, redo_item)
        self.Bind(wx.EVT_MENU, self.clear_selected, clear_item)
        self.Bind(wx.EVT_MENU, self.delete_selection, delete_item)
        self.Bind(wx.EVT_MENU, self.on_set_tile, select_tile_item)
        self.Bind(wx.EVT_MENU, self.on_selection_start, selection_start_item)
        self.Bind(wx.EVT_MENU, self.on_selection_end, selection_end_item)
        self.Bind(wx.EVT_MENU, self.on_fill_selection, fill_item)
        self.Bind(wx.EVT_MENU, self.copy_selection, copy_item)
        self.Bind(wx.EVT_MENU, self.cut_selection, cut_item)
        self.Bind(wx.EVT_MENU, self.paste_clipboard, paste_item)
        self.Bind(wx.EVT_MENU, self.on_goto_cell, goto_item)
        self.Bind(wx.EVT_MENU, self.on_add_object, add_object_item)
        self.Bind(wx.EVT_MENU, self.on_edit_object, edit_object_item)
        self.Bind(wx.EVT_MENU, self.on_delete_object, delete_object_item)
        self.Bind(wx.EVT_MENU, self.copy_object, copy_object_item)
        self.Bind(wx.EVT_MENU, self.cut_object, cut_object_item)
        self.Bind(wx.EVT_MENU, self.paste_object, paste_object_item)
        self.Bind(wx.EVT_MENU, self.on_clear_all_objects, clear_all_objects_item)
        self.Bind(wx.EVT_MENU, self.on_open_object_manager, object_manager_item)
        self.Bind(wx.EVT_CLOSE, self.on_minimize)
        self.Bind(wx.EVT_CHAR_HOOK, self.on_global_key)

    def on_undo(self, event):
        if self.data_manager.undo():
            self.cursor_x = min(self.cursor_x, self.data_manager.width - 1)
            self.cursor_y = min(self.cursor_y, self.data_manager.height - 1)
            self.grid.SetGridCursor(self.cursor_y, self.cursor_x)
            self.grid.MakeCellVisible(self.cursor_y, self.cursor_x)
            TTS.cancel()
            TTS.speak("撤销")
        else:
            TTS.cancel()
            TTS.speak("无法撤销")

    def on_redo(self, event):
        if self.data_manager.redo():
            self.cursor_x = min(self.cursor_x, self.data_manager.width - 1)
            self.cursor_y = min(self.cursor_y, self.data_manager.height - 1)
            self.grid.SetGridCursor(self.cursor_y, self.cursor_x)
            self.grid.MakeCellVisible(self.cursor_y, self.cursor_x)
            TTS.cancel()
            TTS.speak("重做")
        else:
            TTS.cancel()
            TTS.speak("无法重做")

    def on_global_key(self, event):
        focus = wx.Window.FindFocus()
        if focus is None or focus.GetTopLevelParent() != self:
            event.Skip()
            return
        key = event.GetKeyCode()
        if event.ControlDown() and event.ShiftDown():
            if key == ord("A"):
                self.on_add_object(None)
                return
            elif key == ord("C"):
                self.copy_object(None)
                return
            elif key == ord("X"):
                self.cut_object(None)
                return
            elif key == ord("V"):
                self.paste_object(None)
                return
            elif key == ord("M"):
                self.on_open_object_manager(None)
                return
        if event.ControlDown():
            if key == ord("S"):
                self.on_save(None)
                return
            elif key == ord("R"):
                self.on_resize(None)
                return
            elif key == ord("C"):
                self.copy_selection(None)
                return
            elif key == ord("X"):
                self.cut_selection(None)
                return
            elif key == ord("V"):
                self.paste_clipboard(None)
                return
            elif key == ord("F"):
                self.on_fill_selection(None)
                return
            elif key == ord("Z"):
                self.on_undo(None)
                return
            elif key == ord("Y"):
                self.on_redo(None)
                return
        elif key == wx.WXK_DELETE:
            _, obj = self.data_manager.find_object_at(self.cursor_x, self.cursor_y)
            if obj:
                self.on_delete_object(None)
            return
        elif key == wx.WXK_BACK:
            if self.grid.HasFocus():
                self.delete_selection(None)
            return
        elif key == wx.WXK_SPACE:
            if self.grid.HasFocus():
                self.data_manager.toggle_collision(self.cursor_x, self.cursor_y)
                self.update_status()
            return
        event.Skip()

    def is_map_modified(self):
        return self.data_manager.is_modified()

    def on_minimize(self, event):
        self.Iconize()

    def on_close_file(self, event):
        if self.is_map_modified():
            result = wx.MessageBox(
                "地图有未保存的更改，是否关闭？",
                "提示",
                wx.YES_NO | wx.ICON_QUESTION,
            )
            if result == 2:
                self.reset_to_default_map()
            elif result == 8:
                return

    def reset_to_default_map(self):
        self.data_manager.clear()
        self.cursor_x = 0
        self.cursor_y = 0
        self.current_file = None
        TTS.speak("地图已重置")
        self.update_title()

    def on_exit(self, event):
        if self.is_map_modified():
            wx.MessageBox(
                "存在为保存的修改，请先保存再退出！",
                "提示",
                wx.OK | wx.ICON_WARNING,
            )
            return
        self.Destroy()

    def on_save_file(self):
        with wx.FileDialog(
            self,
            "保存地图",
            wildcard="Tiled JSON (*.json)|*.json",
            style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT,
        ) as dlg:
            if dlg.ShowModal() == wx.ID_OK:
                self.save_to_tiled_json(dlg.GetPath())

    def on_resize(self, event):
        dm = self.data_manager
        dlg = ResizeDialog(self, dm.width, dm.height)
        if dlg.ShowModal() == wx.ID_OK:
            new_w, new_h = dlg.get_size()
            if new_w <= 0 or new_h <= 0:
                wx.MessageBox("尺寸必须大于0", "错误", wx.OK | wx.ICON_ERROR)
                return

            dm.resize(new_w, new_h)

            self.cursor_x = min(self.cursor_x, new_w - 1)
            self.cursor_y = min(self.cursor_y, new_h - 1)
            self.grid.SetGridCursor(self.cursor_y, self.cursor_x)
            self.grid.SelectBlock(
                self.cursor_y, self.cursor_x, self.cursor_y, self.cursor_x
            )

            TTS.speak(f"尺寸已调整为{new_w}乘{new_h}")
        dlg.Destroy()

    def on_custom_tiles(self, event):
        self.Enable(False)
        self.Unbind(wx.EVT_CHAR_HOOK)
        self.tile_window = CustomTileDialog(self, self.tile_definitions)
        self.tile_window.Show()

    def on_edit_map_properties(self, event):
        dlg = MapPropertiesDialog(self, self.data_manager.map_properties)
        if dlg.ShowModal() == wx.ID_OK:
            self.data_manager.map_properties = dlg.get_properties()
            TTS.speak("地图属性已更新")
        dlg.Destroy()

    def enable_and_update(self, tile_data):
        global TILE_DEFINITIONS
        TILE_DEFINITIONS = tile_data
        self.tile_definitions = tile_data.copy()
        self.data_manager.tile_definitions = self.tile_definitions
        self.Enable(True)
        self.Bind(wx.EVT_CHAR_HOOK, self.on_global_key)
        self.Raise()

    def update_status(self):
        dm = self.data_manager
        tile_id = str(dm.map_data[self.cursor_y][self.cursor_x])
        tile_data = self.tile_definitions.get(tile_id)
        if tile_data:
            if isinstance(tile_data, dict):
                tile_name = tile_data.get("name", f"未知({tile_id})")
            else:
                tile_name = tile_data
        else:
            tile_name = f"未知({tile_id})"

        _, obj = dm.find_object_at(self.cursor_x, self.cursor_y)
        obj_info = ""
        obj_tts = ""
        if obj:
            obj_name = obj.get("name", "")
            obj_type = obj.get("type", "")
            obj_id = obj.get("id", "")
            props = obj.get("properties", {})
            prop_str = ""
            if props:
                prop_str = " " + " ".join(
                    [f"{k}={v}" for k, v in props.items()]
                )
            obj_info = f"[{obj_id}:{obj_name}:{obj_type}]{prop_str}"
            obj_tts = f"[{obj_id}:{obj_name}:{obj_type}]"

        coord_info = f"({self.cursor_x}； {self.cursor_y})"
        if self.selection_start and self.selection_end:
            x1, y1 = self.selection_start
            x2, y2 = self.selection_end
            coord_info += f" 选区: ({x1},{y1}) 到 ({x2},{y2})"

        if obj_info:
            status_text = f"{coord_info} ； {obj_info} ； {tile_name}"
        else:
            status_text = f"{coord_info} ； {tile_name}"
        self.status_label.SetLabel(status_text)

        if not getattr(self, "_silent_status", False):
            TTS.cancel()
            collision_info = (
                "碰撞" if (self.cursor_x, self.cursor_y) in dm.collision_set else ""
            )
            if obj_tts:
                TTS.speak(f"{obj_tts} {tile_name} {collision_info} {coord_info}")
            else:
                TTS.speak(f"{tile_name} {collision_info} {coord_info}")
        self.status_label.Refresh()
        wx.Yield()

    def on_goto_cell(self, event):
        dlg = wx.TextEntryDialog(
            self, "输入目标坐标（格式：x,y）", "跳转单元格", ""
        )
        if dlg.ShowModal() == wx.ID_OK:
            try:
                text = dlg.GetValue().strip()
                x, y = map(int, text.split(","))
                dm = self.data_manager
                if 0 <= x < dm.width and 0 <= y < dm.height:
                    self.cursor_x = x
                    self.cursor_y = y
                    self.grid.SelectBlock(y, x, y, x)
                    self.grid.MakeCellVisible(y, x)
                    self.grid.SetGridCursor(y, x)
                    self.update_status()
                    TTS.cancel()
                    TTS.speak(f"跳转至 {x} {y}")
                else:
                    TTS.cancel()
                    TTS.speak("坐标超出范围")
            except:
                TTS.cancel()
                TTS.speak("格式错误")
        dlg.Destroy()

    def on_key_down(self, event):
        key = event.GetKeyCode()
        modifiers = event.GetModifiers()
        moved = False

        dm = self.data_manager

        if key in [wx.WXK_LEFT, wx.WXK_RIGHT, wx.WXK_UP, wx.WXK_DOWN]:
            old_x, old_y = self.cursor_x, self.cursor_y
            if key == wx.WXK_LEFT and self.cursor_x > 0:
                self.cursor_x -= 1
                moved = True
            elif key == wx.WXK_RIGHT and self.cursor_x < dm.width - 1:
                self.cursor_x += 1
                moved = True
            elif key == wx.WXK_UP and self.cursor_y > 0:
                self.cursor_y -= 1
                moved = True
            elif key == wx.WXK_DOWN and self.cursor_y < dm.height - 1:
                self.cursor_y += 1
                moved = True
        if key == wx.WXK_ESCAPE:
            self.clear_selected(None)
            return

        elif key == ord("G") and modifiers == wx.MOD_CONTROL:
            dlg = wx.TextEntryDialog(
                self, "输入目标坐标（格式：x,y）", "跳转单元格", ""
            )
            if dlg.ShowModal() == wx.ID_OK:
                try:
                    text = dlg.GetValue().strip()
                    x, y = map(int, text.split(","))
                    if 0 <= x < dm.width and 0 <= y < dm.height:
                        self.cursor_x = x
                        self.cursor_y = y
                        self.grid.SelectBlock(y, x, y, x)
                        self.grid.MakeCellVisible(y, x)
                        self.grid.SetGridCursor(y, x)
                        self.update_status()
                        TTS.cancel()
                        TTS.speak(f"跳转至 {x} {y}")
                    else:
                        TTS.cancel()
                        TTS.speak("坐标超出范围")
                except:
                    TTS.cancel()
                    TTS.speak("格式错误")
            dlg.Destroy()
            return

        elif key == wx.WXK_RETURN:
            if modifiers == wx.MOD_SHIFT:
                self.selection_start = (self.cursor_x, self.cursor_y)
                self.update_status()
                TTS.cancel()
                TTS.speak("选区开始")
                return
            elif modifiers == wx.MOD_CONTROL:
                self.selection_end = (self.cursor_x, self.cursor_y)
                self.update_status()
                TTS.cancel()
                TTS.speak(f"已选: {self.selection_start} 到 {self.selection_end}")
                return

            else:
                _, obj = self.data_manager.find_object_at(
                    self.cursor_x, self.cursor_y
                )
                if obj:
                    self.on_edit_object(None)
                else:
                    self.on_set_tile(None)
                return
        event.Skip()

        if moved:
            self.grid.SetGridCursor(self.cursor_y, self.cursor_x)
            self.grid.SelectBlock(
                self.cursor_y, self.cursor_x, self.cursor_y, self.cursor_x
            )
            self.grid.MakeCellVisible(self.cursor_y, self.cursor_x)
            self.update_status()

    def on_selection_start(self, event):
        self.selection_start = (self.cursor_x, self.cursor_y)
        self.update_status()
        TTS.cancel()
        TTS.speak("选区开始")

    def on_selection_end(self, event):
        self.selection_end = (self.cursor_x, self.cursor_y)
        self.update_status()
        TTS.cancel()
        TTS.speak(f"已选: {self.selection_start} 到 {self.selection_end}")

    def on_grid_select(self, event):
        self.cursor_y = event.GetRow()
        self.cursor_x = event.GetCol()
        self.update_status()
        event.Skip()

    def on_set_tile(self, event):
        dlg = TileSelectionDialog(self, self.tile_definitions)
        if dlg.ShowModal() == wx.ID_OK:
            tile_id = dlg.GetSelectedTileId()
            self.data_manager.set_tile(self.cursor_x, self.cursor_y, tile_id)
        dlg.Destroy()

    def get_selection_bounds(self):
        if not self.selection_start or not self.selection_end:
            return None
        x1, y1 = self.selection_start
        x2, y2 = self.selection_end
        left = min(x1, x2)
        right = max(x1, x2)
        top = min(y1, y2)
        bottom = max(y1, y2)
        return left, top, right, bottom

    def copy_selection(self, event):
        global CLIPBOARD
        dm = self.data_manager
        CLIPBOARD = []
        bounds = self.get_selection_bounds()
        if not bounds:
            CLIPBOARD.append([dm.map_data[self.cursor_y][self.cursor_x]])
            self._clear_selection()
            self.update_status()
            TTS.cancel()
            TTS.speak("复制")
            return
        left, top, right, bottom = bounds

        for y in range(top, bottom + 1):
            row = []
            for x in range(left, right + 1):
                row.append(dm.map_data[y][x])
            CLIPBOARD.append(row)

        self._clear_selection()
        self.update_status()
        TTS.cancel()
        TTS.speak("复制选区")

    def cut_selection(self, event):
        self.copy_selection(event)
        self.delete_selection(event)
        TTS.cancel()
        TTS.speak("剪切选区")

    def delete_selection(self, event):
        dm = self.data_manager
        bounds = self.get_selection_bounds()
        changes = []
        if not bounds:
            changes.append((self.cursor_x, self.cursor_y, 0))
        else:
            left, top, right, bottom = bounds
            for y in range(top, bottom + 1):
                for x in range(left, right + 1):
                    changes.append((x, y, 0))
        if changes:
            dm.set_tiles_bulk(changes)
        self._clear_selection()
        TTS.cancel()
        TTS.speak("清除")

    def on_fill_selection(self, event):
        dlg = TileSelectionDialog(self, self.tile_definitions)
        if dlg.ShowModal() == wx.ID_OK:
            tile_id = dlg.GetSelectedTileId()
            self._fill_selection(tile_id)
            self.Refresh()
        dlg.Destroy()

    def _fill_selection(self, tile_id):
        dm = self.data_manager
        bounds = self.get_selection_bounds()
        changes = []
        if bounds:
            left, top, right, bottom = bounds
            for y in range(top, bottom + 1):
                for x in range(left, right + 1):
                    changes.append((x, y, tile_id))
        else:
            changes.append((self.cursor_x, self.cursor_y, tile_id))
        if changes:
            dm.set_tiles_bulk(changes)
        self._clear_selection()

    def clear_selected(self, event):
        if not self.selection_start and not self.selection_end:
            TTS.cancel()
            TTS.speak("没有选区")
            return

        self._clear_selection()
        self.update_status()
        TTS.cancel()
        TTS.speak("已清除选区")

    def _clear_selection(self):
        self.selection_start = None
        self.selection_end = None

    def paste_clipboard(self, event):
        global CLIPBOARD
        dm = self.data_manager
        if CLIPBOARD is None:
            TTS.cancel()
            TTS.speak("剪贴板为空")
            return
        paste_h = len(CLIPBOARD)
        paste_w = len(CLIPBOARD[0]) if paste_h > 0 else 0

        if self.cursor_y + paste_h > dm.height or self.cursor_x + paste_w > dm.width:
            wx.MessageBox(
                "粘贴区域超出地图边界", "错误", wx.OK | wx.ICON_ERROR
            )
            return

        changes = []
        for dy, row in enumerate(CLIPBOARD):
            for dx, tile_id in enumerate(row):
                y = self.cursor_y + dy
                x = self.cursor_x + dx
                changes.append((x, y, tile_id))
        dm.set_tiles_bulk(changes)
        self._clear_selection()
        TTS.cancel()
        TTS.speak("粘贴")

    def copy_object(self, event):
        layer_idx, obj = self.data_manager.find_object_at(
            self.cursor_x, self.cursor_y
        )
        if not obj:
            wx.MessageBox(
                "当前光标位置没有对象！", "提示", wx.OK | wx.ICON_WARNING
            )
            return

        self.object_clipboard = copy.deepcopy(obj)
        TTS.cancel()
        TTS.speak(f"已复制对象：{obj.get('name', '')}")

    def cut_object(self, event):
        layer_idx, obj = self.data_manager.find_object_at(
            self.cursor_x, self.cursor_y
        )
        if not obj:
            wx.MessageBox(
                "当前光标位置没有对象！", "提示", wx.OK | wx.ICON_WARNING
            )
            return
        self.object_clipboard = copy.deepcopy(obj)
        self.data_manager.remove_object(obj.get("id"), layer_idx)
        TTS.cancel()
        TTS.speak(f"已剪切对象：{obj.get('name', '')}")

    def paste_object(self, event):
        if self.object_clipboard is None:
            wx.MessageBox(
                "对象剪贴板为空！", "提示", wx.OK | wx.ICON_WARNING
            )
            return

        new_obj = copy.deepcopy(self.object_clipboard)
        new_obj["x"] = self.cursor_x * TILE_SIZE
        new_obj["y"] = self.cursor_y * TILE_SIZE
        self.data_manager.add_object(new_obj)
        TTS.cancel()
        TTS.speak(f"已粘贴对象：{new_obj.get('name', '')}")

    def on_add_object(self, event):
        dlg = ObjectDialog(
            self,
            is_edit=False,
            next_id=self.data_manager.next_object_id,
            default_tile_x=self.cursor_x,
            default_tile_y=self.cursor_y,
        )
        if dlg.ShowModal() == wx.ID_OK:
            obj_data = dlg.get_object_data()
            self.data_manager.add_object(obj_data)
            TTS.cancel()
            TTS.speak(f"已添加对象：{obj_data.get('name', '')}")
        dlg.Destroy()

    def on_edit_object(self, event):
        layer_idx, obj = self.data_manager.find_object_at(
            self.cursor_x, self.cursor_y
        )
        if not obj:
            wx.MessageBox(
                "当前光标位置没有对象！", "提示", wx.OK | wx.ICON_WARNING
            )
            return

        self._silent_status = True
        dlg = ObjectDialog(
            self, obj_data=obj, is_edit=True, next_id=self.data_manager.next_object_id
        )
        if dlg.ShowModal() == wx.ID_OK:
            new_obj_data = dlg.get_object_data()
            self.data_manager.modify_object(
                obj.get("id"), new_obj_data, layer_idx
            )
            del self._silent_status
            TTS.speak(f"已编辑对象：{new_obj_data.get('name', '')}")
        else:
            del self._silent_status
        dlg.Destroy()

    def on_delete_object(self, event):
        layer_idx, obj = self.data_manager.find_object_at(
            self.cursor_x, self.cursor_y
        )
        if not obj:
            wx.MessageBox(
                "当前光标位置没有对象！", "提示", wx.OK | wx.ICON_WARNING
            )
            return

        result = wx.MessageBox(
            f'确定要删除对象 "{obj.get("name", "")}" 吗？',
            "确认",
            wx.YES_NO | wx.ICON_QUESTION,
        )
        if result == 2:
            self.data_manager.remove_object(obj.get("id"), layer_idx)
            TTS.speak("已删除对象")

    def on_clear_all_objects(self, event):
        result = wx.MessageBox(
            "确定要清除所有对象吗？", "确认", wx.YES_NO | wx.ICON_QUESTION
        )
        if result == 2:
            self.data_manager.clear_objects()
            TTS.speak("已清除所有对象")

    def on_open_object_manager(self, event):
        if self.object_manager_dlg:
            self.object_manager_dlg.Raise()
            return
        self.object_manager_dlg = ObjectManagerDialog(self, self.data_manager)

    def on_open(self, event):
        with wx.FileDialog(
            self,
            "打开地图",
            wildcard="Tiled JSON (*.json)|*.json",
            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST,
        ) as dlg:
            if dlg.ShowModal() == wx.ID_OK:
                filepath = dlg.GetPath()
                self.current_file = filepath
                self.load_from_tiled_json(filepath)
                self.update_title()

    def update_title(self):
        if self.current_file:
            filename = os.path.basename(self.current_file)
            self.SetTitle(f"{filename} - 地图编辑器 V1.0")
        else:
            self.SetTitle("地图编辑器 V1.0")

    def load_from_tiled_json(self, filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)

            if not self.data_manager.load_from_dict(data):
                wx.MessageBox("地图数据无效！", "错误", wx.OK | wx.ICON_ERROR)
                return

            self.cursor_x = 0
            self.cursor_y = 0
            self.update_status()

            dm = self.data_manager
            wx.MessageBox(
                f"成功加载地图：{dm.width}x{dm.height}", "提示", wx.OK
            )
            TTS.speak(f"已加载地图，宽度{dm.width}，高度{dm.height}")

        except Exception as e:
            wx.MessageBox(f"加载失败：{str(e)}", "错误", wx.OK | wx.ICON_ERROR)

    def rebuild_grid(self):
        dm = self.data_manager
        self.grid.ClearGrid()
        self.grid.DeleteRows(0, self.grid.GetNumberRows())
        self.grid.DeleteCols(0, self.grid.GetNumberCols())
        self.grid.AppendRows(dm.height)
        self.grid.AppendCols(dm.width)

        for y in range(dm.height):
            for x in range(dm.width):
                self.grid.SetCellValue(y, x, dm.get_cell_display(x, y))

        self._clear_selection()
        self.cursor_x = min(self.cursor_x, dm.width - 1)
        self.cursor_y = min(self.cursor_y, dm.height - 1)
        self.grid.SetGridCursor(self.cursor_y, self.cursor_x)
        self.grid.MakeCellVisible(self.cursor_y, self.cursor_x)

    def on_save(self, event):
        self.on_save_file()

    def save_to_tiled_json(self, filepath):
        tiled_json = self.data_manager.to_dict(self.tile_definitions)

        json_str = json.dumps(tiled_json, indent=2, ensure_ascii=False)

        def format_data(match):
            content = match.group(1)
            arr = json.loads("[" + content + "]")
            lines = [
                ", ".join(str(v) for v in arr[i : i + 50])
                for i in range(0, len(arr), 50)
            ]
            return '"data": [\n    ' + ",\n    ".join(lines) + "\n  ]"

        json_str = re.sub(
            r'"data":\s*\[(.*?)\]', format_data, json_str, flags=re.DOTALL
        )

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(json_str)
        wx.MessageBox(f"地图已保存至:\n{filepath}", "成功", wx.OK)


class MapEditorApp(wx.App):
    def OnInit(self):
        self.instance = wx.SingleInstanceChecker("MapEditor")
        if self.instance.IsAnotherRunning():
            wx.MessageBox("编辑器已在运行！", "提示", wx.OK)
            return False

        frame = MapEditorFrame()
        frame.Show()
        return True


if __name__ == "__main__":
    app = MapEditorApp()
    app.MainLoop()
