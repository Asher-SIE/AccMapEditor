import copy
import ctypes
import json
import locale
import os
import sys

if sys.platform == "darwin":
    os.environ.setdefault("LANG", "zh_CN.UTF-8")
    os.environ.setdefault("LC_ALL", "zh_CN.UTF-8")

import TTS
import wx
import wx.adv
import wx.grid as gridlib

import expiry_guard
from platform_utils import IS_WINDOWS, IS_MACOS

from map_data import MapDataManager, EVT_MAP_DATA, MapDataEvent, TILE_SIZE
from map_data.commands import TILE_SIZE as CMD_TILE_SIZE
from dialogs.object_dialog import ObjectDialog, PropertyListPanel, format_property_value
from dialogs.object_manager import ObjectManagerDialog
from data_editor.tree_panel import TreePanel
from data_editor.data_editor_panel import DataEditorPanel


TILE_DEFINITIONS = {}

CLIPBOARD = None

WX_YES = 2
WX_NO = 8
WX_CANCEL = 16


def tile_sort_key(tile_id):
    try:
        return (0, int(tile_id))
    except (TypeError, ValueError):
        return (1, str(tile_id))


class TileSelectionDialog(wx.Dialog):
    def __init__(self, parent, tile_defs, tile_sources=None):
        super().__init__(parent, title="选择瓦片")
        sizer = wx.BoxSizer(wx.VERTICAL)
        choices = []
        tile_sources = tile_sources or {}
        source_priority = {"map": 0, "root": 1, "root_conflict": 2}

        def entry_sort_key(item):
            source = tile_sources.get(item[0], {}).get("source", "root")
            return (source_priority.get(source, 9),) + tile_sort_key(item[0])

        self.tile_keys = []
        for k, v in sorted(tile_defs.items(), key=entry_sort_key):
            if isinstance(v, dict):
                name = v.get("name", "")
                props = v.get("properties", {})
            else:
                name = v
                props = {}

            if props:
                prop_str = ", ".join(
                    [f"{p_k}={format_property_value(p_v)}" for p_k, p_v in props.items()]
                )
                choices.append(f"{k}: {name} ({prop_str})")
            else:
                choices.append(f"{k}: {name}")
            self.tile_keys.append(k)
        self.original_choices = choices[:]
        self.original_tile_keys = self.tile_keys[:]

        filter_sizer = wx.BoxSizer(wx.HORIZONTAL)
        filter_sizer.Add(wx.StaticText(self, label="筛选:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 5)
        self.filter_input = wx.TextCtrl(self, style=wx.TE_PROCESS_ENTER)
        filter_sizer.Add(self.filter_input, 1, wx.EXPAND | wx.ALL, 5)
        sizer.Add(filter_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)

        self.listbox = wx.ListBox(self, choices=choices)
        if choices:
            self.listbox.SetSelection(0)
        sizer.Add(self.listbox, 1, wx.ALL | wx.EXPAND, 10)

        btn_sizer = self.CreateButtonSizer(wx.OK | wx.CANCEL)
        sizer.Add(btn_sizer, 0, wx.ALL | wx.EXPAND, 10)
        self.SetSizer(sizer)

        self.filter_input.Bind(wx.EVT_TEXT, self.on_filter_changed)
        self.listbox.Bind(wx.EVT_KEY_DOWN, self.on_listbox_keydown)
        self.filter_input.Bind(wx.EVT_KEY_DOWN, self.on_filter_keydown)

        self.listbox.SetFocus()

    def GetSelectedTileId(self):
        sel = self.listbox.GetSelection()
        if sel != wx.NOT_FOUND:
            return self.tile_keys[sel]
        return 0

    def on_filter_changed(self, event):
        filter_text = self.filter_input.GetValue().strip()
        if not filter_text:
            self.listbox.Set(self.original_choices)
            self.tile_keys = self.original_tile_keys[:]
            if self.original_choices:
                self.listbox.SetSelection(0)
            return

        is_numeric = filter_text.isdigit()
        filtered_choices = []
        filtered_keys = []

        for choice, key in zip(self.original_choices, self.original_tile_keys):
            if is_numeric:
                if filter_text in str(key):
                    filtered_choices.append(choice)
                    filtered_keys.append(key)
            else:
                choice_lower = choice.lower()
                if filter_text.lower() in choice_lower:
                    filtered_choices.append(choice)
                    filtered_keys.append(key)

        self.listbox.Set(filtered_choices)
        self.tile_keys = filtered_keys
        if filtered_choices:
            self.listbox.SetSelection(0)

        event.Skip()

    def on_listbox_keydown(self, event):
        if event.GetKeyCode() == wx.WXK_TAB:
            self.filter_input.SetFocus()
            return
        event.Skip()

    def on_filter_keydown(self, event):
        if event.GetKeyCode() == wx.WXK_TAB and event.ShiftDown():
            self.listbox.SetFocus()
            return
        event.Skip()


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

        self.prop_panel = PropertyListPanel(
            self, properties=self.properties, label="属性列表："
        )
        sizer.Add(self.prop_panel, 1, wx.EXPAND | wx.ALL, 10)

        btn_sizer = self.CreateButtonSizer(wx.OK | wx.CANCEL)
        sizer.Add(btn_sizer, 0, wx.EXPAND | wx.ALL, 10)

        self.SetSizer(sizer)
        self.SetSize((400, 320))

    def get_properties(self):
        return self.prop_panel.get_properties()


class MapPropertiesDialog(wx.Dialog):
    def __init__(self, parent, map_properties):
        super().__init__(parent, title="编辑地图属性")

        self.map_properties = map_properties.copy()

        sizer = wx.BoxSizer(wx.VERTICAL)

        self.prop_panel = PropertyListPanel(
            self, properties=self.map_properties, label="属性列表："
        )
        sizer.Add(self.prop_panel, 1, wx.EXPAND | wx.ALL, 10)

        btn_sizer = self.CreateButtonSizer(wx.OK | wx.CANCEL)
        sizer.Add(btn_sizer, 0, wx.EXPAND | wx.ALL, 10)

        self.SetSizer(sizer)
        self.SetSize((400, 350))

    def get_properties(self):
        return self.prop_panel.get_properties()


class ShapeGenerationDialog(wx.Dialog):
    def __init__(self, parent, current_x, current_y):
        super().__init__(parent, title="生成图形")

        sizer = wx.BoxSizer(wx.VERTICAL)

        coord_sizer = wx.BoxSizer(wx.HORIZONTAL)
        coord_sizer.Add(wx.StaticText(self, label="X坐标:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
        self.x_ctrl = wx.SpinCtrl(self, value=str(current_x), min=-1000, max=1000)
        coord_sizer.Add(self.x_ctrl, 0, wx.RIGHT, 10)
        coord_sizer.Add(wx.StaticText(self, label="Y坐标:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
        self.y_ctrl = wx.SpinCtrl(self, value=str(current_y), min=-1000, max=1000)
        coord_sizer.Add(self.y_ctrl, 0)
        sizer.Add(coord_sizer, 0, wx.ALL, 5)

        anchor_sizer = wx.BoxSizer(wx.HORIZONTAL)
        anchor_sizer.Add(wx.StaticText(self, label="坐标基准:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
        self.anchor_choice = wx.Choice(self, choices=["中心点", "左上角"])
        self.anchor_choice.SetSelection(0)
        anchor_sizer.Add(self.anchor_choice, 1)
        sizer.Add(anchor_sizer, 0, wx.EXPAND | wx.ALL, 5)

        shape_sizer = wx.BoxSizer(wx.HORIZONTAL)
        shape_sizer.Add(wx.StaticText(self, label="图形:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
        self.shape_choice = wx.Choice(self, choices=["矩形", "椭圆", "菱形", "三角形", "路标多边形"])
        self.shape_choice.SetSelection(0)
        shape_sizer.Add(self.shape_choice, 1)
        sizer.Add(shape_sizer, 0, wx.EXPAND | wx.ALL, 5)

        size_sizer = wx.BoxSizer(wx.HORIZONTAL)
        size_sizer.Add(wx.StaticText(self, label="长:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
        self.width_ctrl = wx.SpinCtrl(self, value="5", min=1, max=1000)
        size_sizer.Add(self.width_ctrl, 0, wx.RIGHT, 10)
        size_sizer.Add(wx.StaticText(self, label="宽:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
        self.height_ctrl = wx.SpinCtrl(self, value="5", min=1, max=1000)
        size_sizer.Add(self.height_ctrl, 0)
        sizer.Add(size_sizer, 0, wx.ALL, 5)

        mode_sizer = wx.BoxSizer(wx.HORIZONTAL)
        mode_sizer.Add(wx.StaticText(self, label="模式:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
        self.mode_choice = wx.Choice(self, choices=["实心", "边框"])
        self.mode_choice.SetSelection(0)
        mode_sizer.Add(self.mode_choice, 1)
        sizer.Add(mode_sizer, 0, wx.EXPAND | wx.ALL, 5)

        border_sizer = wx.BoxSizer(wx.HORIZONTAL)
        border_sizer.Add(wx.StaticText(self, label="边框粗细:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
        self.thickness_ctrl = wx.SpinCtrl(self, value="1", min=1, max=1000)
        border_sizer.Add(self.thickness_ctrl, 0, wx.RIGHT, 10)
        border_sizer.Add(wx.StaticText(self, label="方向:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
        self.border_direction_choice = wx.Choice(self, choices=["向内", "向外"])
        self.border_direction_choice.SetSelection(0)
        border_sizer.Add(self.border_direction_choice, 1)
        sizer.Add(border_sizer, 0, wx.EXPAND | wx.ALL, 5)

        btn_sizer = self.CreateButtonSizer(wx.OK | wx.CANCEL)
        sizer.Add(btn_sizer, 0, wx.EXPAND | wx.ALL, 10)

        self.SetSizer(sizer)
        self.Fit()
        self.mode_choice.Bind(wx.EVT_CHOICE, self.on_mode_changed)
        self.on_mode_changed(None)

    def on_mode_changed(self, event):
        is_border = self.mode_choice.GetStringSelection() == "边框"
        self.thickness_ctrl.Enable(is_border)
        self.border_direction_choice.Enable(is_border)

    def get_config(self):
        return {
            "x": self.x_ctrl.GetValue(),
            "y": self.y_ctrl.GetValue(),
            "anchor": self.anchor_choice.GetStringSelection(),
            "shape": self.shape_choice.GetStringSelection(),
            "width": self.width_ctrl.GetValue(),
            "height": self.height_ctrl.GetValue(),
            "mode": self.mode_choice.GetStringSelection(),
            "thickness": self.thickness_ctrl.GetValue(),
            "border_direction": self.border_direction_choice.GetStringSelection(),
        }


class CustomTileDialog(wx.Frame):
    def __init__(self, parent, tile_defs, tile_sources=None):
        super().__init__(parent, title="编辑瓦片", size=(800, 600))
        self.tile_data = copy.deepcopy(tile_defs)
        self.tile_sources = copy.deepcopy(tile_sources or {})
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
        source_priority = {"map": 0, "root": 1, "root_conflict": 2}

        def entry_sort_key(item):
            source = self.tile_sources.get(item[0], {}).get("source", "root")
            return (source_priority.get(source, 9),) + tile_sort_key(item[0])

        sorted_items = sorted(self.tile_data.items(), key=entry_sort_key)
        for tid, data in sorted_items:
            if isinstance(data, dict):
                name = data.get("name", "")
                props = data.get("properties", {})
            else:
                name = data
                props = {}

            if props:
                prop_str = ", ".join(
                    [f"{k}={format_property_value(v)}" for k, v in props.items()]
                )
                display = f"{tid}: {name} ({prop_str})"
            else:
                display = f"{tid}: {name}"

            self.tile_list.Append(display)

    def on_list_select(self, event):
        sel = self.tile_list.GetSelection()
        if sel != wx.NOT_FOUND:
            text = self.tile_list.GetString(sel)
            before_colon = text.split(":")[0].strip()
            self.selected_tile_id = before_colon.split()[-1]
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
                self.tile_sources.pop(self.selected_tile_id, None)
                self.tile_sources[new_id] = {"source": "map"}
                self.selected_tile_id = new_id
                self.refresh_list()
        dlg.Destroy()

    def on_add(self, event):
        numeric_ids = []
        for key in self.tile_data.keys():
            try:
                numeric_ids.append(int(key))
            except (TypeError, ValueError):
                pass
        max_id = max(numeric_ids, default=-1)
        next_id = str(max_id + 1)

        dlg = TileInputDialog(self, next_id, "", is_edit=False)
        if dlg.ShowModal() == wx.ID_OK:
            new_id = dlg.id_input.GetValue().strip()
            new_name = dlg.name_input.GetValue().strip()
            if new_id and new_name:
                self.tile_data[new_id] = {"name": new_name, "properties": {}}
                self.tile_sources[new_id] = {"source": "map"}
                self.refresh_list()
        dlg.Destroy()

    def on_delete(self, event):
        if not self.selected_tile_id:
            wx.MessageBox("请先选择要删除的瓦片！", "提示", wx.OK | wx.ICON_WARNING)
            return

        del self.tile_data[self.selected_tile_id]
        self.tile_sources.pop(self.selected_tile_id, None)
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
        if int(result) == WX_NO:
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

        if IS_WINDOWS:
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
        self.landmarks = {}
        self.current_file = None
        self._clean_map_state = None

        global TILE_DEFINITIONS
        self.root_tile_definitions = self.load_tiled_data()
        self.map_tile_definitions = {}
        self.tile_definitions = {}
        self.tile_definition_sources = {}
        self._sync_tile_definitions()
        TILE_DEFINITIONS = self.tile_definitions.copy()
        self.data_manager.tile_definitions = self.tile_definitions

        self.object_definitions = self.load_object_definitions()

        self.selection_start = None
        self.selection_end = None
        self._shift_selecting = False

        self.object_manager_dlg = None
        self.object_clipboard = None

        self.init_ui()
        self.create_menu()
        self._set_map_mode(True)
        self._subscribe_events()
        self._mark_map_clean()
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
        elif kind in ("objects_cleared", "map_loaded", "map_cleared", "map_resized"):
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

    def _get_map_state(self):
        data = self.data_manager.to_dict(self._get_used_tile_definitions())
        return json.dumps(data, ensure_ascii=False, sort_keys=True)

    def _mark_map_clean(self):
        self._clean_map_state = self._get_map_state()

    def _is_anything_modified(self):
        if self.is_map_modified():
            return True
        if hasattr(self, "data_panel") and self.data_panel.is_file_modified():
            return True
        return False

    def _confirm_save_if_modified(self):
        if not self._is_anything_modified():
            return True

        parts = []
        if self.is_map_modified():
            parts.append("地图")
        if hasattr(self, "data_panel") and self.data_panel.is_file_modified():
            parts.append("数据文件")
        subject = "、".join(parts) if parts else "当前"

        result = wx.MessageBox(
            f"{subject}有未保存的修改，是否保存？\n\n"
            "选择“是”保存后继续，选择“否”不保存继续，选择“取消”停止操作。",
            "未保存的修改",
            wx.YES_NO | wx.CANCEL | wx.ICON_QUESTION,
        )
        result = int(result)
        if result == WX_YES:
            return self._save_all()
        if result == WX_NO:
            return True
        return False

    def _confirm_data_save(self):
        if not self.data_panel.is_file_modified():
            return True
        result = wx.MessageBox(
            "当前数据文件有未保存的修改，是否保存？\n\n"
            "选择“是”保存后继续，选择“否”不保存继续，选择“取消”停止操作。",
            "未保存的数据修改",
            wx.YES_NO | wx.CANCEL | wx.ICON_QUESTION,
        )
        result = int(result)
        if result == WX_YES:
            return self.data_panel.save()
        if result == WX_NO:
            return True
        return False

    def _save_all(self):
        ok = True
        if self.is_map_modified():
            ok = self.save_current_file() and ok
        if hasattr(self, "data_panel") and self.data_panel.is_file_modified():
            ok = self.data_panel.save() and ok
        self.update_title()
        return ok

    def on_import_data_source(self, event):
        if not self._confirm_save_if_modified():
            return
        current = self.editor_config.get("data_dir", "")
        with wx.DirDialog(
            self,
            "选择数据源目录（assets/data）",
            defaultPath=current if current and os.path.isdir(current) else "",
        ) as dlg:
            if dlg.ShowModal() != wx.ID_OK:
                return
            new_dir = dlg.GetPath().replace("\\", "/")
        self.editor_config["data_dir"] = new_dir
        self._save_editor_config()
        self.data_panel.reset()
        self.tree_panel.populate(self.editor_config)
        wx.MessageBox(f"数据源已切换为：\n{new_dir}", "导入数据源", wx.OK)
        self.update_title()

    def _save_editor_config(self):
        try:
            with open("./editor_config.json", "w", encoding="utf-8") as f:
                json.dump(self.editor_config, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def save_current_file(self):
        if self.current_file:
            return self._save_map_to_path(self.current_file)
        return self.on_save_file()

    def _save_map_to_path(self, filepath):
        if not self.save_to_tiled_json(filepath):
            return False
        self.current_file = filepath
        self._mark_map_clean()
        self.update_title()
        wx.MessageBox(f"地图已保存至:\n{filepath}", "成功", wx.OK)
        return True

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

                return self._normalize_tile_definitions(data)

        except json.JSONDecodeError as e:
            print(f"JSON解析错误: {e}")
            return default_config
        except Exception as e:
            print(f"加载配置文件时发生错误: {e}")
            return default_config

    def _normalize_tile_definitions(self, data):
        if not isinstance(data, dict):
            return {}

        result = {}
        for k, v in data.items():
            key = str(k)
            if isinstance(v, str):
                result[key] = {"name": v, "properties": {}}
            elif isinstance(v, dict):
                item = copy.deepcopy(v)
                item["name"] = str(item.get("name", ""))
                props = item.get("properties", {})
                item["properties"] = props if isinstance(props, dict) else {}
                result[key] = item
        return result

    def _tile_definition_equal(self, left, right):
        return json.dumps(left, ensure_ascii=False, sort_keys=True) == json.dumps(
            right, ensure_ascii=False, sort_keys=True
        )

    def _tile_definition_signature(self, tile_info):
        return json.dumps(tile_info, ensure_ascii=False, sort_keys=True)

    def _contains_tile_definition(self, definitions, tile_info):
        signature = self._tile_definition_signature(tile_info)
        return any(
            self._tile_definition_signature(existing) == signature
            for existing in definitions.values()
        )

    def _next_available_tile_id(self, definitions):
        numeric_ids = []
        for key in definitions.keys():
            try:
                numeric_ids.append(int(key))
            except (TypeError, ValueError):
                pass
        next_id = max(numeric_ids, default=-1) + 1
        while str(next_id) in definitions:
            next_id += 1
        return str(next_id)

    def _sync_tile_definitions(self):
        effective = copy.deepcopy(self.map_tile_definitions)
        sources = {k: {"source": "map"} for k in effective}

        for tile_id, tile_info in self.root_tile_definitions.items():
            if self._contains_tile_definition(effective, tile_info):
                continue

            if tile_id not in effective:
                effective[tile_id] = copy.deepcopy(tile_info)
                sources[tile_id] = {"source": "root"}
                continue

            if self._tile_definition_equal(effective[tile_id], tile_info):
                continue

            new_id = self._next_available_tile_id(effective)
            effective[new_id] = copy.deepcopy(tile_info)
            sources[new_id] = {"source": "root_conflict", "original_id": tile_id}

        self.tile_definitions = effective
        self.tile_definition_sources = sources
        self.data_manager.tile_definitions = self.tile_definitions

    def _add_deduped_tile_definition(self, result, seen, tile_id, tile_info):
        signature = self._tile_definition_signature(tile_info)
        if signature in seen:
            return

        target_id = tile_id
        if target_id in result and not self._tile_definition_equal(
            result[target_id], tile_info
        ):
            target_id = self._next_available_tile_id(result)

        result[target_id] = copy.deepcopy(tile_info)
        seen.add(signature)

    def _dedupe_tile_definitions(self, definitions):
        result = {}
        seen = set()

        for tile_id, tile_info in sorted(
            definitions.items(), key=lambda x: tile_sort_key(x[0])
        ):
            self._add_deduped_tile_definition(result, seen, tile_id, tile_info)

        return result

    def _get_root_tile_definitions_for_save(self):
        result = {}
        seen = set()

        groups = (
            self.map_tile_definitions,
            self.root_tile_definitions,
            self.tile_definitions,
        )
        for definitions in groups:
            normalized = self._normalize_tile_definitions(definitions)
            for tile_id, tile_info in sorted(
                normalized.items(), key=lambda x: tile_sort_key(x[0])
            ):
                self._add_deduped_tile_definition(result, seen, tile_id, tile_info)

        return result

    def _get_used_tile_ids(self):
        used = set()
        for row in self.data_manager.map_data:
            for tile_id in row:
                used.add(str(tile_id))
        return used

    def _get_used_tile_definitions(self):
        used = self._get_used_tile_ids()
        return {
            tile_id: copy.deepcopy(tile_info)
            for tile_id, tile_info in self.tile_definitions.items()
            if tile_id in used
        }

    def _save_root_tile_definitions(self):
        root_defs = self._get_root_tile_definitions_for_save()
        with open("./tile_definitions.json", "w", encoding="utf-8") as f:
            json.dump(root_defs, f, ensure_ascii=False, indent=4)
        self.root_tile_definitions = root_defs
        self._sync_tile_definitions()

    def _promote_tile_definition_to_map(self, tile_id):
        tile_id = str(tile_id)
        tile_info = self.tile_definitions.get(tile_id)
        if tile_info is None:
            return
        self.map_tile_definitions[tile_id] = copy.deepcopy(tile_info)
        self._sync_tile_definitions()

    def load_object_definitions(self):
        config_file = "./object_definitions.json"
        try:
            if not os.path.exists(config_file):
                return {}
            with open(config_file, "r", encoding="utf-8") as f:
                content = f.read()
            if not content.strip():
                return {}
            data = json.loads(content)
            if not isinstance(data, dict):
                return {}
            return self._normalize_object_definitions(data)
        except Exception as e:
            print(f"加载对象模板库时发生错误: {e}")
            return {}

    def _normalize_object_definitions(self, data):
        if not isinstance(data, dict):
            return {}
        result = {}
        for key, tmpl in data.items():
            if not isinstance(tmpl, dict):
                continue
            props = tmpl.get("properties", {})
            try:
                width = int(tmpl.get("width", TILE_SIZE))
            except (TypeError, ValueError):
                width = TILE_SIZE
            try:
                height = int(tmpl.get("height", TILE_SIZE))
            except (TypeError, ValueError):
                height = TILE_SIZE
            result[str(key)] = {
                "name": str(tmpl.get("name", key)),
                "type": str(tmpl.get("type", "")),
                "width": width,
                "height": height,
                "properties": copy.deepcopy(props) if isinstance(props, dict) else {},
            }
        return result

    def _object_to_template(self, obj):
        try:
            width = int(obj.get("width", TILE_SIZE))
        except (TypeError, ValueError):
            width = TILE_SIZE
        try:
            height = int(obj.get("height", TILE_SIZE))
        except (TypeError, ValueError):
            height = TILE_SIZE
        props = obj.get("properties", {})
        return {
            "name": str(obj.get("name", "")),
            "type": str(obj.get("type", "")),
            "width": width,
            "height": height,
            "properties": copy.deepcopy(props) if isinstance(props, dict) else {},
        }

    def _upsert_object_template(self, obj):
        name = str(obj.get("name", "")).strip()
        if not name:
            return None
        self.object_definitions[name] = self._object_to_template(obj)
        return name

    def _save_root_object_definitions(self):
        with open("./object_definitions.json", "w", encoding="utf-8") as f:
            json.dump(self.object_definitions, f, ensure_ascii=False, indent=4)

    def init_ui(self):
        splitter = wx.SplitterWindow(self, style=wx.SP_LIVE_UPDATE | wx.SP_BORDER)
        splitter.SetMinimumPaneSize(220)

        self.editor_config = self._load_editor_config()

        self.tree_panel = TreePanel(splitter, on_select=self._on_tree_select)

        self.main_book = wx.Simplebook(splitter)

        map_panel = wx.Panel(self.main_book)
        map_sizer = wx.BoxSizer(wx.VERTICAL)
        self.status_label = wx.StaticText(map_panel, label="")
        map_sizer.Add(self.status_label, 0, wx.ALL, 5)
        self.grid = gridlib.Grid(map_panel)
        self.grid.CreateGrid(self.data_manager.height, self.data_manager.width)

        self.grid.EnableEditing(False)
        self.grid.SetDefaultCellAlignment(wx.ALIGN_CENTER, wx.ALIGN_CENTER)
        self.grid.SetRowLabelSize(40)
        self.grid.SetColLabelSize(30)

        self.grid.Bind(wx.EVT_KEY_DOWN, self.on_key_down)
        self.grid.Bind(wx.EVT_KEY_UP, self.on_key_up)
        self.grid.Bind(gridlib.EVT_GRID_SELECT_CELL, self.on_grid_select)

        map_sizer.Add(self.grid, 1, wx.EXPAND | wx.ALL, 5)
        map_panel.SetSizer(map_sizer)
        self.main_book.AddPage(map_panel, "")

        self.data_panel = DataEditorPanel(
            self.main_book,
            self.editor_config.get("backup_dir", "data_backup"),
            on_dirty_change=self.update_title,
        )
        self.main_book.AddPage(self.data_panel, "")

        splitter.SplitVertically(self.tree_panel, self.main_book, 380)
        self.splitter = splitter

        self.main_book.SetSelection(0)

        self.tree_panel.populate(self.editor_config)

        self.grid.SetFocus()

    def _load_editor_config(self):
        config_path = "./editor_config.json"
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {
                "data_dir": "",
                "map_dir": "",
                "backup_dir": "data_backup",
                "entity_files": [],
                "config_files": [],
            }

    def _load_data_file(self, path):
        if not path:
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None

    def _on_tree_select(self, info):
        if not hasattr(self, "main_book"):
            return
        kind = info.get("kind")
        if kind == "map_file":
            if not self._confirm_save_if_modified():
                self.tree_panel.select_first_map()
                return
            if self.load_from_tiled_json(info["path"]):
                self.current_file = info["path"]
                self._mark_map_clean()
                self.update_title()
                self.main_book.SetSelection(0)
                self._set_map_mode(True)
                self.grid.SetFocus()
            return
        if kind == "map_root":
            self.main_book.SetSelection(0)
            self._set_map_mode(True)
            self.grid.SetFocus()
            return
        if kind == "data_file":
            new_path = info.get("path", "")
            if new_path and new_path != self.data_panel.active_path():
                if self.data_panel.is_file_modified() and not self._confirm_data_save():
                    return
            self.main_book.SetSelection(1)
            self._set_map_mode(False)
            self.data_panel.select(info)
            self.data_panel.browser.list.SetFocus()
            self.update_title()
            return
        if kind in ("data_root", "other_root"):
            self.main_book.SetSelection(1)
            self._set_map_mode(False)
            return

    def create_menu(self):
        menubar = wx.MenuBar()
        self._map_menu_items = []

        def map_item(menu, id_, text):
            item = menu.Append(id_, text)
            self._map_menu_items.append(item)
            return item

        mod = "Cmd" if IS_MACOS else "Ctrl"

        file_menu = wx.Menu()
        open_item = file_menu.Append(wx.ID_OPEN, f"打开...\t{mod}+O")
        import_data_item = file_menu.Append(
            wx.ID_ANY,
            "导入数据源...\t&I" if IS_WINDOWS else "导入数据源...",
        )
        close_item = map_item(
            file_menu,
            wx.ID_ANY,
            "关闭当前文件\t&L" if IS_WINDOWS else "关闭当前文件",
        )
        save_item = file_menu.Append(wx.ID_SAVE, f"保存...\t{mod}+S")
        save_as_item = file_menu.Append(wx.ID_SAVEAS, f"另存为...\t{mod}+Shift+S")
        resize_item = map_item(
            file_menu,
            wx.ID_ANY,
            "调整地图尺寸...\t&R" if IS_WINDOWS else "调整地图尺寸...",
        )
        custom_tile_item = map_item(
            file_menu,
            wx.ID_ANY,
            "编辑瓦片...\t&C" if IS_WINDOWS else "编辑瓦片...",
        )
        map_prop_item = map_item(
            file_menu,
            wx.ID_ANY,
            "编辑地图属性...\t&M" if IS_WINDOWS else "编辑地图属性...",
        )
        if IS_WINDOWS:
            file_menu.AppendSeparator()
        about_item = file_menu.Append(wx.ID_ABOUT, "关于地图编辑器")
        exit_item = file_menu.Append(
            wx.ID_EXIT,
            "退出\t&X" if IS_WINDOWS else "退出",
        )

        edit_menu = wx.Menu()
        undo_item = edit_menu.Append(wx.ID_UNDO, f"撤销\t{mod}+Z")
        redo_item = edit_menu.Append(wx.ID_REDO, f"重做\t{mod}+Y")
        edit_menu.AppendSeparator()
        goto_item = map_item(edit_menu, wx.ID_ANY, f"跳转单元格...\t{mod}+G")
        landmark_menu = wx.Menu()
        for i in range(1, 11):
            label = "0" if i == 10 else str(i)
            mark_item = landmark_menu.Append(wx.ID_ANY, f"标记{label}")
            jump_item = landmark_menu.Append(wx.ID_ANY, f"跳转到{label}")
            self._map_menu_items.append(mark_item)
            self._map_menu_items.append(jump_item)
            self.Bind(
                wx.EVT_MENU,
                lambda event, index=i: self._add_landmark(index),
                mark_item,
            )
            self.Bind(
                wx.EVT_MENU,
                lambda event, index=i: self._jump_to_landmark(index),
                jump_item,
            )
        clear_landmarks_item = landmark_menu.Append(wx.ID_ANY, "清理")
        self._map_menu_items.append(clear_landmarks_item)
        landmark_submenu = edit_menu.AppendSubMenu(landmark_menu, "路标")
        self._map_menu_items.append(landmark_submenu)
        edit_menu.AppendSeparator()
        clear_item = map_item(edit_menu, wx.ID_ANY, "清除选区")
        delete_item = map_item(edit_menu, wx.ID_ANY, "清除单元格\tBackspace")
        select_tile_item = map_item(edit_menu, wx.ID_ANY, "选择瓦片\tEnter")
        selection_start_item = map_item(
            edit_menu, wx.ID_ANY, "选区开始点\tShift+Enter"
        )
        selection_end_item = map_item(
            edit_menu, wx.ID_ANY, f"选区结束点\t{mod}+Enter"
        )
        fill_item = map_item(edit_menu, wx.ID_ANY, f"填充选区\t{mod}+F")
        generate_shape_item = map_item(edit_menu, wx.ID_ANY, "生成图形...")
        edit_menu.AppendSeparator()
        copy_item = map_item(edit_menu, wx.ID_ANY, f"复制\t{mod}+C")
        cut_item = map_item(edit_menu, wx.ID_ANY, f"剪切\t{mod}+X")
        paste_item = map_item(edit_menu, wx.ID_ANY, f"粘贴\t{mod}+V")

        object_menu = wx.Menu()
        add_object_items = [
            map_item(object_menu, wx.ID_ANY, f"添加对象...\t{mod}+Shift+A"),
            map_item(object_menu, wx.ID_ANY, "编辑对象..."),
            map_item(object_menu, wx.ID_ANY, "删除对象...\tDelete"),
        ]
        add_object_item, edit_object_item, delete_object_item = add_object_items
        object_menu.AppendSeparator()
        copy_object_item = map_item(object_menu, wx.ID_ANY, f"复制对象\t{mod}+Shift+C")
        cut_object_item = map_item(object_menu, wx.ID_ANY, f"剪切对象\t{mod}+Shift+X")
        paste_object_item = map_item(object_menu, wx.ID_ANY, f"粘贴对象\t{mod}+Shift+V")
        object_menu.AppendSeparator()
        clear_all_objects_item = map_item(object_menu, wx.ID_ANY, "清除所有对象")
        object_menu.AppendSeparator()
        object_manager_item = map_item(
            object_menu, wx.ID_ANY, f"对象管理器...\t{mod}+Shift+M"
        )

        collision_menu = wx.Menu()
        toggle_collision_item = map_item(
            collision_menu, wx.ID_ANY, "标记/取消碰撞\tSpace"
        )

        menubar.Append(file_menu, "文件 &F" if IS_WINDOWS else "文件")
        menubar.Append(edit_menu, "编辑 &E" if IS_WINDOWS else "编辑")
        menubar.Append(object_menu, "对象 &O" if IS_WINDOWS else "对象")
        menubar.Append(collision_menu, "碰撞 &C" if IS_WINDOWS else "碰撞")
        self.SetMenuBar(menubar)
        self._menubar = menubar

        self.Bind(wx.EVT_MENU, self.on_open, open_item)
        self.Bind(wx.EVT_MENU, self.on_import_data_source, import_data_item)
        self.Bind(wx.EVT_MENU, self.on_save, save_item)
        self.Bind(wx.EVT_MENU, self.on_save_as, save_as_item)
        self.Bind(wx.EVT_MENU, self.on_resize, resize_item)
        self.Bind(wx.EVT_MENU, self.on_custom_tiles, custom_tile_item)
        self.Bind(wx.EVT_MENU, self.on_edit_map_properties, map_prop_item)
        self.Bind(wx.EVT_MENU, self.on_close_file, close_item)
        self.Bind(wx.EVT_MENU, self.on_exit, exit_item)
        self.Bind(wx.EVT_MENU, self.on_about, about_item)
        self.Bind(wx.EVT_MENU, self.on_undo, undo_item)
        self.Bind(wx.EVT_MENU, self.on_redo, redo_item)
        self.Bind(wx.EVT_MENU, self.clear_selected, clear_item)
        self.Bind(wx.EVT_MENU, self.delete_selection, delete_item)
        self.Bind(wx.EVT_MENU, self.on_set_tile, select_tile_item)
        self.Bind(wx.EVT_MENU, self.on_selection_start, selection_start_item)
        self.Bind(wx.EVT_MENU, self.on_selection_end, selection_end_item)
        self.Bind(wx.EVT_MENU, self.on_fill_selection, fill_item)
        self.Bind(wx.EVT_MENU, self.on_generate_shape, generate_shape_item)
        self.Bind(wx.EVT_MENU, self.copy_selection, copy_item)
        self.Bind(wx.EVT_MENU, self.cut_selection, cut_item)
        self.Bind(wx.EVT_MENU, self.paste_clipboard, paste_item)
        self.Bind(wx.EVT_MENU, self.on_goto_cell, goto_item)
        self.Bind(wx.EVT_MENU, self._clear_landmarks, clear_landmarks_item)
        self.Bind(wx.EVT_MENU, self.on_add_object, add_object_item)
        self.Bind(wx.EVT_MENU, self.on_edit_object, edit_object_item)
        self.Bind(wx.EVT_MENU, self.on_delete_object, delete_object_item)
        self.Bind(wx.EVT_MENU, self.copy_object, copy_object_item)
        self.Bind(wx.EVT_MENU, self.cut_object, cut_object_item)
        self.Bind(wx.EVT_MENU, self.paste_object, paste_object_item)
        self.Bind(wx.EVT_MENU, self.on_clear_all_objects, clear_all_objects_item)
        self.Bind(wx.EVT_MENU, self.on_open_object_manager, object_manager_item)
        self.Bind(wx.EVT_MENU, self._on_toggle_collision, toggle_collision_item)
        self.Bind(wx.EVT_CLOSE, self.on_minimize)
        self.Bind(wx.EVT_CHAR_HOOK, self.on_global_key)

    def _set_map_mode(self, enabled):
        """切换地图模式：启用/禁用地图专用菜单项与对象/碰撞顶层菜单。"""
        if not hasattr(self, "_map_menu_items"):
            return
        for item in self._map_menu_items:
            try:
                item.Enable(enabled)
            except Exception:
                pass
        if hasattr(self, "_menubar"):
            for top in (2, 3):
                if top < self._menubar.GetMenuCount():
                    self._menubar.EnableTop(top, enabled)

    def on_undo(self, event):
        if hasattr(self, "main_book") and self.main_book.GetSelection() == 1:
            self.data_panel.undo()
            return
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
        if hasattr(self, "main_book") and self.main_book.GetSelection() == 1:
            self.data_panel.redo()
            return
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
        map_active = hasattr(self, "main_book") and self.main_book.GetSelection() == 0

        if key == wx.WXK_TAB:
            if self.grid.HasFocus():
                self.tree_panel.tree.SetFocus()
                return
            if self.tree_panel.tree.HasFocus() and map_active:
                self.grid.SetFocus()
                return

        if event.ControlDown() and not event.ShiftDown():
            if key == ord("S"):
                self.on_save(None)
                return
            if key == ord("Z"):
                self.on_undo(None)
                return
            if key == ord("Y"):
                self.on_redo(None)
                return

        if not map_active:
            event.Skip()
            return

        if event.ControlDown() and event.ShiftDown():
            if key == ord("A"):
                self.on_add_object(None)
                return
            elif key == ord("S"):
                self.on_save_as(None)
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
        elif event.ControlDown():
            if key == ord("R"):
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
        elif key == wx.WXK_ESCAPE:
            if self.grid.HasFocus():
                self.clear_selected(None)
                return
            event.Skip()
            return
        elif key == wx.WXK_DELETE:
            if self.grid.HasFocus():
                _, obj = self.data_manager.find_object_at(self.cursor_x, self.cursor_y)
                if obj:
                    self.on_delete_object(None)
                return
            event.Skip()
            return
        elif key == wx.WXK_BACK:
            if self.grid.HasFocus():
                self.delete_selection(None)
                return
            event.Skip()
            return
        elif key == wx.WXK_SPACE:
            if self.grid.HasFocus():
                self._on_toggle_collision(None)
                return
            event.Skip()
            return
        event.Skip()

    def _on_toggle_collision(self, event):
        dm = self.data_manager
        bounds = self.get_selection_bounds()
        if bounds:
            left, top, right, bottom = bounds
            target_state = (self.cursor_x, self.cursor_y) not in dm.collision_set
            changes = []
            for y in range(top, bottom + 1):
                for x in range(left, right + 1):
                    changes.append((x, y, target_state))
            dm.set_collision_bulk(changes)
            self._clear_selection()
            self.update_status()
            TTS.cancel()
            action = "标记碰撞" if target_state else "取消碰撞"
            count = len(changes)
            TTS.speak(f"{action} {count} 个格子")
        else:
            state = dm.toggle_collision(self.cursor_x, self.cursor_y)
            self.update_status()
            TTS.cancel()
            action = "标记碰撞" if state else "取消碰撞"
            TTS.speak(f"{action}")

    def is_map_modified(self):
        return self._clean_map_state != self._get_map_state()

    def on_minimize(self, event):
        self.Iconize()

    def on_close_file(self, event):
        if not self._confirm_save_if_modified():
            return
        self.reset_to_default_map()

    def reset_to_default_map(self):
        self.data_manager.clear()
        self.map_tile_definitions = {}
        self.root_tile_definitions = self.load_tiled_data()
        self._sync_tile_definitions()
        self.object_definitions = self.load_object_definitions()
        self.cursor_x = 0
        self.cursor_y = 0
        self.landmarks.clear()
        self.grid.SetGridCursor(self.cursor_y, self.cursor_x)
        self.grid.SelectBlock(self.cursor_y, self.cursor_x, self.cursor_y, self.cursor_x)
        self.grid.MakeCellVisible(self.cursor_y, self.cursor_x)
        self.current_file = None
        self._clear_selection()
        self._mark_map_clean()
        TTS.speak("地图已重置")
        self.update_title()

    def on_exit(self, event):
        if not self._confirm_save_if_modified():
            return
        result = wx.MessageBox(
            "是否退出地图编辑器？", "确认退出", wx.YES_NO | wx.ICON_QUESTION
        )
        if int(result) == WX_YES:
            self.Destroy()

    def on_about(self, event):
        info = wx.adv.AboutDialogInfo()
        info.SetName("地图编辑器")
        info.SetVersion("V1.0")
        info.SetDescription("跨平台地图与游戏数据编辑器")
        info.AddDeveloper("MapEditor")
        wx.adv.AboutBox(info)

    def on_save_file(self):
        default_dir = ""
        default_file = ""
        if self.current_file:
            default_dir = os.path.dirname(self.current_file)
            default_file = os.path.basename(self.current_file)

        with wx.FileDialog(
            self,
            "保存地图",
            defaultDir=default_dir,
            defaultFile=default_file,
            wildcard="Tiled JSON (*.json)|*.json",
            style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT,
        ) as dlg:
            if dlg.ShowModal() == wx.ID_OK:
                return self._save_map_to_path(dlg.GetPath())
        return False

    def on_resize(self, event):
        dm = self.data_manager
        dlg = ResizeDialog(self, dm.width, dm.height)
        if dlg.ShowModal() == wx.ID_OK:
            new_w, new_h = dlg.get_size()
            if new_w <= 0 or new_h <= 0:
                wx.MessageBox("尺寸必须大于0", "错误", wx.OK | wx.ICON_ERROR)
                return

            dm.resize(new_w, new_h)

            TTS.speak(f"尺寸已调整为{new_w}乘{new_h}")
        dlg.Destroy()

    def on_custom_tiles(self, event):
        self.Enable(False)
        self.Unbind(wx.EVT_CHAR_HOOK)
        self.tile_window = CustomTileDialog(
            self, self.tile_definitions, self.tile_definition_sources
        )
        self.tile_window.Show()

    def on_edit_map_properties(self, event):
        dlg = MapPropertiesDialog(self, self.data_manager.map_properties)
        if dlg.ShowModal() == wx.ID_OK:
            self.data_manager.map_properties = dlg.get_properties()
            TTS.speak("地图属性已更新")
        dlg.Destroy()

    def enable_and_update(self, tile_data):
        global TILE_DEFINITIONS
        normalized = self._normalize_tile_definitions(tile_data)
        previous_sources = copy.deepcopy(self.tile_definition_sources)
        previous_map_defs = copy.deepcopy(self.map_tile_definitions)
        used_ids = self._get_used_tile_ids()
        self.map_tile_definitions = {
            tile_id: copy.deepcopy(tile_info)
            for tile_id, tile_info in normalized.items()
            if tile_id in used_ids
            or previous_sources.get(tile_id, {}).get("source") == "map"
        }
        for tile_id in list(previous_map_defs.keys()):
            if tile_id not in normalized:
                self.map_tile_definitions.pop(tile_id, None)

        self.root_tile_definitions = self._dedupe_tile_definitions(normalized)
        self._sync_tile_definitions()
        TILE_DEFINITIONS = self.tile_definitions.copy()
        self.Enable(True)
        self.Bind(wx.EVT_CHAR_HOOK, self.on_global_key)
        self.Raise()

    def update_status(self):
        dm = self.data_manager
        tile_name = self._get_tile_name(self.cursor_x, self.cursor_y)

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

        landmark_prefix = ""
        for idx, (lx, ly) in self.landmarks.items():
            if lx == self.cursor_x and ly == self.cursor_y:
                label = "0" if idx == 10 else str(idx)
                landmark_prefix = f"路标{label}；"
                break

        if obj_info:
            status_text = f"{landmark_prefix}{coord_info} ； {obj_info} ； {tile_name}"
        else:
            status_text = f"{landmark_prefix}{coord_info} ； {tile_name}"
        self.status_label.SetLabel(status_text)

        if not getattr(self, "_silent_status", False):
            TTS.cancel()
            collision_info = (
                "碰撞" if (self.cursor_x, self.cursor_y) in dm.collision_set else ""
            )
            if obj_tts:
                TTS.speak(f"{landmark_prefix}{obj_tts} {tile_name} {collision_info} {coord_info}")
            else:
                TTS.speak(f"{landmark_prefix}{tile_name} {collision_info} {coord_info}")
        self.status_label.Refresh()
        wx.Yield()

    def _get_tile_name(self, x, y):
        dm = self.data_manager
        tile_id = str(dm.map_data[y][x])
        tile_data = self.tile_definitions.get(tile_id)
        if tile_data:
            if isinstance(tile_data, dict):
                return tile_data.get("name", f"未知({tile_id})")
            else:
                return tile_data
        return f"未知({tile_id})"

    def _route_key_index(self, key):
        if key == ord("0"):
            return 10
        if ord("1") <= key <= ord("9"):
            return key - ord("0")
        return None

    def _move_grid_cursor(self, x, y):
        self.cursor_x = x
        self.cursor_y = y
        self.grid.SelectBlock(y, x, y, x)
        self.grid.MakeCellVisible(y, x)
        self.grid.SetGridCursor(y, x)
        self.update_status()

    def _selection_summary(self):
        bounds = self.get_selection_bounds()
        if not bounds:
            return "没有选区"
        left, top, right, bottom = bounds
        width = right - left + 1
        height = bottom - top + 1
        return f"已选:宽{width}，高{height}， ({left}, {top}) 到 ({right}, {bottom})；"

    def _add_landmark(self, index):
        self.landmarks[index] = (self.cursor_x, self.cursor_y)
        tile_name = self._get_tile_name(self.cursor_x, self.cursor_y)
        TTS.cancel()
        TTS.speak(f"已添加 {tile_name}，{self.cursor_x}，{self.cursor_y}")

    def _clear_landmarks(self, event=None):
        self.landmarks.clear()
        TTS.cancel()
        TTS.speak("已清理所有路标")

    def _jump_to_landmark(self, index):
        coord = self.landmarks.get(index)
        if coord is None:
            TTS.cancel()
            wx.CallAfter(lambda: TTS.speak("未设置路标"))
            return
        x, y = coord
        dm = self.data_manager
        if not (0 <= x < dm.width and 0 <= y < dm.height):
            self.landmarks.pop(index, None)
            TTS.cancel()
            TTS.speak("路标已超出范围")
            return
        self._move_grid_cursor(x, y)

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

    def on_key_up(self, event):
        if not event.ShiftDown():
            self._shift_selecting = False
        event.Skip()

    def on_key_down(self, event):
        key = event.GetKeyCode()
        modifiers = event.GetModifiers()
        moved = False

        dm = self.data_manager
        arrow_keys = [wx.WXK_LEFT, wx.WXK_RIGHT, wx.WXK_UP, wx.WXK_DOWN]
        is_shift_arrow = key in arrow_keys and modifiers == wx.MOD_SHIFT
        if not is_shift_arrow:
            self._shift_selecting = False

        if event.ControlDown() and not event.AltDown() and key in (ord("`"), ord("~")):
            self._clear_landmarks()
            return

        landmark_index = self._route_key_index(key)
        if landmark_index is not None:
            if modifiers == wx.MOD_CONTROL:
                self._add_landmark(landmark_index)
                return
            if modifiers == wx.MOD_NONE:
                self._jump_to_landmark(landmark_index)
                return

        if key in arrow_keys:
            if modifiers == wx.MOD_CONTROL:
                dm_ctrl = self.data_manager
                cx, cy = self.cursor_x, self.cursor_y
                cur = dm_ctrl.map_data[cy][cx]
                if cur not in (0, "0"):
                    nx, ny = cx, cy
                    if key == wx.WXK_RIGHT:
                        while nx + 1 < dm_ctrl.width and dm_ctrl.map_data[cy][nx + 1] == cur:
                            nx += 1
                    elif key == wx.WXK_LEFT:
                        while nx - 1 >= 0 and dm_ctrl.map_data[cy][nx - 1] == cur:
                            nx -= 1
                    elif key == wx.WXK_DOWN:
                        while ny + 1 < dm_ctrl.height and dm_ctrl.map_data[ny + 1][cx] == cur:
                            ny += 1
                    elif key == wx.WXK_UP:
                        while ny - 1 >= 0 and dm_ctrl.map_data[ny - 1][cx] == cur:
                            ny -= 1
                    self._move_grid_cursor(nx, ny)
                    TTS.cancel()
                    TTS.speak(self._get_tile_name(nx, ny))
                    return
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
            if moved and modifiers == wx.MOD_SHIFT:
                if not self._shift_selecting:
                    self._clear_selection()
                    self.selection_start = (old_x, old_y)
                    self._shift_selecting = True
                self.selection_end = (self.cursor_x, self.cursor_y)
                left, top, right, bottom = self.get_selection_bounds()
                self.grid.SetGridCursor(self.cursor_y, self.cursor_x)
                self.grid.SelectBlock(top, left, bottom, right)
                self.grid.MakeCellVisible(self.cursor_y, self.cursor_x)
                self.update_status()
                TTS.cancel()
                TTS.speak(self._selection_summary())
                return
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
                TTS.speak(self._selection_summary())
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

    def on_selection_start(self, event):
        self.selection_start = (self.cursor_x, self.cursor_y)
        self.update_status()
        TTS.cancel()
        TTS.speak("选区开始")

    def on_selection_end(self, event):
        self.selection_end = (self.cursor_x, self.cursor_y)
        self.update_status()
        TTS.cancel()
        TTS.speak(self._selection_summary())

    def on_grid_select(self, event):
        self.cursor_y = event.GetRow()
        self.cursor_x = event.GetCol()
        self.update_status()
        event.Skip()

    def on_set_tile(self, event):
        dlg = TileSelectionDialog(
            self, self.tile_definitions, self.tile_definition_sources
        )
        if dlg.ShowModal() == wx.ID_OK:
            tile_id = dlg.GetSelectedTileId()
            self._promote_tile_definition_to_map(tile_id)
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

    def _get_landmark_polygon_points(self):
        points = []
        for index in range(1, 11):
            coord = self.landmarks.get(index)
            if coord is not None:
                points.append(coord)
        return points

    def _polygon_area2(self, points):
        area2 = 0
        for i, (x1, y1) in enumerate(points):
            x2, y2 = points[(i + 1) % len(points)]
            area2 += x1 * y2 - x2 * y1
        return area2

    def _orientation(self, a, b, c):
        return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])

    def _point_on_segment(self, point, start, end):
        if self._orientation(start, end, point) != 0:
            return False
        return (
            min(start[0], end[0]) <= point[0] <= max(start[0], end[0])
            and min(start[1], end[1]) <= point[1] <= max(start[1], end[1])
        )

    def _segments_intersect(self, a, b, c, d):
        o1 = self._orientation(a, b, c)
        o2 = self._orientation(a, b, d)
        o3 = self._orientation(c, d, a)
        o4 = self._orientation(c, d, b)
        if o1 == 0 and self._point_on_segment(c, a, b):
            return True
        if o2 == 0 and self._point_on_segment(d, a, b):
            return True
        if o3 == 0 and self._point_on_segment(a, c, d):
            return True
        if o4 == 0 and self._point_on_segment(b, c, d):
            return True
        return (o1 > 0) != (o2 > 0) and (o3 > 0) != (o4 > 0)

    def _polygon_self_intersects(self, points):
        count = len(points)
        for i in range(count):
            a = points[i]
            b = points[(i + 1) % count]
            for j in range(i + 1, count):
                if j == i or j == (i + 1) % count or i == (j + 1) % count:
                    continue
                c = points[j]
                d = points[(j + 1) % count]
                if self._segments_intersect(a, b, c, d):
                    return True
        return False

    def _point_in_polygon(self, point, points):
        x, y = point
        inside = False
        for i, start in enumerate(points):
            end = points[(i + 1) % len(points)]
            if self._point_on_segment(point, start, end):
                return True
            x1, y1 = start
            x2, y2 = end
            if (y1 > y) != (y2 > y):
                intersect_x = x1 + (y - y1) * (x2 - x1) / (y2 - y1)
                if x < intersect_x:
                    inside = not inside
        return inside

    def _get_polygon_fill_cells(self, points):
        dm = self.data_manager
        if len(points) < 3:
            return None
        if len(set(points)) < 3 or self._polygon_area2(points) == 0:
            TTS.cancel()
            TTS.speak("路标无法组成封闭区域")
            return []
        if self._polygon_self_intersects(points):
            TTS.cancel()
            TTS.speak("路标图形交叉，无法填充")
            return []

        left = min(x for x, _ in points)
        right = max(x for x, _ in points)
        top = min(y for _, y in points)
        bottom = max(y for _, y in points)
        cells = []
        for y in range(top, bottom + 1):
            for x in range(left, right + 1):
                if 0 <= x < dm.width and 0 <= y < dm.height and self._point_in_polygon((x, y), points):
                    cells.append((x, y))
        return cells

    def _get_landmark_polygon_fill_cells(self):
        points = self._get_landmark_polygon_points()
        if len(points) < 3:
            return None
        return self._get_polygon_fill_cells(points)

    def _shape_left_top(self, x, y, width, height, anchor):
        if anchor == "中心点":
            return x - width // 2, y - height // 2
        return x, y

    def _get_shape_solid_cells(self, shape, left, top, width, height):
        if width <= 0 or height <= 0:
            return set()

        if shape == "路标多边形":
            cells = self._get_landmark_polygon_fill_cells()
            return set(cells or [])

        if shape == "三角形":
            points = [
                (left + width // 2, top),
                (left, top + height - 1),
                (left + width - 1, top + height - 1),
            ]
            cells = self._get_polygon_fill_cells(points)
            return set(cells or [])

        cells = set()
        center_x = (width - 1) / 2
        center_y = (height - 1) / 2
        radius_x = max(center_x, 0.5)
        radius_y = max(center_y, 0.5)

        for y in range(top, top + height):
            for x in range(left, left + width):
                rel_x = x - left
                rel_y = y - top
                if shape == "矩形":
                    cells.add((x, y))
                elif shape == "椭圆":
                    dx = (rel_x - center_x) / radius_x
                    dy = (rel_y - center_y) / radius_y
                    if dx * dx + dy * dy <= 1:
                        cells.add((x, y))
                elif shape == "菱形":
                    dx = abs(rel_x - center_x) / radius_x
                    dy = abs(rel_y - center_y) / radius_y
                    if dx + dy <= 1:
                        cells.add((x, y))
        return cells

    def _erode_cells(self, cells, steps):
        current = set(cells)
        neighbors = [
            (-1, -1), (0, -1), (1, -1),
            (-1, 0), (0, 0), (1, 0),
            (-1, 1), (0, 1), (1, 1),
        ]
        for _ in range(steps):
            current = {
                (x, y)
                for x, y in current
                if all((x + dx, y + dy) in current for dx, dy in neighbors)
            }
            if not current:
                break
        return current

    def _dilate_cells(self, cells, steps):
        current = set(cells)
        neighbors = [
            (-1, -1), (0, -1), (1, -1),
            (-1, 0), (0, 0), (1, 0),
            (-1, 1), (0, 1), (1, 1),
        ]
        for _ in range(steps):
            expanded = set(current)
            for x, y in current:
                for dx, dy in neighbors:
                    expanded.add((x + dx, y + dy))
            current = expanded
        return current

    def _get_shape_cells(self, config):
        left, top = self._shape_left_top(
            config["x"],
            config["y"],
            config["width"],
            config["height"],
            config["anchor"],
        )
        solid_cells = self._get_shape_solid_cells(
            config["shape"], left, top, config["width"], config["height"]
        )

        if config["mode"] == "边框":
            thickness = max(1, config["thickness"])
            inner_cells = self._erode_cells(solid_cells, 1)
            if config["border_direction"] == "向外":
                outer_cells = self._dilate_cells(solid_cells, thickness - 1)
                cells = outer_cells - inner_cells
            else:
                inner_cells = self._erode_cells(solid_cells, thickness)
                cells = solid_cells - inner_cells
        else:
            cells = solid_cells

        dm = self.data_manager
        return sorted(
            (x, y)
            for x, y in cells
            if 0 <= x < dm.width and 0 <= y < dm.height
        )

    def _shape_feedback_size(self, config, cells):
        if cells:
            left = min(x for x, _ in cells)
            right = max(x for x, _ in cells)
            top = min(y for _, y in cells)
            bottom = max(y for _, y in cells)
            return right - left + 1, bottom - top + 1
        return config["width"], config["height"]

    def copy_selection(self, event):
        global CLIPBOARD
        dm = self.data_manager
        bounds = self.get_selection_bounds()
        if bounds:
            left, top, right, bottom = bounds
            single = False
        else:
            left = right = self.cursor_x
            top = bottom = self.cursor_y
            single = True
        CLIPBOARD = dm.snapshot_region(left, top, right, bottom)
        self._clear_selection()
        self.update_status()
        TTS.cancel()
        TTS.speak("复制" if single else "复制选区")

    def cut_selection(self, event):
        global CLIPBOARD
        dm = self.data_manager
        bounds = self.get_selection_bounds()
        if bounds:
            left, top, right, bottom = bounds
            single = False
        else:
            left = right = self.cursor_x
            top = bottom = self.cursor_y
            single = True
        CLIPBOARD = dm.snapshot_region(left, top, right, bottom)
        dm.clear_region(left, top, right, bottom)
        self._clear_selection()
        self.update_status()
        TTS.cancel()
        TTS.speak("剪切" if single else "剪切选区")

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
        dlg = TileSelectionDialog(
            self, self.tile_definitions, self.tile_definition_sources
        )
        if dlg.ShowModal() == wx.ID_OK:
            tile_id = dlg.GetSelectedTileId()
            self._fill_selection(tile_id)
            self.Refresh()
        dlg.Destroy()

    def on_generate_shape(self, event):
        tile_dlg = TileSelectionDialog(
            self, self.tile_definitions, self.tile_definition_sources
        )
        if tile_dlg.ShowModal() != wx.ID_OK:
            tile_dlg.Destroy()
            return
        tile_id = tile_dlg.GetSelectedTileId()
        tile_dlg.Destroy()

        shape_dlg = ShapeGenerationDialog(self, self.cursor_x, self.cursor_y)
        if shape_dlg.ShowModal() == wx.ID_OK:
            config = shape_dlg.get_config()
            cells = self._get_shape_cells(config)
            if cells:
                self._promote_tile_definition_to_map(tile_id)
                self.data_manager.set_tiles_bulk([(x, y, tile_id) for x, y in cells])
                self._clear_selection()
                width, height = self._shape_feedback_size(config, cells)
                TTS.cancel()
                TTS.speak(f"生成{config['shape']}，长{width}宽{height}")
            else:
                TTS.cancel()
                TTS.speak("没有可生成的图形")
        shape_dlg.Destroy()

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
            polygon_cells = self._get_landmark_polygon_fill_cells()
            if polygon_cells is None:
                changes.append((self.cursor_x, self.cursor_y, tile_id))
            else:
                changes.extend((x, y, tile_id) for x, y in polygon_cells)
        if changes:
            self._promote_tile_definition_to_map(tile_id)
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
        if not CLIPBOARD:
            TTS.cancel()
            TTS.speak("剪贴板为空")
            return
        paste_h = CLIPBOARD.get("height", 0)
        paste_w = CLIPBOARD.get("width", 0)
        if paste_w <= 0 or paste_h <= 0:
            TTS.cancel()
            TTS.speak("剪贴板为空")
            return

        if (self.cursor_y + paste_h > dm.height
                or self.cursor_x + paste_w > dm.width):
            wx.MessageBox(
                "粘贴区域超出地图边界", "错误", wx.OK | wx.ICON_ERROR
            )
            return

        if (paste_w * paste_h > 1 and dm.destination_has_content(
            self.cursor_x, self.cursor_y, paste_w, paste_h
        )):
            result = wx.MessageBox(
                "目标区域已有内容，是否覆盖？",
                "确认",
                wx.YES_NO | wx.ICON_QUESTION,
            )
            if int(result) != WX_YES:
                TTS.cancel()
                TTS.speak("已取消粘贴")
                return

        dm.paste_region(CLIPBOARD, self.cursor_x, self.cursor_y)
        self._clear_selection()
        TTS.cancel()
        TTS.speak("粘贴")

    def copy_object(self, event):
        _, obj = self.data_manager.find_object_at(
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
        _, obj = self.data_manager.find_object_at(
            self.cursor_x, self.cursor_y
        )
        if not obj:
            wx.MessageBox(
                "当前光标位置没有对象！", "提示", wx.OK | wx.ICON_WARNING
            )
            return
        self.object_clipboard = copy.deepcopy(obj)
        self.data_manager.remove_object(obj.get("id"))
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
        new_obj.pop("id", None)
        self.data_manager.add_object(new_obj)
        self._upsert_object_template(new_obj)
        TTS.cancel()
        TTS.speak(f"已粘贴对象：{new_obj.get('name', '')}")

    def on_add_object(self, event):
        dlg = ObjectDialog(
            self,
            is_edit=False,
            next_id=self.data_manager.next_object_id,
            default_tile_x=self.cursor_x,
            default_tile_y=self.cursor_y,
            object_definitions=self.object_definitions,
            data_manager=self.data_manager,
        )
        if dlg.ShowModal() == wx.ID_OK:
            obj_data = dlg.get_object_data()
            self.data_manager.add_object(obj_data)
            self._upsert_object_template(obj_data)
            TTS.cancel()
            TTS.speak(f"已添加对象：{obj_data.get('name', '')}")
        dlg.Destroy()

    def on_edit_object(self, event):
        _, obj = self.data_manager.find_object_at(
            self.cursor_x, self.cursor_y
        )
        if not obj:
            wx.MessageBox(
                "当前光标位置没有对象！", "提示", wx.OK | wx.ICON_WARNING
            )
            return

        self._silent_status = True
        dlg = ObjectDialog(
            self,
            obj_data=obj,
            is_edit=True,
            next_id=self.data_manager.next_object_id,
            object_definitions=self.object_definitions,
            data_manager=self.data_manager,
        )
        if dlg.ShowModal() == wx.ID_OK:
            new_obj_data = dlg.get_object_data()
            if self.data_manager.modify_object(obj.get("id"), new_obj_data):
                self._upsert_object_template(new_obj_data)
            del self._silent_status
            TTS.speak(f"已编辑对象：{new_obj_data.get('name', '')}")
        else:
            del self._silent_status
        dlg.Destroy()

    def on_delete_object(self, event):
        _, obj = self.data_manager.find_object_at(
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
        if int(result) == WX_YES:
            self.data_manager.remove_object(obj.get("id"))
            TTS.speak("已删除对象")

    def on_clear_all_objects(self, event):
        result = wx.MessageBox(
            "确定要清除所有对象吗？", "确认", wx.YES_NO | wx.ICON_QUESTION
        )
        if int(result) == WX_YES:
            self.data_manager.clear_objects()
            TTS.speak("已清除所有对象")

    def on_open_object_manager(self, event):
        if self.object_manager_dlg:
            self.object_manager_dlg.Raise()
            return
        self.object_manager_dlg = ObjectManagerDialog(self, self.data_manager)

    def on_open(self, event):
        if not self._confirm_save_if_modified():
            return

        with wx.FileDialog(
            self,
            "打开地图",
            wildcard="Tiled JSON (*.json)|*.json",
            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST,
        ) as dlg:
            if dlg.ShowModal() == wx.ID_OK:
                filepath = dlg.GetPath()
                if self.load_from_tiled_json(filepath):
                    self.current_file = filepath
                    self._mark_map_clean()
                    self.update_title()

    def update_title(self):
        parts = []
        if self.current_file:
            map_name = os.path.basename(self.current_file)
            if self.is_map_modified():
                map_name = "*" + map_name
            parts.append(map_name)
        if hasattr(self, "data_panel") and self.data_panel.manager.is_loaded():
            data_name = self.data_panel.current_file_id or os.path.basename(
                self.data_panel.active_path() or ""
            )
            if self.data_panel.is_file_modified():
                data_name = "*" + data_name
            parts.append(data_name)
        suffix = " | ".join(parts) if parts else ""
        base = "地图编辑器 V1.0"
        self.SetTitle(f"{suffix} - {base}" if suffix else base)

    def load_from_tiled_json(self, filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)

            if not self.data_manager.load_from_dict(data):
                wx.MessageBox("地图数据无效！", "错误", wx.OK | wx.ICON_ERROR)
                return False

            global TILE_DEFINITIONS
            self.root_tile_definitions = self.load_tiled_data()
            self.map_tile_definitions = self._normalize_tile_definitions(
                data.get("tile_definitions", {})
            )
            self._sync_tile_definitions()
            TILE_DEFINITIONS = self.tile_definitions.copy()
            self.object_definitions = self.load_object_definitions()

            self.cursor_x = 0
            self.cursor_y = 0
            self.landmarks.clear()
            self.grid.SetGridCursor(self.cursor_y, self.cursor_x)
            self.grid.SelectBlock(self.cursor_y, self.cursor_x, self.cursor_y, self.cursor_x)
            self.grid.MakeCellVisible(self.cursor_y, self.cursor_x)
            self.update_status()

            dm = self.data_manager
            wx.MessageBox(
                f"成功加载地图：{dm.width}x{dm.height}", "提示", wx.OK
            )
            TTS.speak(f"已加载地图，宽度{dm.width}，高度{dm.height}")
            return True

        except Exception as e:
            wx.MessageBox(f"加载失败：{str(e)}", "错误", wx.OK | wx.ICON_ERROR)
            return False

    def rebuild_grid(self):
        dm = self.data_manager
        self.grid.BeginBatch()
        try:
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
        finally:
            self.grid.EndBatch()
        self.grid.ForceRefresh()

    def on_save(self, event):
        if hasattr(self, "main_book") and self.main_book.GetSelection() == 1:
            if self.data_panel.is_file_modified() or self.data_panel.manager.is_loaded():
                if self.data_panel.save():
                    wx.MessageBox("数据已保存（已生成时间戳备份）", "成功", wx.OK)
                    self.update_title()
                return
        self.save_current_file()

    def on_save_as(self, event):
        self.on_save_file()

    def save_to_tiled_json(self, filepath):
        try:
            tiled_json = self.data_manager.to_dict(self._get_used_tile_definitions())
            json_str = json.dumps(tiled_json, indent=2, ensure_ascii=False)

            def format_impassable_section(s):
                marker = '"impassable": ['
                start = s.find(marker)
                if start == -1:
                    return s
                bracket_pos = start + len(marker) - 1
                depth = 1
                pos = bracket_pos + 1
                while pos < len(s) and depth > 0:
                    if s[pos] == '[':
                        depth += 1
                    elif s[pos] == ']':
                        depth -= 1
                    pos += 1
                end = pos
                content = s[bracket_pos + 1:end - 1]
                arr = json.loads("[" + content + "]")
                if not arr:
                    return s[:start] + '"impassable": []' + s[end:]
                pairs = [f"[{p[0]}, {p[1]}]" for p in arr]
                line_groups = [
                    ", ".join(pairs[i:i + 50])
                    for i in range(0, len(pairs), 50)
                ]
                replacement = (
                    '"impassable": [\n      '
                    + ",\n      ".join(line_groups)
                    + "\n    ]"
                )
                return s[:start] + replacement + s[end:]

            json_str = format_impassable_section(json_str)

            with open(filepath, "w", encoding="utf-8") as f:
                f.write(json_str)
            self._save_root_tile_definitions()
            self._save_root_object_definitions()
            return True
        except Exception as e:
            wx.MessageBox(f"保存失败：{str(e)}", "错误", wx.OK | wx.ICON_ERROR)
            return False


class MapEditorApp(wx.App):
    def OnInit(self):
        if IS_MACOS:
            try:
                locale.setlocale(locale.LC_ALL, "zh_CN.UTF-8")
            except locale.Error:
                pass
            self._locale = wx.Locale()
            self._locale.Init(wx.LANGUAGE_CHINESE_SIMPLIFIED, wx.LOCALE_DONT_LOAD_DEFAULT)

        self.instance = wx.SingleInstanceChecker("MapEditor")
        if self.instance.IsAnotherRunning():
            wx.MessageBox("编辑器已在运行！", "提示", wx.OK)
            return False

        frame = MapEditorFrame()
        frame.Show()
        return True


if __name__ == "__main__":
    expiry_guard.check()
    app = MapEditorApp()
    app.MainLoop()
