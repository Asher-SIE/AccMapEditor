import wx

from json_data import JsonDataManager
from data_editor.collection_view import CollectionView
from data_editor.entity_view import EntityView
from data_editor.config_view import ConfigView

PAGE_COLLECTION = 0
PAGE_ENTITY = 1
PAGE_CONFIG = 2


class DataEditorPanel(wx.Panel):
    """右侧数据编辑容器：持有 JsonDataManager，按树选择路由到三个子视图。"""

    def __init__(self, parent, backup_dir, on_dirty_change=None):
        super().__init__(parent)
        self.manager = JsonDataManager()
        self.backup_dir = backup_dir
        self.on_dirty_change = on_dirty_change
        self.current_file_id = None
        self._current_page = -1

        sizer = wx.BoxSizer(wx.VERTICAL)
        self.book = wx.Simplebook(self)

        self.collection_view = CollectionView(
            self.book, self.manager, on_open_entity=self._open_entity_by_id
        )
        self.book.AddPage(self.collection_view, "")

        self.entity_view = EntityView(self.book, self.manager)
        self.book.AddPage(self.entity_view, "")

        self.config_view = ConfigView(self.book, self.manager)
        self.book.AddPage(self.config_view, "")

        sizer.Add(self.book, 1, wx.EXPAND)
        self.SetSizer(sizer)

    def _switch_page(self, page):
        if self._current_page == page:
            return
        if self._current_page == PAGE_ENTITY:
            self.entity_view.commit()
        self._current_page = page
        self.book.SetSelection(page)
        self._notify_dirty()

    def _notify_dirty(self):
        if self.on_dirty_change:
            self.on_dirty_change()

    def active_path(self):
        return self.manager.filepath

    def is_modified(self):
        return self._current_page == PAGE_ENTITY and self.entity_view._loaded and True or self.manager.is_modified()

    def is_file_modified(self):
        if self._current_page == PAGE_ENTITY:
            self.entity_view.commit()
        return self.manager.is_modified()

    def select(self, info):
        kind = info.get("kind")
        if kind == "entity_file":
            root_key = info.get("default_root")
            if not root_key:
                roots = info.get("roots") or []
                if roots:
                    root_key = roots[0][0]
            if not root_key:
                self._show_empty("该文件未识别到实体集合根")
                return
            self._load_file(info.get("path", ""), info.get("file_id", ""))
            self._show_collection(info.get("file_id", ""), root_key)
            return
        if kind == "entity_group":
            self._load_file(info.get("path", ""), info.get("file_id", ""))
            self._show_collection(info.get("file_id", ""), info.get("root_key", ""))
            return
        if kind == "entity":
            self._load_file(info.get("path", ""), info.get("file_id", ""))
            self.entity_view.load(
                info.get("file_id", ""),
                info.get("root_key", ""),
                info.get("entity_id", ""),
            )
            self._switch_page(PAGE_ENTITY)
            return
        if kind == "config_file":
            self._load_file(info.get("path", ""), info.get("file_id", ""))
            self.config_view.load(info.get("file_id", ""))
            self._switch_page(PAGE_CONFIG)
            return

    def _show_empty(self, msg):
        self.collection_view.title.SetLabel(msg)
        self.collection_view.list.DeleteAllItems()
        self._switch_page(PAGE_COLLECTION)

    def _load_file(self, path, file_id):
        if self.manager.filepath == path and self.manager.is_loaded():
            self.current_file_id = file_id
            return
        if self._current_page == PAGE_ENTITY:
            self.entity_view.commit()
        self.manager.load(path)
        self.current_file_id = file_id
        self._notify_dirty()

    def _show_collection(self, file_id, root_key):
        self.collection_view.load(file_id, root_key)
        self._switch_page(PAGE_COLLECTION)

    def _open_entity_by_id(self, file_id, root_key, entity_id):
        self.entity_view.load(file_id, root_key, entity_id)
        self._switch_page(PAGE_ENTITY)

    def save(self):
        if self._current_page == PAGE_ENTITY:
            self.entity_view.commit()
        elif self._current_page == PAGE_CONFIG:
            self.config_view.commit()
        result = self.manager.save(self.backup_dir)
        self._notify_dirty()
        return result

    def undo(self):
        if self._current_page == PAGE_ENTITY:
            self.entity_view.commit()
        if self.manager.undo():
            self._reload_current_view()
            self._notify_dirty()
            return True
        return False

    def redo(self):
        if self.manager.redo():
            self._reload_current_view()
            self._notify_dirty()
            return True
        return False

    def can_undo(self):
        return self.manager.can_undo()

    def can_redo(self):
        return self.manager.can_redo()

    def _reload_current_view(self):
        if self._current_page == PAGE_COLLECTION:
            if self.collection_view.root_key:
                self.collection_view.load(
                    self.collection_view.file_id, self.collection_view.root_key
                )
        elif self._current_page == PAGE_ENTITY:
            if self.entity_view.entity_id is not None:
                self.entity_view.load(
                    self.entity_view.file_id,
                    self.entity_view.root_key,
                    self.entity_view.entity_id,
                )
        elif self._current_page == PAGE_CONFIG:
            if self.config_view.file_id:
                self.config_view.load(self.config_view.file_id)

    def reset(self):
        self.manager = JsonDataManager()
        self.current_file_id = None
        self._current_page = -1
