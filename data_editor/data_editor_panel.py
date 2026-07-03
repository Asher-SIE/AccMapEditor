import wx

from json_data import JsonDataManager
from data_editor.json_browser import JsonBrowserPanel


class DataEditorPanel(wx.Panel):
    """右侧数据编辑容器：单一 JsonBrowserPanel + JsonDataManager。"""

    def __init__(self, parent, backup_dir, on_dirty_change=None):
        super().__init__(parent)
        self.manager = JsonDataManager()
        self.backup_dir = backup_dir
        self._on_dirty_change = on_dirty_change
        self.current_file_id = None

        sizer = wx.BoxSizer(wx.VERTICAL)
        self.browser = JsonBrowserPanel(
            self, self.manager, on_dirty_change=self._dirty
        )
        sizer.Add(self.browser, 1, wx.EXPAND)
        self.SetSizer(sizer)

    def _dirty(self):
        if self._on_dirty_change:
            self._on_dirty_change()

    def active_path(self):
        return self.manager.filepath

    def is_file_modified(self):
        return self.manager.is_modified()

    def select(self, info):
        kind = info.get("kind")
        if kind not in ("data_file",):
            return
        path = info.get("path", "")
        file_id = info.get("file_id", "")
        if not path:
            return
        if self.manager.filepath != path or not self.manager.is_loaded():
            self.manager.load(path)
        self.current_file_id = file_id
        self.browser.open_root(file_id)
        self._dirty()

    def save(self):
        result = self.manager.save(self.backup_dir)
        self._dirty()
        return result

    def undo(self):
        if self.manager.undo():
            self.browser.refresh()
            self._dirty()
            return True
        return False

    def redo(self):
        if self.manager.redo():
            self.browser.refresh()
            self._dirty()
            return True
        return False

    def can_undo(self):
        return self.manager.can_undo()

    def can_redo(self):
        return self.manager.can_redo()

    def reset(self):
        self.manager = JsonDataManager()
        self.current_file_id = None
        self.browser.manager = self.manager
        self.browser.open_root("")
