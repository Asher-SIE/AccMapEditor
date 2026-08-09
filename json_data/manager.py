import copy
import datetime
import json
import os
import re
import shutil


def _detect_indent(text):
    """检测 JSON 原始缩进，返回空格数（默认 2）。"""
    for line in text.splitlines():
        stripped = line.lstrip(" ")
        if stripped and line[: len(line) - len(stripped)]:
            indent = len(line) - len(stripped)
            if indent > 0:
                return indent
    return 2


def _detect_trailing_newline(text):
    return "\n" if text.endswith("\n") else ""


class JsonDataManager:
    """单个 JSON 文件的内存编辑模型。

    - 加载时保留原始缩进与末尾换行，保存时原样写回。
    - 每次保存前将原文件带时间戳备份到 backup_dir。
    - 快照式撤销：每次 commit 前压栈当前数据副本。
    """

    def __init__(self):
        self.data = None
        self.filepath = None
        self._orig_indent = 2
        self._orig_trailing = "\n"
        self._undo_stack = []
        self._redo_stack = []
        self._clean_snapshot = None

    def load(self, filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                text = f.read()
            self._orig_indent = _detect_indent(text)
            self._orig_trailing = _detect_trailing_newline(text)
            self.data = json.loads(text)
            self.filepath = filepath
            self._undo_stack.clear()
            self._redo_stack.clear()
            self.mark_clean()
            return True
        except Exception:
            self.data = None
            self.filepath = None
            return False

    def reload(self):
        if self.filepath:
            return self.load(self.filepath)
        return False

    def is_loaded(self):
        return self.data is not None

    def is_modified(self):
        if self.data is None:
            return False
        return self._snapshot_sig(self.data) != self._clean_snapshot

    def _snapshot_sig(self, data):
        return json.dumps(data, ensure_ascii=False, sort_keys=True)

    def mark_clean(self):
        self._clean_snapshot = (
            self._snapshot_sig(self.data) if self.data is not None else None
        )

    def push_snapshot(self):
        """在执行变更前调用，压入当前数据副本供撤销。"""
        if self.data is None:
            return
        self._undo_stack.append(copy.deepcopy(self.data))
        self._redo_stack.clear()

    def undo(self):
        if not self._undo_stack:
            return False
        self._redo_stack.append(copy.deepcopy(self.data))
        self.data = self._undo_stack.pop()
        return True

    def redo(self):
        if not self._redo_stack:
            return False
        self._undo_stack.append(copy.deepcopy(self.data))
        self.data = self._redo_stack.pop()
        return True

    def can_undo(self):
        return bool(self._undo_stack)

    def can_redo(self):
        return bool(self._redo_stack)

    def save(self, backup_dir):
        if self.data is None or not self.filepath:
            return False
        if backup_dir:
            os.makedirs(backup_dir, exist_ok=True)
            if os.path.exists(self.filepath):
                ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                base = os.path.basename(self.filepath)
                backup_path = os.path.join(backup_dir, f"{base}.{ts}.bak")
                try:
                    shutil.copy2(self.filepath, backup_path)
                except Exception:
                    pass
        text = (
            json.dumps(
                self.data,
                ensure_ascii=False,
                indent=self._orig_indent,
            )
            + self._orig_trailing
        )
        with open(self.filepath, "w", encoding="utf-8", newline="") as f:
            f.write(text)
        self.mark_clean()
        return True
