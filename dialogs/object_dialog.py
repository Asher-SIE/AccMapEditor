import wx


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

        info_sizer = wx.FlexGridSizer(rows=6, cols=2, hgap=5, vgap=5)

        info_sizer.Add(wx.StaticText(self, label="对象ID/名称："))
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

        btn_sizer = self.CreateButtonSizer(wx.OK | wx.CANCEL)
        sizer.Add(btn_sizer, 0, wx.EXPAND | wx.ALL, 10)

        self.SetSizer(sizer)
        self.SetSize((400, 450))

        self.Bind(wx.EVT_BUTTON, self.on_add_prop, self.btn_add_prop)
        self.Bind(wx.EVT_BUTTON, self.on_del_prop, self.btn_del_prop)

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

    def refresh_prop_list(self):
        self.prop_list.Clear()
        for name, value in self.properties.items():
            self.prop_list.Append(f"{name}={value}")

    def on_add_prop(self, event):
        dlg = wx.TextEntryDialog(
            self, "输入属性名和值（格式：name=value）", "添加属性", ""
        )
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
            "properties": self.properties,
        }
        return obj
