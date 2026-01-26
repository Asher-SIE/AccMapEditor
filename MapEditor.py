import wx
import wx.grid as gridlib
import json
import copy

# ========== 瓦片定义 ==========
TILE_DEFINITIONS = {
    0: "空地",
    1: "墙壁",
    2: "水",
    3: "草地",
    4: "门",
    5: "宝箱"
}

# ========== 全局剪贴板 ==========
CLIPBOARD = None  # 存储 [[row], [row], ...] 的二维列表



class TileSelectionDialog(wx.Dialog):
    def __init__(self, parent, tile_defs):
        super().__init__(parent, title="选择瓦片")
        sizer = wx.BoxSizer(wx.VERTICAL)
        choices = [f"{k}: {v}" for k, v in sorted(tile_defs.items())]
        self.listbox = wx.ListBox(self, choices=choices)
        self.listbox.SetSelection(0)
        sizer.Add(self.listbox, 1, wx.ALL | wx.EXPAND, 10)
        btn_sizer = self.CreateButtonSizer(wx.OK | wx.CANCEL)
        sizer.Add(btn_sizer, 0, wx.ALL | wx.EXPAND, 10)
        self.SetSizer(sizer)
        self.listbox.SetFocus()
        self.tile_keys = list(sorted(tile_defs.keys()))


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
        w_sizer.Add(wx.StaticText(self, label="宽度:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
        self.width_ctrl = wx.SpinCtrl(self, value=str(current_w), min=1, max=1000)
        w_sizer.Add(self.width_ctrl, 0)
        sizer.Add(w_sizer, 0, wx.ALL, 5)

        h_sizer = wx.BoxSizer(wx.HORIZONTAL)
        h_sizer.Add(wx.StaticText(self, label="高度:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
        self.height_ctrl = wx.SpinCtrl(self, value=str(current_h), min=1, max=1000)
        h_sizer.Add(self.height_ctrl, 0)
        sizer.Add(h_sizer, 0, wx.ALL, 5)

        btn_sizer = self.CreateButtonSizer(wx.OK | wx.CANCEL)
        sizer.Add(btn_sizer, 0, wx.ALL | wx.EXPAND, 10)
        self.SetSizer(sizer)


    def get_size(self):
        return self.width_ctrl.GetValue(), self.height_ctrl.GetValue()


class CustomTileDialog(wx.Dialog):
    def __init__(self, parent, tile_defs):
        super().__init__(parent, title="自定义瓦片类型")
        self.tile_entries = []
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(wx.StaticText(self, label="格式: ID 名称 (例如: 0 空地)"), 0, wx.ALL, 5)

        for tile_id, name in sorted(tile_defs.items()):
            row = wx.BoxSizer(wx.HORIZONTAL)
            id_ctrl = wx.TextCtrl(self, value=str(tile_id), size=(60, -1))
            name_ctrl = wx.TextCtrl(self, value=name)
            row.Add(id_ctrl, 0, wx.RIGHT, 5)
            row.Add(name_ctrl, 1)
            sizer.Add(row, 0, wx.EXPAND | wx.ALL, 2)
            self.tile_entries.append((id_ctrl, name_ctrl))

        btn_add = wx.Button(self, label="添加新瓦片")
        btn_add.Bind(wx.EVT_BUTTON, self.on_add_tile)
        sizer.Add(btn_add, 0, wx.ALL, 5)

        btn_sizer = self.CreateButtonSizer(wx.OK | wx.CANCEL)
        sizer.Add(btn_sizer, 0, wx.ALL | wx.EXPAND, 10)
        self.SetSizer(sizer)


    def on_add_tile(self, event):
        row = wx.BoxSizer(wx.HORIZONTAL)
        id_ctrl = wx.TextCtrl(self, value="6", size=(60, -1))
        name_ctrl = wx.TextCtrl(self, value="新瓦片")
        row.Add(id_ctrl, 0, wx.RIGHT, 5)
        row.Add(name_ctrl, 1)
        self.GetSizer().Insert(len(self.tile_entries) + 1, row, 0, wx.EXPAND | wx.ALL, 2)
        self.tile_entries.append((id_ctrl, name_ctrl))
        self.Layout()


    def get_tile_definitions(self):
        defs = {}
        for id_ctrl, name_ctrl in self.tile_entries:
            try:
                tile_id = int(id_ctrl.GetValue())
                name = name_ctrl.GetValue().strip()
                if name:
                    defs[tile_id] = name
            except ValueError:
                continue
        return defs


# ========== 主窗口 ==========
class MapEditorFrame(wx.Frame):
    def __init__(self):
        super().__init__(None, title="无障碍地图编辑器", size=(900, 700))
        
        self.width = 200
        self.height = 200
        self.map_data = [[0 for _ in range(self.width)] for _ in range(self.height)]
        self.cursor_x = 0
        self.cursor_y = 0
        self.tile_definitions = TILE_DEFINITIONS.copy()

        # 区域选择
        self.selection_start = None  # (x, y)
        self.selection_end = None    # (x, y)

        self.init_ui()
        self.create_menu()
        self.update_status()


    def init_ui(self):
        panel = wx.Panel(self)
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        # 状态栏
        self.status_label = wx.StaticText(panel, label="")
        main_sizer.Add(self.status_label, 0, wx.ALL, 5)

        # Grid
        self.grid = gridlib.Grid(panel)
        self.grid.CreateGrid(self.height, self.width)
        self.grid.EnableEditing(False)
        self.grid.SetDefaultCellAlignment(wx.ALIGN_CENTER, wx.ALIGN_CENTER)
        self.grid.SetRowLabelSize(40)
        self.grid.SetColLabelSize(30)
        
        # 绑定事件
        self.grid.Bind(wx.EVT_KEY_DOWN, self.on_key_down)
        self.grid.Bind(gridlib.EVT_GRID_SELECT_CELL, self.on_grid_select)

        main_sizer.Add(self.grid, 1, wx.EXPAND | wx.ALL, 5)
        panel.SetSizer(main_sizer)
        self.grid.SetFocus()


    def create_menu(self):
        menubar = wx.MenuBar()
        file_menu = wx.Menu()
        save_item = file_menu.Append(wx.ID_SAVE, "保存为 Tiled JSON...\tCtrl+S")
        resize_item = file_menu.Append(wx.ID_ANY, "调整地图尺寸...\tCtrl+R")
        edit_menu = wx.Menu()
        custom_tile_item = edit_menu.Append(wx.ID_ANY, "自定义瓦片类型...")
        menubar.Append(file_menu, "文件")
        menubar.Append(edit_menu, "编辑")
        self.SetMenuBar(menubar)

        self.Bind(wx.EVT_MENU, self.on_save, save_item)
        self.Bind(wx.EVT_MENU, self.on_resize, resize_item)
        self.Bind(wx.EVT_MENU, self.on_custom_tiles, custom_tile_item)
        self.Bind(wx.EVT_CHAR_HOOK, self.on_global_key)


    def on_global_key(self, event):
        key = event.GetKeyCode()
        if event.ControlDown():
            if key == ord('S'):
                self.on_save(None)
                return
            elif key == ord('R'):
                self.on_resize(None)
                return
            elif key == ord('C'):
                self.copy_selection()
                return
            elif key == ord('V'):
                self.paste_clipboard()
                return
        elif key == wx.WXK_DELETE or key == wx.WXK_BACK:
            self.clear_selection()
            return
        event.Skip()


    def on_resize(self, event):
        dlg = ResizeDialog(self, self.width, self.height)
        if dlg.ShowModal() == wx.ID_OK:
            new_w, new_h = dlg.get_size()
            if new_w <= 0 or new_h <= 0:
                wx.MessageBox("尺寸必须大于0", "错误", wx.OK | wx.ICON_ERROR)
                return

            old_data = self.map_data
            self.width, self.height = new_w, new_h
            self.map_data = [[0 for _ in range(new_w)] for _ in range(new_h)]

            for y in range(min(len(old_data), new_h)):
                for x in range(min(len(old_data[0]), new_w)):
                    self.map_data[y][x] = old_data[y][x]

            # 刷新 Grid
            self.grid.ClearGrid()
            self.grid.DeleteRows(0, self.grid.GetNumberRows())
            self.grid.DeleteCols(0, self.grid.GetNumberCols())
            self.grid.AppendRows(new_h)
            self.grid.AppendCols(new_w)

            self.cursor_x = min(self.cursor_x, new_w - 1)
            self.cursor_y = min(self.cursor_y, new_h - 1)
            self.grid.SelectBlock(self.cursor_y, self.cursor_x, self.cursor_y, self.cursor_x)
            self.update_status()
        dlg.Destroy()


    def on_custom_tiles(self, event):
        dlg = CustomTileDialog(self, self.tile_definitions)
        if dlg.ShowModal() == wx.ID_OK:
            self.tile_definitions = dlg.get_tile_definitions()
        dlg.Destroy()


    def update_status(self):
        tile_id = self.map_data[self.cursor_y][self.cursor_x]
        tile_name = self.tile_definitions.get(tile_id, f"未知({tile_id})")
        coord_info = f"位置: ({self.cursor_x}, {self.cursor_y})"
        if self.selection_start and self.selection_end:
            x1, y1 = self.selection_start
            x2, y2 = self.selection_end
            coord_info += f" | 选区: ({x1},{y1})-({x2},{y2})"
        self.status_label.SetLabel(f"{coord_info} | 瓦片: {tile_name}")
        self.status_label.Refresh()
        wx.Yield() 


    def on_key_down(self, event):
        key = event.GetKeyCode()
        modifiers = event.GetModifiers()
        moved = False

        # 方向键移动
        if key in [wx.WXK_LEFT, wx.WXK_RIGHT, wx.WXK_UP, wx.WXK_DOWN]:
            old_x, old_y = self.cursor_x, self.cursor_y
            if key == wx.WXK_LEFT and self.cursor_x > 0:
                self.cursor_x -= 1; moved = True
            elif key == wx.WXK_RIGHT and self.cursor_x < self.width - 1:
                self.cursor_x += 1; moved = True
            elif key == wx.WXK_UP and self.cursor_y > 0:
                self.cursor_y -= 1; moved = True
            elif key == wx.WXK_DOWN and self.cursor_y < self.height - 1:
                self.cursor_y += 1; moved = True

            if moved:
                self.grid.SelectBlock(self.cursor_y, self.cursor_x, self.cursor_y, self.cursor_x)
                self.update_status()
                return

        # 区域选择
        elif key == wx.WXK_RETURN:
            if modifiers == wx.MOD_SHIFT:
                self.selection_start = (self.cursor_x, self.cursor_y)
                self.update_status()
                return
            elif modifiers == wx.MOD_CONTROL:
                self.selection_end = (self.cursor_x, self.cursor_y)
                self.update_status()
                return
            else:
                self.on_set_tile(None)
                return

        event.Skip()


    def on_grid_select(self, event):
        self.cursor_y = event.GetRow()
        self.cursor_x = event.GetCol()
        self.update_status()
        event.Skip()


    def on_set_tile(self, event):
        dlg = TileSelectionDialog(self, self.tile_definitions)
        if dlg.ShowModal() == wx.ID_OK:
            tile_id = dlg.GetSelectedTileId()
            self.map_data[self.cursor_y][self.cursor_x] = tile_id
            self.grid.SetCellValue(self.cursor_y, self.cursor_x, str(tile_id))
            self.update_status()
        dlg.Destroy()


    # ====== 区域操作 ======
    def get_selection_bounds(self):
        if not self.selection_start or not self.selection_end:
            return None
        x1, y1 = self.selection_start
        x2, y2 = self.selection_end
        left = min(x1, x2); right = max(x1, x2)
        top = min(y1, y2); bottom = max(y1, y2)
        return left, top, right, bottom


    def copy_selection(self):
        bounds = self.get_selection_bounds()
        if not bounds:
            wx.MessageBox("请先用 Shift+Enter 和 Ctrl+Enter 选择区域", "提示", wx.OK)
            return
        left, top, right, bottom = bounds
        global CLIPBOARD
        CLIPBOARD = []
        for y in range(top, bottom + 1):
            row = []
            for x in range(left, right + 1):
                row.append(self.map_data[y][x])
            CLIPBOARD.append(row)
        self.update_status()
        print("已复制区域")  # 实际可通过 status_label 显示


    def clear_selection(self):
        bounds = self.get_selection_bounds()
        if not bounds:
            # 如果没选区，只清当前格子
            self.map_data[self.cursor_y][self.cursor_x] = 0
            self.grid.SetCellValue(self.cursor_y, self.cursor_x, "0")
        else:
            left, top, right, bottom = bounds
            for y in range(top, bottom + 1):
                for x in range(left, right + 1):
                    self.map_data[y][x] = 0
                    self.grid.SetCellValue(y, x, "0")
        self.update_status()


    def paste_clipboard(self):
        global CLIPBOARD
        if CLIPBOARD is None:
            wx.MessageBox("剪贴板为空", "提示", wx.OK)
            return
        paste_h = len(CLIPBOARD)
        paste_w = len(CLIPBOARD[0]) if paste_h > 0 else 0

        if self.cursor_y + paste_h > self.height or self.cursor_x + paste_w > self.width:
            wx.MessageBox("粘贴区域超出地图边界", "错误", wx.OK | wx.ICON_ERROR)
            return

        for dy, row in enumerate(CLIPBOARD):
            for dx, tile_id in enumerate(row):
                y = self.cursor_y + dy
                x = self.cursor_x + dx
                self.map_data[y][x] = tile_id
                self.grid.SetCellValue(y, x, str(tile_id))
        self.update_status()


    # ====== 保存 ======
    def on_save(self, event):
        with wx.FileDialog(
            self, "保存地图", wildcard="Tiled JSON (*.json)|*.json",
            style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT
        ) as dlg:
            if dlg.ShowModal() == wx.ID_OK:
                self.save_to_tiled_json(dlg.GetPath())


    def save_to_tiled_json(self, filepath):
        data = []
        for y in range(self.height):
            for x in range(self.width):
                data.append(self.map_data[y][x])

        tiled_json = {
            "width": self.width,
            "height": self.height,
            "layers": [{
                "data": data,
                "name": "Ground",
                "width": self.width,
                "height": self.height,
                "opacity": 1,
                "type": "tilelayer",
                "visible": True
            }],
            "tilewidth": 32,
            "tileheight": 32,
            "orientation": "orthogonal",
            "infinite": False,
            "nextlayerid": 2,
            "nextobjectid": 1,
            "renderorder": "right-down",
            "tiledversion": "1.10.1",
            "version": "1.9"
        }

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(tiled_json, f, indent=2)
        wx.MessageBox(f"地图已保存至:\n{filepath}", "成功", wx.OK)


# ========== 启动 ==========
class MapEditorApp(wx.App):
    def OnInit(self):
        frame = MapEditorFrame()
        frame.Show()
        return True

if __name__ == "__main__":
    app = MapEditorApp()
    app.MainLoop()


