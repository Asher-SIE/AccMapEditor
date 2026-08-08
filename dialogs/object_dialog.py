import copy

import wx


VALUE_TYPE_LABELS = {
    "string": "文本",
    "number": "数字",
    "boolean": "布尔",
    "array": "数组",
    "object": "对象",
}

VALUE_TYPE_KEYS = {v: k for k, v in VALUE_TYPE_LABELS.items()}


def infer_value_type(value):
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return "number"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return "string"


def format_property_value(value):
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, list):
        return f"[{len(value)}项]"
    if isinstance(value, dict):
        return f"{{{len(value)}字段}}"
    if isinstance(value, str):
        return value
    return str(value)


class StructuredValueDialog(wx.Dialog):
    def __init__(self, parent, title, value=None, name="", require_name=False):
        super().__init__(parent, title=title)
        self.require_name = require_name
        self.value = copy.deepcopy(value) if value is not None else ""
        self.result_name = name
        self.result_value = None
        self.object_keys = []
        self._type_cache = {}
        self._current_type = infer_value_type(self.value)
        self._type_cache[self._current_type] = copy.deepcopy(self.value)

        main_sizer = wx.BoxSizer(wx.VERTICAL)

        if self.require_name:
            name_sizer = wx.BoxSizer(wx.HORIZONTAL)
            name_sizer.Add(
                wx.StaticText(self, label="名称："),
                0,
                wx.ALIGN_CENTER_VERTICAL | wx.RIGHT,
                5,
            )
            self.name_input = wx.TextCtrl(self, value=name)
            name_sizer.Add(self.name_input, 1, wx.EXPAND)
            main_sizer.Add(name_sizer, 0, wx.EXPAND | wx.ALL, 8)
        else:
            self.name_input = None

        type_sizer = wx.BoxSizer(wx.HORIZONTAL)
        type_sizer.Add(
            wx.StaticText(self, label="值类型："),
            0,
            wx.ALIGN_CENTER_VERTICAL | wx.RIGHT,
            5,
        )
        self.type_choice = wx.Choice(self, choices=list(VALUE_TYPE_KEYS.keys()))
        type_label = VALUE_TYPE_LABELS[infer_value_type(self.value)]
        self.type_choice.SetStringSelection(type_label)
        type_sizer.Add(self.type_choice, 1, wx.EXPAND)
        main_sizer.Add(type_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)

        self.value_panel = wx.Panel(self)
        self.value_sizer = wx.BoxSizer(wx.VERTICAL)
        self.value_panel.SetSizer(self.value_sizer)
        main_sizer.Add(self.value_panel, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 8)

        btn_sizer = self.CreateButtonSizer(wx.OK | wx.CANCEL)
        main_sizer.Add(btn_sizer, 0, wx.EXPAND | wx.ALL, 8)

        self.SetSizer(main_sizer)
        self.Bind(wx.EVT_CHOICE, self.on_type_changed, self.type_choice)
        self.Bind(wx.EVT_BUTTON, self.on_ok, id=wx.ID_OK)

        self.rebuild_value_editor()
        self.SetSize((520, 420))

    def get_selected_type(self):
        return VALUE_TYPE_KEYS[self.type_choice.GetStringSelection()]

    def default_value_for_type(self, value_type):
        if value_type == "string":
            return ""
        if value_type == "number":
            return 0
        if value_type == "boolean":
            return False
        if value_type == "array":
            return []
        if value_type == "object":
            return {}
        return ""

    def _capture_current_value(self, value_type):
        if value_type == "string":
            if hasattr(self, "scalar_input") and self.scalar_input:
                return self.scalar_input.GetValue()
        elif value_type == "number":
            if hasattr(self, "scalar_input") and self.scalar_input:
                try:
                    return self.parse_number(self.scalar_input.GetValue())
                except ValueError:
                    return self.value
        elif value_type == "boolean":
            if hasattr(self, "bool_input") and self.bool_input:
                return self.bool_input.GetValue()
        elif value_type in ("array", "object"):
            return copy.deepcopy(self.value)
        return self.value

    def on_type_changed(self, event):
        old_type = self._current_type
        self._type_cache[old_type] = self._capture_current_value(old_type)
        new_type = self.get_selected_type()
        if new_type in self._type_cache:
            self.value = copy.deepcopy(self._type_cache[new_type])
        else:
            self.value = self.default_value_for_type(new_type)
        self._current_type = new_type
        self.rebuild_value_editor()

    def clear_value_sizer(self):
        for child in self.value_panel.GetChildren():
            child.Destroy()
        self.value_sizer.Clear(delete_windows=False)

    def rebuild_value_editor(self):
        self.clear_value_sizer()
        value_type = self.get_selected_type()

        if value_type == "string":
            self.scalar_input = wx.TextCtrl(self.value_panel, value=str(self.value))
            self.value_sizer.Add(self.scalar_input, 0, wx.EXPAND | wx.BOTTOM, 5)
        elif value_type == "number":
            self.scalar_input = wx.TextCtrl(self.value_panel, value=str(self.value))
            self.value_sizer.Add(self.scalar_input, 0, wx.EXPAND | wx.BOTTOM, 5)
        elif value_type == "boolean":
            self.bool_input = wx.CheckBox(self.value_panel, label="启用 / true")
            self.bool_input.SetValue(bool(self.value))
            self.value_sizer.Add(self.bool_input, 0, wx.BOTTOM, 5)
        elif value_type == "array":
            if not isinstance(self.value, list):
                self.value = []
            self.build_array_editor()
        elif value_type == "object":
            if not isinstance(self.value, dict):
                self.value = {}
            self.build_object_editor()

        self.value_panel.Layout()
        self.Layout()

    def build_array_editor(self):
        self.array_list = wx.ListBox(self.value_panel, style=wx.LB_SINGLE)
        self.refresh_array_list()
        self.value_sizer.Add(self.array_list, 1, wx.EXPAND | wx.BOTTOM, 5)

        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        btn_add = wx.Button(self.value_panel, label="添加项")
        btn_edit = wx.Button(self.value_panel, label="编辑项")
        btn_del = wx.Button(self.value_panel, label="删除项")
        btn_sizer.Add(btn_add, 1, wx.RIGHT, 5)
        btn_sizer.Add(btn_edit, 1, wx.RIGHT, 5)
        btn_sizer.Add(btn_del, 1)
        self.value_sizer.Add(btn_sizer, 0, wx.EXPAND)

        btn_add.Bind(wx.EVT_BUTTON, self.on_add_array_item)
        btn_edit.Bind(wx.EVT_BUTTON, self.on_edit_array_item)
        btn_del.Bind(wx.EVT_BUTTON, self.on_delete_array_item)

    def refresh_array_list(self):
        self.array_list.Clear()
        for idx, item in enumerate(self.value, start=1):
            self.array_list.Append(f"第{idx}项 = {format_property_value(item)}")

    def on_add_array_item(self, event):
        dlg = StructuredValueDialog(self, "添加数组项", value="")
        if dlg.ShowModal() == wx.ID_OK:
            self.value.append(dlg.get_value())
            self.refresh_array_list()
        dlg.Destroy()

    def on_edit_array_item(self, event):
        sel = self.array_list.GetSelection()
        if sel == wx.NOT_FOUND:
            wx.MessageBox("请先选择数组项！", "提示", wx.OK | wx.ICON_WARNING)
            return
        dlg = StructuredValueDialog(self, "编辑数组项", value=self.value[sel])
        if dlg.ShowModal() == wx.ID_OK:
            self.value[sel] = dlg.get_value()
            self.refresh_array_list()
        dlg.Destroy()

    def on_delete_array_item(self, event):
        sel = self.array_list.GetSelection()
        if sel == wx.NOT_FOUND:
            wx.MessageBox("请先选择数组项！", "提示", wx.OK | wx.ICON_WARNING)
            return
        del self.value[sel]
        self.refresh_array_list()

    def build_object_editor(self):
        self.object_list = wx.ListBox(self.value_panel, style=wx.LB_SINGLE)
        self.refresh_object_list()
        self.value_sizer.Add(self.object_list, 1, wx.EXPAND | wx.BOTTOM, 5)

        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        btn_add = wx.Button(self.value_panel, label="添加字段")
        btn_edit = wx.Button(self.value_panel, label="编辑字段")
        btn_del = wx.Button(self.value_panel, label="删除字段")
        btn_sizer.Add(btn_add, 1, wx.RIGHT, 5)
        btn_sizer.Add(btn_edit, 1, wx.RIGHT, 5)
        btn_sizer.Add(btn_del, 1)
        self.value_sizer.Add(btn_sizer, 0, wx.EXPAND)

        btn_add.Bind(wx.EVT_BUTTON, self.on_add_object_field)
        btn_edit.Bind(wx.EVT_BUTTON, self.on_edit_object_field)
        btn_del.Bind(wx.EVT_BUTTON, self.on_delete_object_field)

    def refresh_object_list(self):
        self.object_list.Clear()
        self.object_keys = list(self.value.keys())
        for key in self.object_keys:
            self.object_list.Append(f"{key} = {format_property_value(self.value[key])}")

    def on_add_object_field(self, event):
        dlg = StructuredValueDialog(self, "添加字段", value="", require_name=True)
        if dlg.ShowModal() == wx.ID_OK:
            name = dlg.get_name()
            if name in self.value:
                wx.MessageBox("字段名已存在！", "提示", wx.OK | wx.ICON_WARNING)
            else:
                self.value[name] = dlg.get_value()
                self.refresh_object_list()
        dlg.Destroy()

    def on_edit_object_field(self, event):
        sel = self.object_list.GetSelection()
        if sel == wx.NOT_FOUND:
            wx.MessageBox("请先选择字段！", "提示", wx.OK | wx.ICON_WARNING)
            return
        old_name = self.object_keys[sel]
        dlg = StructuredValueDialog(
            self,
            "编辑字段",
            value=self.value[old_name],
            name=old_name,
            require_name=True,
        )
        if dlg.ShowModal() == wx.ID_OK:
            new_name = dlg.get_name()
            if new_name != old_name and new_name in self.value:
                wx.MessageBox("字段名已存在！", "提示", wx.OK | wx.ICON_WARNING)
            else:
                if new_name != old_name:
                    del self.value[old_name]
                self.value[new_name] = dlg.get_value()
                self.refresh_object_list()
        dlg.Destroy()

    def on_delete_object_field(self, event):
        sel = self.object_list.GetSelection()
        if sel == wx.NOT_FOUND:
            wx.MessageBox("请先选择字段！", "提示", wx.OK | wx.ICON_WARNING)
            return
        del self.value[self.object_keys[sel]]
        self.refresh_object_list()

    def parse_number(self, text):
        text = text.strip()
        if not text:
            raise ValueError("数字不能为空")
        if any(ch in text for ch in (".", "e", "E")):
            return float(text)
        return int(text)

    def on_ok(self, event):
        if self.require_name:
            name = self.name_input.GetValue().strip()
            if not name:
                wx.MessageBox("名称不能为空！", "提示", wx.OK | wx.ICON_WARNING)
                return
            self.result_name = name

        value_type = self.get_selected_type()
        try:
            if value_type == "string":
                self.result_value = self.scalar_input.GetValue()
            elif value_type == "number":
                self.result_value = self.parse_number(self.scalar_input.GetValue())
            elif value_type == "boolean":
                self.result_value = self.bool_input.GetValue()
            elif value_type in ("array", "object"):
                self.result_value = copy.deepcopy(self.value)
        except ValueError as exc:
            wx.MessageBox(str(exc), "提示", wx.OK | wx.ICON_WARNING)
            return

        event.Skip()

    def get_name(self):
        return self.result_name

    def get_value(self):
        return self.result_value


class PropertyListPanel(wx.Panel):
    """可复用的属性编辑面板：ListBox + 添加/编辑/删除三按钮。

    支持任意 JSON 类型（string/number/boolean/array/object），通过
    StructuredValueDialog 进行编辑，供对象/瓦片/地图属性等复用。
    """

    def __init__(self, parent, properties=None, label="自定义属性："):
        super().__init__(parent)
        self.properties = (
            copy.deepcopy(properties) if properties is not None else {}
        )
        self.property_keys = []

        sizer = wx.BoxSizer(wx.VERTICAL)

        if label:
            sizer.Add(
                wx.StaticText(self, label=label), 0, wx.LEFT | wx.TOP, 0
            )

        self.prop_list = wx.ListBox(self, style=wx.LB_SINGLE)
        sizer.Add(self.prop_list, 1, wx.EXPAND | wx.TOP, 5)

        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.btn_add_prop = wx.Button(self, label="添加属性")
        self.btn_edit_prop = wx.Button(self, label="编辑")
        self.btn_del_prop = wx.Button(self, label="删除")
        btn_sizer.Add(self.btn_add_prop, 1, wx.RIGHT, 5)
        btn_sizer.Add(self.btn_edit_prop, 1, wx.RIGHT, 5)
        btn_sizer.Add(self.btn_del_prop, 1)
        sizer.Add(btn_sizer, 0, wx.EXPAND | wx.TOP, 5)

        self.SetSizer(sizer)

        self.btn_add_prop.Bind(wx.EVT_BUTTON, self.on_add_prop)
        self.btn_edit_prop.Bind(wx.EVT_BUTTON, self.on_edit_prop)
        self.btn_del_prop.Bind(wx.EVT_BUTTON, self.on_del_prop)
        self.prop_list.Bind(wx.EVT_LISTBOX_DCLICK, self.on_edit_prop)

        self.refresh_prop_list()

    def refresh_prop_list(self):
        self.prop_list.Clear()
        self.property_keys = list(self.properties.keys())
        for name in self.property_keys:
            value = self.properties[name]
            self.prop_list.Append(
                f"{name} = {format_property_value(value)}"
            )

    def set_properties(self, properties):
        self.properties = (
            copy.deepcopy(properties) if properties is not None else {}
        )
        self.refresh_prop_list()

    def get_properties(self):
        return copy.deepcopy(self.properties)

    def on_add_prop(self, event):
        dlg = StructuredValueDialog(self, "添加属性", value="", require_name=True)
        if dlg.ShowModal() == wx.ID_OK:
            name = dlg.get_name()
            self.properties[name] = dlg.get_value()
            self.refresh_prop_list()
        dlg.Destroy()

    def on_edit_prop(self, event):
        sel = self.prop_list.GetSelection()
        if sel == wx.NOT_FOUND:
            wx.MessageBox("请先选择要编辑的属性！", "提示", wx.OK | wx.ICON_WARNING)
            return
        old_name = self.property_keys[sel]
        dlg = StructuredValueDialog(
            self,
            "编辑属性",
            value=self.properties[old_name],
            name=old_name,
            require_name=True,
        )
        if dlg.ShowModal() == wx.ID_OK:
            new_name = dlg.get_name()
            if new_name != old_name:
                del self.properties[old_name]
            self.properties[new_name] = dlg.get_value()
            self.refresh_prop_list()
        dlg.Destroy()

    def on_del_prop(self, event):
        sel = self.prop_list.GetSelection()
        if sel == wx.NOT_FOUND:
            wx.MessageBox("请先选择要删除的属性！", "提示", wx.OK | wx.ICON_WARNING)
            return
        name = self.property_keys[sel]
        del self.properties[name]
        self.refresh_prop_list()


class ObjectDialog(wx.Dialog):
    TILE_SIZE = 32

    def __init__(
        self,
        parent,
        obj_data=None,
        is_edit=False,
        next_id=1,
        default_tile_x=0,
        default_tile_y=0,
    ):
        title = "编辑对象" if is_edit else "添加对象"
        super().__init__(parent, title=title)

        self.obj_data = obj_data if obj_data else {}
        self.is_edit = is_edit
        self.next_id = next_id

        if obj_data and obj_data.get("x") is not None:
            default_tile_x = int(obj_data.get("x", 0)) // self.TILE_SIZE
            default_tile_y = int(obj_data.get("y", 0)) // self.TILE_SIZE

        sizer = wx.BoxSizer(wx.VERTICAL)

        info_sizer = wx.FlexGridSizer(rows=7, cols=2, hgap=5, vgap=5)

        info_sizer.Add(wx.StaticText(self, label="对象ID："))
        self.id_input = wx.SpinCtrl(
            self,
            value=str(self.obj_data.get("id", self.next_id)),
            min=1,
            max=999999,
        )
        if not is_edit:
            self.id_input.Disable()
        info_sizer.Add(self.id_input, 1, wx.EXPAND)

        info_sizer.Add(wx.StaticText(self, label="对象名称："))
        self.name_input = wx.TextCtrl(self, value=self.obj_data.get("name", ""))
        info_sizer.Add(self.name_input, 1, wx.EXPAND)

        info_sizer.Add(wx.StaticText(self, label="对象类型："))
        self.type_input = wx.TextCtrl(self, value=self.obj_data.get("type", ""))
        info_sizer.Add(self.type_input, 1, wx.EXPAND)

        info_sizer.Add(wx.StaticText(self, label="X坐标："))
        self.tile_x_input = wx.SpinCtrl(
            self, value=str(default_tile_x), min=0, max=1000
        )
        info_sizer.Add(self.tile_x_input, 1, wx.EXPAND)

        info_sizer.Add(wx.StaticText(self, label="Y坐标："))
        self.tile_y_input = wx.SpinCtrl(
            self, value=str(default_tile_y), min=0, max=1000
        )
        info_sizer.Add(self.tile_y_input, 1, wx.EXPAND)

        info_sizer.Add(wx.StaticText(self, label="宽度(瓦片)："))
        self.tile_w_input = wx.SpinCtrl(
            self,
            value=str(
                int(obj_data.get("width", 32)) // self.TILE_SIZE if obj_data else 1
            ),
            min=1,
            max=100,
        )
        info_sizer.Add(self.tile_w_input, 1, wx.EXPAND)

        info_sizer.Add(wx.StaticText(self, label="高度(瓦片)："))
        self.tile_h_input = wx.SpinCtrl(
            self,
            value=str(
                int(obj_data.get("height", 32)) // self.TILE_SIZE if obj_data else 1
            ),
            min=1,
            max=100,
        )
        info_sizer.Add(self.tile_h_input, 1, wx.EXPAND)

        sizer.Add(info_sizer, 0, wx.EXPAND | wx.ALL, 10)

        self.prop_panel = PropertyListPanel(
            self,
            properties=self.obj_data.get("properties", {}),
            label="自定义属性：",
        )
        sizer.Add(self.prop_panel, 1, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 10)

        btn_sizer = self.CreateButtonSizer(wx.OK | wx.CANCEL)
        sizer.Add(btn_sizer, 0, wx.EXPAND | wx.ALL, 10)

        self.SetSizer(sizer)
        self.SetSize((400, 450))

    def Validate(self):
        for ctrl in (
            self.tile_x_input,
            self.tile_y_input,
            self.tile_w_input,
            self.tile_h_input,
        ):
            try:
                ctrl.SetValue(int(ctrl.GetValue()))
            except (ValueError, TypeError):
                pass
        return True

    def get_object_data(self):
        tile_x = self.tile_x_input.GetValue()
        tile_y = self.tile_y_input.GetValue()
        tile_w = self.tile_w_input.GetValue()
        tile_h = self.tile_h_input.GetValue()

        obj = {
            "id": self.id_input.GetValue(),
            "name": self.name_input.GetValue().strip(),
            "type": self.type_input.GetValue().strip(),
            "x": tile_x * self.TILE_SIZE,
            "y": tile_y * self.TILE_SIZE,
            "width": tile_w * self.TILE_SIZE,
            "height": tile_h * self.TILE_SIZE,
            "properties": self.prop_panel.get_properties(),
        }
        return obj
