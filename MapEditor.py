import copy
import ctypes
import json
import os
import re
import TTS
import wx
import wx.grid as gridlib


# 瓦片类型定义
TILE_DEFINITIONS = {}


# 全局剪贴板
# 二维列表 [[row1], [row2], ...]
CLIPBOARD = None  


class TileSelectionDialog(wx.Dialog):
    """瓦片选择对话框"""
    def __init__(self, parent, tile_defs):
        """
        初始化对话框
        """
        super().__init__(parent, title="选择瓦片")
        # 垂直布局管理器
        sizer = wx.BoxSizer(wx.VERTICAL)
        # 列表框选项（数字排序）
        choices = []
        for k, v in sorted(tile_defs.items(), key=lambda x: int(x[0])):
            if isinstance(v, dict):
                name = v.get("name", "")
                props = v.get("properties", {})
            else:
                name = v
                props = {}
            
            # 追加属性信息
            if props:
                prop_str = ", ".join([f"{p_k}={p_v}" for p_k, p_v in props.items()])
                choices.append(f"{k}: {name} ({prop_str})")
            else:
                choices.append(f"{k}: {name}")
        # 选中第一项
        self.listbox = wx.ListBox(self, choices=choices)
        self.listbox.SetSelection(0)
        # 列表框添加到布局
        sizer.Add(self.listbox, 1, wx.ALL | wx.EXPAND, 10)
        
        btn_sizer = self.CreateButtonSizer(wx.OK | wx.CANCEL)
        sizer.Add(btn_sizer, 0, wx.ALL | wx.EXPAND, 10)
        # 设置对话框布局
        self.SetSizer(sizer)
        # 设置列表框为焦点控件
        self.listbox.SetFocus()
        # 存储排序后的瓦片ID列表
        self.tile_keys = list(sorted(tile_defs.keys(), key=lambda x: int(x)))

    def GetSelectedTileId(self):
        """
        获取选中的瓦片ID
        """
        sel = self.listbox.GetSelection()
        if sel != wx.NOT_FOUND:
            return self.tile_keys[sel]
        return 0


class ResizeDialog(wx.Dialog):
    """地图尺寸调整对话框"""
    def __init__(self, parent, current_w, current_h):
        """
        初始化对话框
        """
        super().__init__(parent, title="调整地图尺寸")
        # 创建垂直布局管理器
        sizer = wx.BoxSizer(wx.VERTICAL)
        
        # 宽度输入行
        w_sizer = wx.BoxSizer(wx.HORIZONTAL)
        w_sizer.Add(wx.StaticText(self, label="宽度:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
        # 数值选择框
        self.width_ctrl = wx.SpinCtrl(self, value=str(current_w), min=1, max=1000)
        w_sizer.Add(self.width_ctrl, 0)
        sizer.Add(w_sizer, 0, wx.ALL, 5)

        # 高度输入行
        h_sizer = wx.BoxSizer(wx.HORIZONTAL)
        h_sizer.Add(wx.StaticText(self, label="高度:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
        self.height_ctrl = wx.SpinCtrl(self, value=str(current_h), min=1, max=1000)
        h_sizer.Add(self.height_ctrl, 0)
        sizer.Add(h_sizer, 0, wx.ALL, 5)

        btn_sizer = self.CreateButtonSizer(wx.OK | wx.CANCEL)
        sizer.Add(btn_sizer, 0, wx.ALL | wx.EXPAND, 10)
        # 设置对话框布局
        self.SetSizer(sizer)

    def get_size(self):
        """
        获取用户输入的新尺寸
        """
        return self.width_ctrl.GetValue(), self.height_ctrl.GetValue()


class TileInputDialog(wx.Dialog):
    """瓦片输入对话框"""
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
    """属性编辑对话框"""
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
    """地图属性编辑对话框"""
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


class ObjectDialog(wx.Dialog):
    """对象编辑对话框"""
    TILE_SIZE = 32  # 瓦片大小
    
    def __init__(self, parent, obj_data=None, is_edit=False, next_id=1, default_tile_x=0, default_tile_y=0):
        title = "编辑对象" if is_edit else "添加对象"
        super().__init__(parent, title=title)
        
        self.obj_data = obj_data if obj_data else {}
        self.is_edit = is_edit
        self.next_id = next_id
        
        # 计算默认瓦片坐标
        if obj_data and obj_data.get("x") is not None:
            default_tile_x = int(obj_data.get("x", 0)) // self.TILE_SIZE
            default_tile_y = int(obj_data.get("y", 0)) // self.TILE_SIZE
        
        sizer = wx.BoxSizer(wx.VERTICAL)
        
        # 基本信息
        info_sizer = wx.FlexGridSizer(rows=6, cols=2, hgap=5, vgap=5)
        
        info_sizer.Add(wx.StaticText(self, label="对象ID/名称："))
        self.name_input = wx.TextCtrl(self, value=self.obj_data.get("name", ""))
        info_sizer.Add(self.name_input, 1, wx.EXPAND)
        
        info_sizer.Add(wx.StaticText(self, label="对象类型："))
        self.type_input = wx.TextCtrl(self, value=self.obj_data.get("type", ""))
        info_sizer.Add(self.type_input, 1, wx.EXPAND)
        
        info_sizer.Add(wx.StaticText(self, label="X坐标："))
        self.tile_x_input = wx.SpinCtrl(self, value=str(default_tile_x), min=0, max=1000)
        info_sizer.Add(self.tile_x_input, 1, wx.EXPAND)
        
        info_sizer.Add(wx.StaticText(self, label="Y坐标："))
        self.tile_y_input = wx.SpinCtrl(self, value=str(default_tile_y), min=0, max=1000)
        info_sizer.Add(self.tile_y_input, 1, wx.EXPAND)
        
        info_sizer.Add(wx.StaticText(self, label="宽度(瓦片)："))
        self.tile_w_input = wx.SpinCtrl(self, value=str(int(obj_data.get("width", 32)) // self.TILE_SIZE if obj_data else 1), min=1, max=100)
        info_sizer.Add(self.tile_w_input, 1, wx.EXPAND)
        
        info_sizer.Add(wx.StaticText(self, label="高度(瓦片)："))
        self.tile_h_input = wx.SpinCtrl(self, value=str(int(obj_data.get("height", 32)) // self.TILE_SIZE if obj_data else 1), min=1, max=100)
        info_sizer.Add(self.tile_h_input, 1, wx.EXPAND)
        
        sizer.Add(info_sizer, 0, wx.EXPAND | wx.ALL, 10)
        
        # 属性编辑
        sizer.Add(wx.StaticText(self, label="自定义属性："), 0, wx.LEFT | wx.TOP, 10)
        
        self.prop_list = wx.ListBox(self, style=wx.LB_SINGLE, size=(-1, 80))
        self.properties = self.obj_data.get("properties", {}).copy()
        self.refresh_prop_list()
        sizer.Add(self.prop_list, 1, wx.EXPAND | wx.ALL, 5)
        
        prop_btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.btn_add_prop = wx.Button(self, label="添加属性")
        self.btn_del_prop = wx.Button(self, label="删除")
        prop_btn_sizer.Add(self.btn_add_prop, 1, wx.RIGHT, 5)
        prop_btn_sizer.Add(self.btn_del_prop, 1)
        sizer.Add(prop_btn_sizer, 0, wx.EXPAND | wx.ALL, 5)
        
        # 按钮
        btn_sizer = self.CreateButtonSizer(wx.OK | wx.CANCEL)
        sizer.Add(btn_sizer, 0, wx.EXPAND | wx.ALL, 10)
        
        self.SetSizer(sizer)
        self.SetSize((400, 450))
        
        self.Bind(wx.EVT_BUTTON, self.on_add_prop, self.btn_add_prop)
        self.Bind(wx.EVT_BUTTON, self.on_del_prop, self.btn_del_prop)
    
    def refresh_prop_list(self):
        self.prop_list.Clear()
        for name, value in self.properties.items():
            self.prop_list.Append(f"{name}={value}")
    
    def on_add_prop(self, event):
        dlg = wx.TextEntryDialog(self, "输入属性名和值（格式：name=value）", "添加属性", "")
        if dlg.ShowModal() == wx.ID_OK:
            text = dlg.GetValue()
            if "=" in text:
                name, value = text.split("=", 1)
                self.properties[name.strip()] = value.strip()
                self.refresh_prop_list()
        dlg.Destroy()
    
    def on_del_prop(self, event):
        sel = self.prop_list.GetSelection()
        if sel == wx.NOT_FOUND:
            wx.MessageBox("请先选择要删除的属性！", "提示", wx.OK | wx.ICON_WARNING)
            return
        text = self.prop_list.GetString(sel)
        name = text.split("=")[0]
        del self.properties[name]
        self.refresh_prop_list()
    
    def get_object_data(self):
        tile_x = self.tile_x_input.GetValue()
        tile_y = self.tile_y_input.GetValue()
        tile_w = self.tile_w_input.GetValue()
        tile_h = self.tile_h_input.GetValue()
        
        obj = {
            "id": self.obj_data.get("id", self.next_id),
            "name": self.name_input.GetValue().strip(),
            "type": self.type_input.GetValue().strip(),
            "x": tile_x * self.TILE_SIZE,
            "y": tile_y * self.TILE_SIZE,
            "width": tile_w * self.TILE_SIZE,
            "height": tile_h * self.TILE_SIZE,
            "properties": self.properties
        }
        return obj


class CustomTileDialog(wx.Frame):
    """编辑瓦片窗口"""
    def __init__(self, parent, tile_defs):
        super().__init__(parent, title="编辑瓦片", size=(800, 600))
        self.tile_data = copy.deepcopy(tile_defs)
        self.parent = parent
        self.selected_tile_id = None
        
        self.Bind(wx.EVT_SHOW, self.on_show)
        self.Bind(wx.EVT_CLOSE, self.on_close)
        
        panel = wx.Panel(self)
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        main_sizer.Add(wx.StaticText(panel, label="瓦片列表（ID: 名称） &T"), 0, wx.ALL, 5)
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
            
            # 追加属性信息
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
        
        dlg = TileInputDialog(self, self.selected_tile_id, tile_name, is_edit=True)
        if dlg.ShowModal() == wx.ID_OK:
            new_id = dlg.id_input.GetValue().strip()
            new_name = dlg.name_input.GetValue().strip()
            if new_id and new_name:
                old_data = self.tile_data.pop(self.selected_tile_id, {"name": "", "properties": {}})
                if isinstance(old_data, str):
                    old_data = {"name": old_data, "properties": {}}
                properties = old_data.get("properties", {})
                self.tile_data[new_id] = {"name": new_name, "properties": properties}
                self.refresh_list()
        dlg.Destroy()

    def on_add(self, event):
        max_id = max([int(k) for k in self.tile_data.keys()]) if self.tile_data else -1
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
            wx.MessageBox("请先选择要编辑属性的瓦片！", "提示", wx.OK | wx.ICON_WARNING)
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
                self.tile_data[self.selected_tile_id] = {"name": tile_data, "properties": new_properties}
            self.refresh_list()
        dlg.Destroy()

    def on_save(self, event):
        with open('./tile_definitions.json', 'w', encoding='utf-8') as f:
            json.dump(self.tile_data, f, ensure_ascii=False, indent=4)
        wx.MessageBox("保存成功！", "提示", wx.OK)
        self.notify_parent()
        self.Destroy()

    def on_close(self, event):
        result = wx.MessageBox("确定要退出吗？", "提示", wx.YES_NO | wx.ICON_QUESTION)
        if result == 8:
            return
        self.notify_parent()
        self.Destroy()
        
    def notify_parent(self):
        self.parent.enable_and_update(self.tile_data.copy())


class MapEditorFrame(wx.Frame):
    """地图编辑器主窗口类"""
    def __init__(self):
        """初始化"""
        # 使用样式移除系统菜单
        style = wx.DEFAULT_FRAME_STYLE & ~wx.RESIZE_BORDER & ~wx.MAXIMIZE_BOX
        super().__init__(None, title="地图编辑器 V1.0", size=(1366, 768), style=style)
        
        # 使用Windows API移除系统菜单
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
        
        # 地图参数
        self.width = 200
        self.height = 200
        self.current_file = None  # 当前打开的文件名
        # 地图数据
        self.map_data = [[0 for _ in range(self.width)] for _ in range(self.height)]
        self.cursor_x = 0         # 当前光标所在列
        self.cursor_y = 0         # 当前光标所在行

        # 加载瓦片字典 JSON
        global TILE_DEFINITIONS
        TILE_DEFINITIONS = self.load_tiled_data()
        # 复制默认瓦片类型定义
        self.tile_definitions = TILE_DEFINITIONS.copy()
        
        # 区域选择相关变量
        self.selection_start = None  # 选区起始坐标 (x, y)
        self.selection_end = None    # 选区结束坐标 (x, y)

        # 对象层
        self.object_layers = [{
            "type": "objectgroup",
            "objects": []
        }]
        self.next_object_id = 1  # 下一个对象ID
        self.selected_object = None  # 当前选中的对象
        self.map_properties = {"name": "Ground", "bgm": ""}  # 地图属性

        # 初始化UI和菜单
        self.init_ui()
        self.create_menu()
        # 更新状态栏信息
        self.update_status()
        TTS.init_engine()
        TTS.speak('编辑器启动')


    def load_tiled_data(self):
        """
        加载瓦片配置
        """
        config_file = './tile_definitions.json'
        # 默认配置
        default_config = {
            "0": {"name": "空地", "properties": {}},
            "1": {"name": "墙壁", "properties": {}}
        }

        
        try:
            if not os.path.exists(config_file):
                print(f"配置文件不存在，创建新文件: {config_file}")
                with open(config_file, 'w', encoding='utf-8') as f:
                    json.dump(default_config, f, ensure_ascii=False, indent=4)
                print("已创建默认配置文件")
                return default_config
            
            # 文件存在，读取内容
            with open(config_file, 'r', encoding='utf-8') as f:
                content = f.read()
                
                # 检查文件是否为空
                if not content.strip():
                    print("配置文件为空，创建默认配置")
                    with open(config_file, 'w', encoding='utf-8') as f_write:
                        json.dump(default_config, f_write, ensure_ascii=False, indent=4)
                    print(" 已填充默认配置")
                    return default_config
                
                # 解析JSON内容
                data = json.loads(content)
                
                # 验证配置结构
                if not isinstance(data, dict):
                    print("配置文件格式错误，重置为默认配置")
                    return default_config
                
                # 转换为新格式
                result = {}
                for k, v in data.items():
                    if isinstance(v, str):
                        # 旧格式：{"0": "空地"} -> {"0": {"name": "空地", "properties": {}}}
                        result[str(k)] = {"name": v, "properties": {}}
                    else:
                        # 新格式：{"0": {"name": "空地", "properties": {}}}
                        result[str(k)] = v
                
                return result
                
        except json.JSONDecodeError as e:
            print(f"JSON解析错误: {e}")
            return default_config
        except Exception as e:
            print(f"加载配置文件时发生错误: {e}")
            return default_config


    def init_ui(self):
        """初始化用户界面"""
        # 创建主面板
        panel = wx.Panel(self)
        # 创建垂直布局管理器
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        # 状态栏标签
        self.status_label = wx.StaticText(panel, label="")
        main_sizer.Add(self.status_label, 0, wx.ALL, 5)

        # 创建网格控件（用于显示地图）
        self.grid = gridlib.Grid(panel)
        self.grid.CreateGrid(self.height, self.width)
        
        self.grid.EnableEditing(False)  # 禁用网格单元格直接编辑
        
        self.grid.SetDefaultCellAlignment(wx.ALIGN_CENTER, wx.ALIGN_CENTER)  # 设置单元格内容居中对齐
        
        self.grid.SetRowLabelSize(40)  # 设置行标签宽度
        
        self.grid.SetColLabelSize(30)  # 设置列标签高度
        
        # 绑定事件
        self.grid.Bind(wx.EVT_KEY_DOWN, self.on_key_down)
        self.grid.Bind(gridlib.EVT_GRID_SELECT_CELL, self.on_grid_select)

        # 将网格添加到布局
        main_sizer.Add(self.grid, 1, wx.EXPAND | wx.ALL, 5)
        # 设置面板布局
        panel.SetSizer(main_sizer)
        # 设置网格为焦点控件
        self.grid.SetFocus()


    def create_menu(self):
        """创建菜单栏"""
        menubar = wx.MenuBar()
        
        # 文件菜单
        file_menu = wx.Menu()
        open_item = file_menu.Append(wx.ID_OPEN, "打开...\tCtrl+O")
        close_item = file_menu.Append(wx.ID_ANY, "关闭当前文件\t&L")
        save_item = file_menu.Append(wx.ID_SAVE, "保存...\tCtrl+S")
        resize_item = file_menu.Append(wx.ID_ANY, "调整地图尺寸...\t&R")
        custom_tile_item = file_menu.Append(wx.ID_ANY, "编辑瓦片...\t&C")
        map_prop_item = file_menu.Append(wx.ID_ANY, "编辑地图属性...\t&M")
        # 添加分隔符
        file_menu.AppendSeparator()
        exit_item = file_menu.Append(wx.ID_EXIT, "退出\t&X")
        
        # 编辑菜单
        edit_menu = wx.Menu()
        goto_item = edit_menu.Append(wx.ID_ANY, "跳转单元格...\tCtrl+G")
        edit_menu.AppendSeparator()
        clear_item = edit_menu.Append(wx.ID_ANY, "清除选区\tEsc")
        delete_item = edit_menu.Append(wx.ID_ANY, "清除单元格\tBackspace")
        select_tile_item = edit_menu.Append(wx.ID_ANY, "选择瓦片\tEnter")
        selection_start_item = edit_menu.Append(wx.ID_ANY, "选区开始点\tShift+Enter")
        selection_end_item = edit_menu.Append(wx.ID_ANY, "选区结束点\tCtrl+Enter")
        fill_item = edit_menu.Append(wx.ID_ANY, "填充选区\tCtrl+F")
        edit_menu.AppendSeparator()
        copy_item = edit_menu.Append(wx.ID_ANY, "复制\tCtrl+C")
        paste_item = edit_menu.Append(wx.ID_ANY, "粘贴\tCtrl+V")
        
        # 对象菜单
        object_menu = wx.Menu()
        add_object_item = object_menu.Append(wx.ID_ANY, "添加对象...\tCtrl+Shift+A")
        edit_object_item = object_menu.Append(wx.ID_ANY, "编辑对象...")
        delete_object_item = object_menu.Append(wx.ID_ANY, "删除对象...\tDelete")
        object_menu.AppendSeparator()
        copy_object_item = object_menu.Append(wx.ID_ANY, "复制对象\tCtrl+Shift+C")
        paste_object_item = object_menu.Append(wx.ID_ANY, "粘贴对象\tCtrl+Shift+V")
        object_menu.AppendSeparator()
        clear_all_objects_item = object_menu.Append(wx.ID_ANY, "清除所有对象")
        
        # 将菜单添加到菜单栏
        menubar.Append(file_menu, "文件 &F")
        menubar.Append(edit_menu, "编辑 &E")
        menubar.Append(object_menu, "对象 &O")
        # 设置窗口菜单栏
        self.SetMenuBar(menubar)

        # 绑定菜单项事件
        self.Bind(wx.EVT_MENU, self.on_open, open_item)             # 打开事件
        self.Bind(wx.EVT_MENU, self.on_save, save_item)          # 保存事件
        self.Bind(wx.EVT_MENU, self.on_resize, resize_item)      # 调整尺寸事件
        self.Bind(wx.EVT_MENU, self.on_custom_tiles, custom_tile_item)  # 自定义瓦片事件
        self.Bind(wx.EVT_MENU, self.on_edit_map_properties, map_prop_item)  # 地图属性事件
        self.Bind(wx.EVT_MENU, self.on_close_file, close_item)    # 关闭文件事件
        self.Bind(wx.EVT_MENU, self.on_exit, exit_item)          # 退出事件
        # 绑定编辑菜单事件
        self.Bind(wx.EVT_MENU, self.clear_selected, clear_item)
        self.Bind(wx.EVT_MENU, self.delete_selection, delete_item)
        self.Bind(wx.EVT_MENU, self.on_set_tile, select_tile_item)
        self.Bind(wx.EVT_MENU, self.on_selection_start, selection_start_item)
        self.Bind(wx.EVT_MENU, self.on_selection_end, selection_end_item)
        self.Bind(wx.EVT_MENU, self.on_fill_selection, fill_item)
        self.Bind(wx.EVT_MENU, self.copy_selection, copy_item)
        self.Bind(wx.EVT_MENU, self.paste_clipboard, paste_item)
        self.Bind(wx.EVT_MENU, self.on_goto_cell, goto_item)
        # 绑定对象菜单事件
        self.Bind(wx.EVT_MENU, self.on_add_object, add_object_item)
        self.Bind(wx.EVT_MENU, self.on_edit_object, edit_object_item)
        self.Bind(wx.EVT_MENU, self.on_delete_object, delete_object_item)
        self.Bind(wx.EVT_MENU, self.copy_object, copy_object_item)
        self.Bind(wx.EVT_MENU, self.paste_object, paste_object_item)
        self.Bind(wx.EVT_MENU, self.on_clear_all_objects, clear_all_objects_item)
        # 绑定关闭事件，点击叉号最小化
        self.Bind(wx.EVT_CLOSE, self.on_minimize)
        # 绑定全局键盘钩子（处理快捷键）
        self.Bind(wx.EVT_CHAR_HOOK, self.on_global_key)


    def on_global_key(self, event):
        """
        全局键盘事件处理（快捷键）
        :param event: 键盘事件对象
        """
        key = event.GetKeyCode()
        # 处理 Ctrl+Shift 组合键（优先检查）
        if event.ControlDown() and event.ShiftDown():
            if key == ord('A'):          # Ctrl+Shift+A：添加对象
                self.on_add_object(None)
                return
            elif key == ord('C'):        # Ctrl+Shift+C：复制对象
                self.copy_object(None)
                return
            elif key == ord('V'):        # Ctrl+Shift+V：粘贴对象
                self.paste_object(None)
                return
        # 处理Ctrl组合键
        if event.ControlDown():
            if key == ord('S'):          # Ctrl+S：保存
                self.on_save(None)
                return
            elif key == ord('R'):        # Ctrl+R：调整尺寸
                self.on_resize(None)
                return
            elif key == ord('C'):        # Ctrl+C：复制选区
                self.copy_selection(None)
                return
            elif key == ord('V'):        # Ctrl+V：粘贴选区
                self.paste_clipboard(None)
                return
            elif key == ord('F'):        # Ctrl+F：填充选区
                self.on_fill_selection(None)
                return
        # 处理 Delete 键：删除对象
        elif key == wx.WXK_DELETE:
            obj = self.find_object_at(self.cursor_x, self.cursor_y)
            if obj:
                self.on_delete_object(None)
            return
        # 处理退格键：清除瓦片
        elif key == wx.WXK_BACK:
            self.delete_selection(None)
            return
        # 未处理的按键继续传递
        event.Skip()

    def is_map_modified(self):
        """检查地图是否已修改"""
        # 检查尺寸是否改变
        if self.width != 200 or self.height != 200:
            return True
        # 检查瓦片数据是否不全为0
        for row in self.map_data:
            for cell in row:
                if cell != 0:
                    return True
        # 检查对象层是否有对象
        if self.object_layers and self.object_layers[0].get("objects"):
            return True
        return False

    def on_minimize(self, event):
        """点击关闭按钮最小化"""
        self.Iconize()

    def on_close_file(self, event):
        """关闭当前文件"""
        if self.is_map_modified():
            result = wx.MessageBox("地图有未保存的更改，是否关闭？", "提示", wx.YES_NO | wx.ICON_QUESTION)
            if result == 2:
                self.reset_to_default_map()
            elif result == 8:
                return


    def reset_to_default_map(self):
        """重置地图为默认大小"""
        self.width = 200
        self.height = 200
        self.map_data = [[0 for _ in range(self.width)] for _ in range(self.height)]
        self.cursor_x = 0
        self.cursor_y = 0
        self.selection_start = None
        self.selection_end = None
        self.current_file = None  # 清空当前文件名
        self.object_layers = [{
            "type": "objectgroup",
            "objects": []
        }]
        self.next_object_id = 1
        self.map_properties = {"name": "Ground", "bgm": ""}
        # 重建网格
        self.rebuild_grid()
        self.update_status()
        self.update_title()
        TTS.speak("地图已重置")

    def on_exit(self, event):
        """退出程序"""
        if self.is_map_modified():
            wx.MessageBox("存在为保存的修改，请先保存再退出！", "提示", wx.OK | wx.ICON_WARNING)
            return
        self.Destroy()

    def on_save_file(self):
        """保存地图到文件（内部方法）"""
        with wx.FileDialog(
            self, "保存地图", wildcard="Tiled JSON (*.json)|*.json",
            style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT
        ) as dlg:
            if dlg.ShowModal() == wx.ID_OK:
                self.save_to_tiled_json(dlg.GetPath())


    def on_resize(self, event):
        """
        调整地图尺寸事件处理
        :param event: 事件对象
        """
        # 创建尺寸调整对话框
        dlg = ResizeDialog(self, self.width, self.height)
        # 确定
        if dlg.ShowModal() == wx.ID_OK:
            new_w, new_h = dlg.get_size()
            if new_w <= 0 or new_h <= 0:
                wx.MessageBox("尺寸必须大于0", "错误", wx.OK | wx.ICON_ERROR)
                return

            # 保存旧地图数据
            old_data = self.map_data
            # 更新地图尺寸
            self.width, self.height = new_w, new_h
            # 初始化新地图数据（默认值0）
            self.map_data = [[0 for _ in range(new_w)] for _ in range(new_h)]

            # 将旧数据复制到新地图（仅复制重叠区域）
            for y in range(min(len(old_data), new_h)):
                for x in range(min(len(old_data[0]), new_w)):
                    self.map_data[y][x] = old_data[y][x]

            # 刷新网格控件
            self.grid.ClearGrid()                          # 清空现有内容
            self.grid.DeleteRows(0, self.grid.GetNumberRows())  # 删除所有行
            self.grid.DeleteCols(0, self.grid.GetNumberCols())  # 删除所有列
            self.grid.AppendRows(new_h)                    # 添加新行
            self.grid.AppendCols(new_w)                    # 添加新列

            # 修正光标位置（防止超出新边界）
            self.cursor_x = min(self.cursor_x, new_w - 1)
            self.cursor_y = min(self.cursor_y, new_h - 1)
            # 选中光标所在单元格
            self.grid.SelectBlock(self.cursor_y, self.cursor_x, self.cursor_y, self.cursor_x)
            # 更新状态栏
            self.update_status()
        # 销毁对话框
        dlg.Destroy()


    def on_custom_tiles(self, event):
        """
        编辑瓦片事件处理
        使用子窗口模式
        """
        self.Enable(False)
        self.Unbind(wx.EVT_CHAR_HOOK)
        self.tile_window = CustomTileDialog(self, self.tile_definitions)
        self.tile_window.Show()

    def on_edit_map_properties(self, event):
        """编辑地图属性"""
        dlg = MapPropertiesDialog(self, self.map_properties)
        if dlg.ShowModal() == wx.ID_OK:
            self.map_properties = dlg.get_properties()
            TTS.speak("地图属性已更新")
        dlg.Destroy()

    def enable_and_update(self, tile_data):
        """
        子窗口关闭后更新数据并重新启用主窗口
        """
        global TILE_DEFINITIONS
        TILE_DEFINITIONS = tile_data
        self.tile_definitions = tile_data.copy()
        self.Enable(True)
        self.Bind(wx.EVT_CHAR_HOOK, self.on_global_key)
        self.Raise()


    def update_status(self):
        """更新状态栏信息（光标位置、瓦片信息、选区、对象信息）"""
        # 获取当前光标位置的瓦片ID
        tile_id = str(self.map_data[self.cursor_y][self.cursor_x])
        # 获取瓦片名称
        tile_data = self.tile_definitions.get(tile_id)
        if tile_data:
            if isinstance(tile_data, dict):
                tile_name = tile_data.get("name", f"未知({tile_id})")
            else:
                tile_name = tile_data
        else:
            tile_name = f"未知({tile_id})"
        
        # 检查是否有对象
        obj = self.find_object_at(self.cursor_x, self.cursor_y)
        obj_info = ""
        obj_tts = ""
        if obj:
            obj_name = obj.get("name", "")
            obj_type = obj.get("type", "")
            obj_id = obj.get("id", "")
            props = obj.get("properties", {})
            prop_str = ""
            if props:
                prop_str = " " + " ".join([f"{k}={v}" for k, v in props.items()])
            obj_info = f"[{obj_id}:{obj_name}:{obj_type}]{prop_str}"
            obj_tts = f"[{obj_id}:{obj_name}:{obj_type}]"
        
        # 基础坐标信息
        coord_info = f"({self.cursor_x}； {self.cursor_y})"
        # 有选区时添加选区信息
        if self.selection_start and self.selection_end:
            x1, y1 = self.selection_start
            x2, y2 = self.selection_end
            coord_info += f" 选区: ({x1},{y1}) 到 ({x2},{y2})"
        
        # 设置状态栏文本：坐标 ； 对象信息 ； 瓦片名称
        if obj_info:
            status_text = f"{coord_info} ； {obj_info} ； {tile_name}"
        else:
            status_text = f"{coord_info} ； {tile_name}"
        self.status_label.SetLabel(status_text)
        
        # 只在光标移动时播报，不在编辑对象时播报
        if not hasattr(self, '_silent_status'):
            TTS.cancel()
            if obj_tts:
                TTS.speak(f"{obj_tts} {tile_name} {coord_info}")
            else:
                TTS.speak(f"{tile_name} {coord_info}")
        # 刷新状态栏显示
        self.status_label.Refresh()
        # 强制刷新UI
        wx.Yield() 


    def on_goto_cell(self, event):
        """跳转单元格"""
        dlg = wx.TextEntryDialog(self, "输入目标坐标（格式：x,y）", "跳转单元格", "")
        if dlg.ShowModal() == wx.ID_OK:
            try:
                text = dlg.GetValue().strip()
                x, y = map(int, text.split(','))
                if 0 <= x < self.width and 0 <= y < self.height:
                    self.cursor_x = x
                    self.cursor_y = y
                    self.grid.SelectBlock(y, x, y, x)
                    self.grid.MakeCellVisible(y, x)
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
        """
        网格键盘按键事件处理
        :param event: 键盘事件对象
        """
        key = event.GetKeyCode()
        modifiers = event.GetModifiers()
        moved = False  # 标记是否移动了光标

        # 方向键移动光标
        if key in [wx.WXK_LEFT, wx.WXK_RIGHT, wx.WXK_UP, wx.WXK_DOWN]:
            old_x, old_y = self.cursor_x, self.cursor_y
            if key == wx.WXK_LEFT and self.cursor_x > 0:          # 左方向键
                self.cursor_x -= 1
                moved = True
            elif key == wx.WXK_RIGHT and self.cursor_x < self.width - 1:  # 右方向键
                self.cursor_x += 1
                moved = True
            elif key == wx.WXK_UP and self.cursor_y > 0:          # 上方向键
                self.cursor_y -= 1
                moved = True
            elif key == wx.WXK_DOWN and self.cursor_y < self.height - 1:  # 下方向键
                self.cursor_y += 1
                moved = True
        if key == wx.WXK_ESCAPE:
            self.clear_selected(None)
            return

        # Ctrl+G 跳转到指定单元格
        elif key == ord('G') and modifiers == wx.MOD_CONTROL:
            dlg = wx.TextEntryDialog(self, "输入目标坐标（格式：x,y）", "跳转单元格", "")
            if dlg.ShowModal() == wx.ID_OK:
                try:
                    text = dlg.GetValue().strip()
                    x, y = map(int, text.split(','))
                    if 0 <= x < self.width and 0 <= y < self.height:
                        self.cursor_x = x
                        self.cursor_y = y
                        self.grid.SelectBlock(y, x, y, x)
                        self.grid.MakeCellVisible(y, x)
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

        # 回车键处理（选区/设置瓦片）
        elif key == wx.WXK_RETURN:
            if modifiers == wx.MOD_SHIFT:                         # Shift+Enter：设置选区起始点
                self.selection_start = (self.cursor_x, self.cursor_y)
                self.update_status()
                TTS.cancel()
                TTS.speak('选区开始')
                return
            elif modifiers == wx.MOD_CONTROL:                     # Ctrl+Enter：设置选区结束点
                self.selection_end = (self.cursor_x, self.cursor_y)
                self.update_status()
                TTS.cancel()
                TTS.speak(f'已选: {self.selection_start} 到 {self.selection_end}')
                return

            else:                                                 # 设置瓦片或编辑对象
                obj = self.find_object_at(self.cursor_x, self.cursor_y)
                if obj:
                    self.on_edit_object(None)
                else:
                    self.on_set_tile(None)
                return
        # 未处理的按键继续传递
        event.Skip()

    def on_selection_start(self, event):
        """设置选区开始点"""
        self.selection_start = (self.cursor_x, self.cursor_y)
        self.update_status()
        TTS.cancel()
        TTS.speak('选区开始')

    def on_selection_end(self, event):
        """设置选区结束点"""
        self.selection_end = (self.cursor_x, self.cursor_y)
        self.update_status()
        TTS.cancel()
        TTS.speak(f'已选: {self.selection_start} 到 {self.selection_end}')


    def on_grid_select(self, event):
        """
        网格单元格选中事件处理
        :param event: 网格选中事件对象
        """
        # 更新光标坐标为选中的单元格坐标
        self.cursor_y = event.GetRow()
        self.cursor_x = event.GetCol()
        # 更新状态栏
        self.update_status()
        # 事件继续传递
        event.Skip()


    def on_set_tile(self, event):
        """
        设置当前单元格瓦片类型
        :param event: 事件对象
        """
        # 创建瓦片选择对话框
        dlg = TileSelectionDialog(self, self.tile_definitions)
        if dlg.ShowModal() == wx.ID_OK:
            # 获取选中的瓦片ID
            tile_id = dlg.GetSelectedTileId()
            # 更新地图数据
            self.map_data[self.cursor_y][self.cursor_x] = tile_id
            # 更新网格显示
            self.grid.SetCellValue(self.cursor_y, self.cursor_x, str(tile_id))
            # 更新状态栏
            self.update_status()
        # 销毁对话框
        dlg.Destroy()


    # 区域操作
    def get_selection_bounds(self):
        """
        获取选区的边界坐标
        :return: (left, top, right, bottom) 或 None（无选区）
        """
        if not self.selection_start or not self.selection_end:
            return None
        x1, y1 = self.selection_start
        x2, y2 = self.selection_end
        # 计算选区的最小/最大坐标（确保left<=right，top<=bottom）
        left = min(x1, x2)
        right = max(x1, x2)
        top = min(y1, y2)
        bottom = max(y1, y2)
        return left, top, right, bottom


    def copy_selection(self, event):
        """复制选中区域"""
        # 初始化剪贴板
        global CLIPBOARD
        CLIPBOARD = []
        # 获取选区边界
        bounds = self.get_selection_bounds()
        if not bounds:
            # 无选区时
            CLIPBOARD.append([self.map_data[self.cursor_y][self.cursor_x]])
            self.selection_start = None
            self.selection_end = None
            self.update_status()
            TTS.cancel()
            TTS.speak('复制')
            return
        left, top, right, bottom = bounds

        # 复制选区数据
        for y in range(top, bottom + 1):
            row = []
            for x in range(left, right + 1):
                row.append(self.map_data[y][x])
            CLIPBOARD.append(row)

        # 更新状态栏
        self.selection_start = None
        self.selection_end = None
        self.update_status()
        TTS.cancel()
        TTS.speak('复制选区')


    def delete_selection(self, event):
        """清空选中单元格/区域"""
        # 获取选区边界
        bounds = self.get_selection_bounds()
        if not bounds:
            # 无选区时清空当前单元格
            self.map_data[self.cursor_y][self.cursor_x] = 0
            self.grid.SetCellValue(self.cursor_y, self.cursor_x, "0")
        else:
            # 有选区时清空整个选区
            left, top, right, bottom = bounds
            for y in range(top, bottom + 1):
                for x in range(left, right + 1):
                    self.map_data[y][x] = 0
                    self.grid.SetCellValue(y, x, "0")
        # 更新状态栏
        self.update_status()
        self.clear_selected(None)
        TTS.cancel()
        TTS.speak('清除')


    def on_fill_selection(self, event):
        """
        填充选区 - 调出瓦片选择对话框进行填充
        :param event: 事件对象
        """
        dlg = TileSelectionDialog(self, self.tile_definitions)
        if dlg.ShowModal() == wx.ID_OK:
            tile_id = dlg.GetSelectedTileId()
            self.fill_selection(tile_id)
            self.Refresh()
        dlg.Destroy()


    def fill_selection(self, tile_id):
        """
        执行填充操作
        :param tile_id: 瓦片ID
        """
        bounds = self.get_selection_bounds()
        if bounds:
            left, top, right, bottom = bounds
            for y in range(top, bottom + 1):
                for x in range(left, right + 1):
                    self.map_data[y][x] = tile_id
                    self.grid.SetCellValue(y, x, str(tile_id))
        else:
            self.map_data[self.cursor_y][self.cursor_x] = tile_id
            self.grid.SetCellValue(self.cursor_y, self.cursor_x, str(tile_id))
        self.update_status()


    def clear_selected(self, event):
        """ 清除选区 """
        if not self.selection_start and not self.selection_end:
            TTS.cancel()
            TTS.speak('没有选区')
            return

        self.selection_start = None
        self.selection_end = None
        self.update_status()
        TTS.cancel()
        TTS.speak('已清除选区')


    def paste_clipboard(self, event):
        """剪贴板数据粘贴"""
        global CLIPBOARD
        # 剪贴板为空时提示
        if CLIPBOARD is None:
            TTS.cancel()
            TTS.speak('剪贴板为空')
            return
        # 获取剪贴板数据的尺寸
        paste_h = len(CLIPBOARD)
        paste_w = len(CLIPBOARD[0]) if paste_h > 0 else 0

        # 检查粘贴区域是否超出地图边界
        if self.cursor_y + paste_h > self.height or self.cursor_x + paste_w > self.width:
            wx.MessageBox("粘贴区域超出地图边界", "错误", wx.OK | wx.ICON_ERROR)
            return

        # 粘贴数据到地图
        for dy, row in enumerate(CLIPBOARD):
            for dx, tile_id in enumerate(row):
                y = self.cursor_y + dy
                x = self.cursor_x + dx
                self.map_data[y][x] = tile_id
                self.grid.SetCellValue(y, x, str(tile_id))
        # 更新状态栏
        self.update_status()
        self.clear_selected(None)
        TTS.cancel()
        TTS.speak('粘贴')


    OBJECT_CLIPBOARD = None  # 对象剪贴板


    def copy_object(self, event):
        """复制对象"""
        obj = self.find_object_at(self.cursor_x, self.cursor_y)
        if not obj:
            wx.MessageBox("当前光标位置没有对象！", "提示", wx.OK | wx.ICON_WARNING)
            return
        
        OBJECT_CLIPBOARD = copy.deepcopy(obj)
        self.OBJECT_CLIPBOARD = OBJECT_CLIPBOARD
        TTS.cancel()
        TTS.speak(f"已复制对象：{obj.get('name', '')}")


    def paste_object(self, event):
        """粘贴对象"""
        if not hasattr(self, 'OBJECT_CLIPBOARD') or self.OBJECT_CLIPBOARD is None:
            wx.MessageBox("对象剪贴板为空！", "提示", wx.OK | wx.ICON_WARNING)
            return
        
        new_obj = copy.deepcopy(self.OBJECT_CLIPBOARD)
        new_obj["id"] = self.next_object_id
        self.next_object_id += 1
        
        tilewidth = 32
        tileheight = 32
        new_obj["x"] = self.cursor_x * tilewidth
        new_obj["y"] = self.cursor_y * tileheight
        
        self.object_layers[0]["objects"].append(new_obj)
        self.refresh_current_cell()
        self.update_status()
        TTS.cancel()
        TTS.speak(f"已粘贴对象：{new_obj.get('name', '')}")


    def find_object_at(self, tile_x, tile_y):
        """查找指定瓦片坐标处的对象"""
        for layer in self.object_layers:
            for obj in layer.get("objects", []):
                # 对象存储的是像素坐标，转换为瓦片坐标进行比较
                obj_tile_x = obj.get("x", 0) // 32
                obj_tile_y = obj.get("y", 0) // 32
                obj_tile_w = obj.get("width", 32) // 32
                obj_tile_h = obj.get("height", 32) // 32
                
                if obj_tile_x <= tile_x < obj_tile_x + obj_tile_w and obj_tile_y <= tile_y < obj_tile_y + obj_tile_h:
                    return obj
        return None

    def refresh_current_cell(self):
        """刷新当前单元格显示"""
        tile_value = str(self.map_data[self.cursor_y][self.cursor_x])
        obj_text = self.get_object_display_text(self.cursor_x, self.cursor_y)
        if obj_text:
            display_text = f"{tile_value} {obj_text}"
        else:
            display_text = tile_value
        self.grid.SetCellValue(self.cursor_y, self.cursor_x, display_text)


    def get_object_display_text(self, tile_x, tile_y):
        """获取指定坐标处对象的显示文本"""
        obj = self.find_object_at(tile_x, tile_y)
        if obj:
            name = obj.get("name", "")
            obj_type = obj.get("type", "")
            return f"[{name}:{obj_type}]"
        return None


    def on_add_object(self, event):
        """添加对象"""
        dlg = ObjectDialog(self, is_edit=False, next_id=self.next_object_id, 
                          default_tile_x=self.cursor_x, default_tile_y=self.cursor_y)
        if dlg.ShowModal() == wx.ID_OK:
            obj_data = dlg.get_object_data()
            obj_data["id"] = self.next_object_id
            self.next_object_id += 1
            
            self.object_layers[0]["objects"].append(obj_data)
            self.refresh_current_cell()
            self.update_status()
            TTS.cancel()
            TTS.speak(f"已添加对象：{obj_data.get('name', '')}")
        dlg.Destroy()


    def on_edit_object(self, event):
        """编辑对象"""
        obj = self.find_object_at(self.cursor_x, self.cursor_y)
        if not obj:
            wx.MessageBox("当前光标位置没有对象！", "提示", wx.OK | wx.ICON_WARNING)
            return
        
        self._silent_status = True
        dlg = ObjectDialog(self, obj_data=obj, is_edit=True, next_id=self.next_object_id)
        if dlg.ShowModal() == wx.ID_OK:
            new_obj_data = dlg.get_object_data()
            new_obj_data["id"] = obj.get("id")
            
            for i, existing_obj in enumerate(self.object_layers[0]["objects"]):
                if existing_obj.get("id") == obj.get("id"):
                    self.object_layers[0]["objects"][i] = new_obj_data
                    break
            
            self.refresh_current_cell()
            del self._silent_status
            self.update_status()
            TTS.speak(f"已编辑对象：{new_obj_data.get('name', '')}")
        else:
            del self._silent_status
        dlg.Destroy()


    def on_delete_object(self, event):
        """删除对象"""
        obj = self.find_object_at(self.cursor_x, self.cursor_y)
        if not obj:
            wx.MessageBox("当前光标位置没有对象！", "提示", wx.OK | wx.ICON_WARNING)
            return
        
        result = wx.MessageBox(f"确定要删除对象 \"{obj.get('name', '')}\" 吗？", "确认", wx.YES_NO | wx.ICON_QUESTION)
        if result == 2:  # wx.MessageBox 返回 2 表示"是"
            self.object_layers[0]["objects"].remove(obj)
            self.refresh_current_cell()
            self.update_status()
            TTS.speak(f"已删除对象")


    def on_clear_all_objects(self, event):
        """清除所有对象"""
        result = wx.MessageBox("确定要清除所有对象吗？", "确认", wx.YES_NO | wx.ICON_QUESTION)
        if result == 2:  # wx.MessageBox 返回 2 表示"是"
            self.object_layers[0]["objects"] = []
            self.rebuild_grid()
            self.update_status()
            TTS.speak("已清除所有对象")


    def on_open(self, event):
        """
        打开地图文件
        :param event: 事件对象
        """
        with wx.FileDialog(
            self, "打开地图", wildcard="Tiled JSON (*.json)|*.json",
            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST
        ) as dlg:
            if dlg.ShowModal() == wx.ID_OK:
                filepath = dlg.GetPath()
                self.current_file = filepath
                self.load_from_tiled_json(filepath)
                self.update_title()


    def update_title(self):
        """更新窗口标题"""
        if self.current_file:
            
            filename = os.path.basename(self.current_file)
            self.SetTitle(f"{filename} - 地图编辑器 V1.0")
        else:
            self.SetTitle("地图编辑器 V1.0")


    def load_from_tiled_json(self, filepath):
        """
        从Tiled JSON文件加载地图数据
        """
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 获取地图尺寸
            new_width = data.get('width', 0)
            new_height = data.get('height', 0)
            
            if new_width == 0 or new_height == 0:
                wx.MessageBox("无效的地图尺寸！", "错误", wx.OK | wx.ICON_ERROR)
                return
            
            # 获取图层数据
            layers = data.get('layers', [])
            if not layers:
                wx.MessageBox("没有找到图层数据！", "错误", wx.OK | wx.ICON_ERROR)
                return
            
            # 重置对象层
            self.object_layers = []
            self.next_object_id = 1
            
            # 遍历所有图层
            for layer in layers:
                layer_type = layer.get('type', '')
                if layer_type == 'tilelayer':
                    # 瓦片层
                    layer_data = layer.get('data', [])
                    if not layer_data:
                        wx.MessageBox("没有找到瓦片数据！", "错误", wx.OK | wx.ICON_ERROR)
                        return
                    
                    # 将一维数组转换为二维数组（行优先）
                    self.map_data = []
                    for y in range(new_height):
                        row = []
                        for x in range(new_width):
                            idx = y * new_width + x
                            if idx < len(layer_data):
                                row.append(layer_data[idx])
                            else:
                                row.append(0)
                        self.map_data.append(row)
                        
                elif layer_type == 'objectgroup':
                    # 对象层
                    objects = layer.get('objects', [])
                    # 更新最大对象ID
                    for obj in objects:
                        obj_id = obj.get('id', 0)
                        if obj_id >= self.next_object_id:
                            self.next_object_id = obj_id + 1
                    self.object_layers.append(layer)
            
            # 如果没有对象层，创建默认的
            if not self.object_layers:
                self.object_layers = [{
                    "type": "objectgroup",
                    "objects": []
                }]
            
            # 读取地图属性
            self.map_properties = data.get('map_properties', {"name": "Ground", "bgm": ""})
            
            # 更新地图尺寸
            self.width = new_width
            self.height = new_height
            
            # 重建网格
            self.rebuild_grid()
            
            # 更新状态栏
            self.update_status()
            
            wx.MessageBox(f"成功加载地图：{new_width}x{new_height}", "提示", wx.OK)
            TTS.speak(f"已加载地图，宽度{new_width}，高度{new_height}")
            
        except Exception as e:
            wx.MessageBox(f"加载失败：{str(e)}", "错误", wx.OK | wx.ICON_ERROR)


    def rebuild_grid(self):
        """重建网格控件"""
        # 清空现有内容
        self.grid.ClearGrid()
        # 删除所有行和列
        self.grid.DeleteRows(0, self.grid.GetNumberRows())
        self.grid.DeleteCols(0, self.grid.GetNumberCols())
        # 添加新的行和列
        self.grid.AppendRows(self.height)
        self.grid.AppendCols(self.width)
        
        # 填充数据
        for y in range(self.height):
            for x in range(self.width):
                tile_value = str(self.map_data[y][x])
                obj_text = self.get_object_display_text(x, y)
                if obj_text:
                    display_text = f"{tile_value} {obj_text}"
                else:
                    display_text = tile_value
                self.grid.SetCellValue(y, x, display_text)
        
        # 重置光标位置（仅首次加载时）
        # 注意：这里不再强制重置为(0,0)，以保持添加/编辑对象后光标位置不变
        # 如果需要首次加载重置，请在调用处处理
        self.selection_start = None
        self.selection_end = None
        self.grid.SetGridCursor(self.cursor_y, self.cursor_x)
        self.grid.MakeCellVisible(self.cursor_y, self.cursor_x)


    def on_save(self, event):
        """
        保存地图
        :param event: 事件对象
        """
        self.on_save_file()


    def save_to_tiled_json(self, filepath):
        """
        将地图数据保存为Tiled编辑器兼容的JSON格式
        """
        

        data = []
        for y in range(self.height):
            for x in range(self.width):
                data.append(self.map_data[y][x])

        tiled_json = {
            "width": self.width,
            "height": self.height,
            "layers": [{
                "data": data,
                "width": self.width,
                "height": self.height,
                "opacity": 1,
                "type": "tilelayer",
                "visible": True
            }] + self.object_layers,
            "map_properties": self.map_properties,
            "tilewidth": 32,
            "tileheight": 32,
            "orientation": "orthogonal",
            "infinite": False,
            "renderorder": "right-down",
            "version": "1.9",
            "tile_definitions": self.tile_definitions
        }

        json_str = json.dumps(tiled_json, indent=2, ensure_ascii=False)

        def format_data(match):
            content = match.group(1)
            arr = json.loads('[' + content + ']')
            lines = [', '.join(str(v) for v in arr[i:i+50]) for i in range(0, len(arr), 50)]
            return '"data": [\n    ' + ',\n    '.join(lines) + '\n  ]'

        json_str = re.sub(r'"data":\s*\[(.*?)\]', format_data, json_str, flags=re.DOTALL)

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(json_str)
        wx.MessageBox(f"地图已保存至:\n{filepath}", "成功", wx.OK)


class MapEditorApp(wx.App):
    """地图编辑器应用程序类"""
    def OnInit(self):
        """应用程序初始化"""
        # 单实例检测
        self.instance = wx.SingleInstanceChecker("MapEditor")
        if self.instance.IsAnotherRunning():
            wx.MessageBox("编辑器已在运行！", "提示", wx.OK)
            return False
        
        # 创建主窗口
        frame = MapEditorFrame()
        # 显示主窗口
        frame.Show()
        return True

if __name__ == "__main__":
    # 创建应用程序实例
    app = MapEditorApp()
    app.MainLoop()


