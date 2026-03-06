import copy
import json
import os
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
        # 构建列表框选项（按数字排序）
        choices = [f"{k}: {v}" for k, v in sorted(tile_defs.items(), key=lambda x: int(x[0]))]
        # 选中第一项
        self.listbox = wx.ListBox(self, choices=choices)
        self.listbox.SetSelection(0)
        # 列表框添加到布局
        sizer.Add(self.listbox, 1, wx.ALL | wx.EXPAND, 10)
        # 确定/取消按钮
        btn_sizer = self.CreateButtonSizer(wx.OK | wx.CANCEL)
        sizer.Add(btn_sizer, 0, wx.ALL | wx.EXPAND, 10)
        # 设置对话框布局
        self.SetSizer(sizer)
        # 设置列表框为焦点控件
        self.listbox.SetFocus()
        # 存储排序后的瓦片ID列表（按数字排序）
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
        # 创建数值选择框，范围1-1000，默认值为当前宽度
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


class CustomTileDialog(wx.Frame):
    """自定义瓦片类型窗口"""
    def __init__(self, parent, tile_defs):
        super().__init__(parent, title="自定义瓦片类型", size=(500, 400))
        self.tile_data = copy.deepcopy(tile_defs)
        self.parent = parent
        
        self.Bind(wx.EVT_SHOW, self.on_show)
        self.Bind(wx.EVT_CLOSE, self.on_close)
        
        panel = wx.Panel(self)
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        main_sizer.Add(wx.StaticText(panel, label="瓦片列表（ID: 名称） &T"), 0, wx.ALL, 5)
        self.tile_list = wx.ListBox(panel, style=wx.LB_SINGLE)
        self.refresh_list()
        main_sizer.Add(self.tile_list, 1, wx.EXPAND | wx.ALL, 5)

        input_sizer = wx.FlexGridSizer(rows=2, cols=2, hgap=10, vgap=8)
        input_sizer.Add(wx.StaticText(panel, label="瓦片ID："), 0, wx.ALIGN_CENTER_VERTICAL)
        self.id_input = wx.TextCtrl(panel)
        input_sizer.Add(self.id_input, 1, wx.EXPAND)

        input_sizer.Add(wx.StaticText(panel, label="瓦片名称："), 0, wx.ALIGN_CENTER_VERTICAL)
        self.name_input = wx.TextCtrl(panel)
        input_sizer.Add(self.name_input, 1, wx.EXPAND)
        input_sizer.AddGrowableCol(1)
        main_sizer.Add(input_sizer, 0, wx.EXPAND | wx.ALL, 10)

        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.btn_edit = wx.Button(panel, label="编辑 &E")
        self.btn_add = wx.Button(panel, label="添加 &A")
        self.btn_del = wx.Button(panel, label="删除 &D")
        self.btn_save = wx.Button(panel, label="保存并关闭 &S")

        btn_sizer.Add(self.btn_edit, 1, wx.RIGHT, 5)
        btn_sizer.Add(self.btn_add, 1, wx.RIGHT, 5)
        btn_sizer.Add(self.btn_del, 1, wx.RIGHT, 5)
        btn_sizer.Add(self.btn_save, 1)
        main_sizer.Add(btn_sizer, 0, wx.EXPAND | wx.ALL, 10)

        panel.SetSizer(main_sizer)

        self.Bind(wx.EVT_BUTTON, self.on_edit, self.btn_edit)
        self.Bind(wx.EVT_BUTTON, self.on_add, self.btn_add)
        self.Bind(wx.EVT_BUTTON, self.on_delete, self.btn_del)
        self.Bind(wx.EVT_BUTTON, self.on_save, self.btn_save)
        
        self.update_next_id()

    def on_show(self, event):
        if event.IsShown():
            wx.CallAfter(self.tile_list.SetFocus)
        event.Skip()

    def refresh_list(self):
        self.tile_list.Clear()
        sorted_items = sorted(self.tile_data.items(), key=lambda x: int(x[0]))
        for tid, name in sorted_items:
            self.tile_list.Append(f"{tid}: {name}")

    def update_next_id(self):
        if not self.tile_data:
            next_id = "0"
        else:
            max_id = max(int(k) for k in self.tile_data.keys())
            next_id = str(max_id + 1)
        self.id_input.SetValue(next_id)
        self.name_input.SetValue("")

    def on_edit(self, event):
        sel = self.tile_list.GetSelection()
        if sel == wx.NOT_FOUND:
            wx.MessageBox("请先选择要编辑的瓦片！", "提示", wx.OK | wx.ICON_WARNING)
            return
        text = self.tile_list.GetString(sel)
        tid, name = text.split(":", 1)
        self.id_input.SetValue(tid.strip())
        self.name_input.SetValue(name.strip())

    def on_add(self, event):
        tid = self.id_input.GetValue().strip()
        name = self.name_input.GetValue().strip()

        if not tid or not name:
            wx.MessageBox("ID和名称不能为空！", "提示", wx.OK | wx.ICON_WARNING)
            return

        # ID存在则更新，不存在则添加
        self.tile_data[tid] = name
        self.refresh_list()
        self.update_next_id()

    def on_delete(self, event):
        sel = self.tile_list.GetSelection()
        if sel == wx.NOT_FOUND:
            wx.MessageBox("请先选择要删除的瓦片！", "提示", wx.OK | wx.ICON_WARNING)
            return

        text = self.tile_list.GetString(sel)
        tid = text.split(":", 1)[0].strip()
        del self.tile_data[tid]
        self.refresh_list()
        self.update_next_id()

    def on_save(self, event):
        with open('./tile_definitions.json', 'w', encoding='utf-8') as f:
            json.dump(self.tile_data, f, ensure_ascii=False, indent=4)
        wx.MessageBox("保存成功！", "提示", wx.OK)
        self.notify_parent()
        self.Destroy()

    def on_close(self, event):
        result = wx.MessageBox("有未保存的更改，确定要关闭吗？", "提示", wx.YES_NO | wx.ICON_QUESTION)
        if result != wx.ID_YES:
            event.Veto()
            return
        self.notify_parent()
        self.Destroy()

    def notify_parent(self):
        self.parent.enable_and_update(self.tile_data.copy())


class MapEditorFrame(wx.Frame):
    """地图编辑器主窗口类"""
    def __init__(self):
        """初始化"""
        super().__init__(None, title="无障碍地图编辑器", size=(900, 700))
                # 地图参数
        self.width = 200
        self.height = 200
        # 地图数据
        self.map_data = [[0 for _ in range(self.width)] for _ in range(self.height)]
        self.cursor_x = 0         # 当前光标所在列
        self.cursor_y = 0         # 当前光标所在行

        # 加载瓦片字典 JSON
        global TILE_DEFINITIONS
        TILE_DEFINITIONS = self.load_tiled_data()
        # 复制默认瓦片类型定义，避免修改原字典
        self.tile_definitions = TILE_DEFINITIONS.copy()
        print(f'init字典{self.tile_definitions}')

        # 区域选择相关变量
        self.selection_start = None  # 选区起始坐标 (x, y)
        self.selection_end = None    # 选区结束坐标 (x, y)

        # 初始化UI和菜单
        self.init_ui()
        self.create_menu()
        # 更新状态栏信息
        self.update_status()
        TTS.init_engine()
        TTS.speak('编辑器启动')


    def load_tiled_data(self):
        """
        加载瓦片配置数据
        """
        config_file = './tile_definitions.json'
        # 默认配置使用字符串键
        default_config = {
            "0": "空地",
            "1": "墙壁"
        }

        
        try:
            if not os.path.exists(config_file):
                print(f"配置文件不存在，创建新文件: {config_file}")
                # 写入默认配置
                with open(config_file, 'w', encoding='utf-8') as f:
                    json.dump(default_config, f, ensure_ascii=False, indent=4)
                
                print(" 已创建默认配置文件")
                return default_config
            
            # 文件存在，读取内容
            with open(config_file, 'r', encoding='utf-8') as f:
                print(f'📂 文件对象: {f}')
                content = f.read()
                
                # 检查文件是否为空
                if not content.strip():
                    print("⚠️ 配置文件为空，创建默认配置")

                    # 重新写入默认配置
                    with open(config_file, 'w', encoding='utf-8') as f_write:
                        json.dump(default_config, f_write, ensure_ascii=False, indent=4)
                    
                    print(" 已填充默认配置")
                    return default_config
                
                # 解析JSON内容
                TILE_DEFINITIONS = json.loads(content)
                print(f'📖 字典对象: {TILE_DEFINITIONS}')
                
                # 验证配置结构
                if not isinstance(TILE_DEFINITIONS, dict):
                    print("⚠️ 配置文件格式错误，重置为默认配置")
                    return default_config
                
                # 确保所有键都是字符串
                return {str(k): v for k, v in TILE_DEFINITIONS.items()}
                
        except json.JSONDecodeError as e:
            print(f"❌ JSON解析错误: {e}")
            return default_config
            
        except Exception as e:
            print(f"❌ 加载配置文件时发生错误: {e}")
            return


    def init_ui(self):
        """初始化用户界面"""
        # 创建主面板
        panel = wx.Panel(self)
        # 创建垂直布局管理器
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        # 状态栏标签（显示光标位置、瓦片信息、选区等）
        self.status_label = wx.StaticText(panel, label="")
        main_sizer.Add(self.status_label, 0, wx.ALL, 5)

        # 创建网格控件（用于显示地图）
        self.grid = gridlib.Grid(panel)
        # 创建指定行列数的网格
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
        # 添加"保存为Tiled JSON"菜单项（快捷键Ctrl+S）
        save_item = file_menu.Append(wx.ID_SAVE, "保存为 Tiled JSON...\tCtrl+S")
        # 添加"调整地图尺寸"菜单项（快捷键Ctrl+R）
        resize_item = file_menu.Append(wx.ID_ANY, "调整地图尺寸...\tCtrl+R")
        
        # 编辑菜单
        edit_menu = wx.Menu()
        # 添加"自定义瓦片类型"菜单项
        custom_tile_item = edit_menu.Append(wx.ID_ANY, "自定义瓦片类型...")
        
        # 将菜单添加到菜单栏
        menubar.Append(file_menu, "文件")
        menubar.Append(edit_menu, "编辑")
        # 设置窗口菜单栏
        self.SetMenuBar(menubar)

        # 绑定菜单项事件
        self.Bind(wx.EVT_MENU, self.on_save, save_item)          # 保存事件
        self.Bind(wx.EVT_MENU, self.on_resize, resize_item)      # 调整尺寸事件
        self.Bind(wx.EVT_MENU, self.on_custom_tiles, custom_tile_item)  # 自定义瓦片事件
        # 绑定全局键盘钩子（处理快捷键）
        self.Bind(wx.EVT_CHAR_HOOK, self.on_global_key)


    def on_global_key(self, event):
        """
        全局键盘事件处理（快捷键）
        :param event: 键盘事件对象
        """
        key = event.GetKeyCode()
        # 处理Ctrl组合键
        if event.ControlDown():
            if key == ord('S'):          # Ctrl+S：保存
                self.on_save(None)
                return
            elif key == ord('R'):        # Ctrl+R：调整尺寸
                self.on_resize(None)
                return
            elif key == ord('C'):        # Ctrl+C：复制选区
                self.copy_selection()
                return
            elif key == ord('V'):        # Ctrl+V：粘贴选区
                self.paste_clipboard()
                return
        # 处理删除/退格键：清空选区/当前单元格
        elif key == wx.WXK_DELETE or key == wx.WXK_BACK:
            self.delete_selection()
            return
        # 未处理的按键继续传递
        event.Skip()


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
        自定义瓦片类型事件处理
        使用子窗口模式
        """
        self.Enable(False)
        self.tile_window = CustomTileDialog(self, self.tile_definitions)
        self.tile_window.Show()

    def enable_and_update(self, tile_data):
        """
        子窗口关闭后更新数据并重新启用主窗口
        """
        global TILE_DEFINITIONS
        TILE_DEFINITIONS = tile_data
        self.tile_definitions = tile_data.copy()
        self.Enable(True)
        self.Raise()


    def update_status(self):
        """更新状态栏信息（光标位置、瓦片信息、选区）"""
        # 获取当前光标位置的瓦片ID
        tile_id = str(self.map_data[self.cursor_y][self.cursor_x])
        print(f'id{tile_id}')
        # 获取瓦片名称
        tile_name = self.tile_definitions.get(tile_id, f"未知({tile_id})")
        # 基础坐标信息
        coord_info = f"({self.cursor_x}； {self.cursor_y})"
        # 有选区时添加选区信息
        if self.selection_start and self.selection_end:
            x1, y1 = self.selection_start
            x2, y2 = self.selection_end
            coord_info += f" 选区: ({x1},{y1}) 到 ({x2},{y2})"
        # 设置状态栏文本
        self.status_label.SetLabel(f"{coord_info} ； {tile_name}")
        TTS.cancel()
        TTS.speak(f"{tile_name} {coord_info}")
        # 刷新状态栏显示
        self.status_label.Refresh()
        # 强制刷新UI
        wx.Yield() 


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
            self.clear_selected()

            # 光标移动后更新选中状态和状态栏
            if moved:
                self.grid.SelectBlock(self.cursor_y, self.cursor_x, self.cursor_y, self.cursor_x)
                self.update_status()
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

            else:                                                 #设置当前单元格瓦片
                self.on_set_tile(None)
                return
        # 未处理的按键继续传递
        event.Skip()


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


    def copy_selection(self):
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


    def delete_selection(self):
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
        self.clear_selected()
        TTS.cancel()
        TTS.speak('清除')


    def clear_selected(self):
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


    def paste_clipboard(self):
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
        self.clear_selected()
        TTS.cancel()
        TTS.speak('粘贴')


    def on_save(self, event):
        """
        保存地图
        :param event: 事件对象
        """
        # 保存 JSON
        with wx.FileDialog(
            self, "保存地图", wildcard="Tiled JSON (*.json)|*.json",
            style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT
        ) as dlg:
            if dlg.ShowModal() == wx.ID_OK:
                self.save_to_tiled_json(dlg.GetPath())


    def save_to_tiled_json(self, filepath):
        """
        将地图数据保存为Tiled编辑器兼容的JSON格式
        """
        # 将二维地图数据转为一维列表（Tiled格式要求：行优先）
        data = []
        for y in range(self.height):
            for x in range(self.width):
                data.append(self.map_data[y][x])

        # 构建Tiled JSON格式数据
        tiled_json = {
            "width": self.width,                  # 地图宽度
            "height": self.height,                # 地图高度
            "layers": [{                          # 图层列表
                "data": data,                     # 瓦片数据（一维）
                "name": "Ground",                 # 图层名称
                "width": self.width,              # 图层宽度
                "height": self.height,            # 图层高度
                "opacity": 1,                     # 不透明度
                "type": "tilelayer",              # 图层类型（瓦片层）
                "visible": True                   # 是否可见
            }],
            "tilewidth": 32,                      # 瓦片宽度（像素）
            "tileheight": 32,                     # 瓦片高度（像素）
            "orientation": "orthogonal",          # 地图方向（正交）
            "infinite": False,                    # 非无限地图
            "nextlayerid": 2,                     # 下一个图层ID
            "nextobjectid": 1,                    # 下一个对象ID
            "renderorder": "right-down",          # 渲染顺序（从右到下）
            "tiledversion": "1.10.1",             # Tiled版本
            "version": "1.9"                      # JSON格式版本
        }

        # 写入JSON文件（UTF-8编码，缩进2格）
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(tiled_json, f, indent=2)
        wx.MessageBox(f"地图已保存至:\n{filepath}", "成功", wx.OK)


class MapEditorApp(wx.App):
    """地图编辑器应用程序类"""
    def OnInit(self):
        """应用程序初始化"""
        # 创建主窗口
        frame = MapEditorFrame()
        # 显示主窗口
        frame.Show()
        return True

if __name__ == "__main__":
    # 创建应用程序实例
    app = MapEditorApp()
    # 启动应用程序主循环
    app.MainLoop()


