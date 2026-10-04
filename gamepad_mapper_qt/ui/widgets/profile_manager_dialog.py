# -*- coding: utf-8 -*-
"""方案管理对话框 —— 新建 / 重命名 / 删除 / 编辑门控进程

从前 process_names 只能手改 JSON；这里把它变成显式 UI。
对话框不碰 core：所有读写都走 MainWindow 暴露的 ui_* 窄接口，
返回 (是否成功, 失败原因)。
"""

from typing import List, Tuple

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem,
    QMessageBox, QPushButton, QVBoxLayout,
)


class ProfileManagerDialog(QDialog):
    def __init__(self, main_window, parent=None):
        super().__init__(parent or main_window)
        self._mw = main_window
        self.setWindowTitle("方案管理")
        self.resize(680, 460)
        self._setup_ui()
        self._reload_list()
        self._select_first()

    # ---------- UI ----------

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(12)

        intro = QLabel(
            "方案按前台进程门控生效。门控进程留空 = 对任意窗口生效。\n"
            "示例：Cursor.exe, agent.exe（逗号或换行分隔，不区分大小写）"
        )
        intro.setObjectName("dialogHint")
        intro.setWordWrap(True)
        root.addWidget(intro)

        body = QHBoxLayout()
        body.setSpacing(16)
        root.addLayout(body, stretch=1)

        self._list = QListWidget()
        self._list.setObjectName("profileList")
        self._list.currentItemChanged.connect(self._on_select)
        body.addWidget(self._list, stretch=2)

        form = QVBoxLayout()
        form.setSpacing(10)
        body.addLayout(form, stretch=3)

        name_label = QLabel("显示名")
        name_label.setObjectName("fieldLabel")
        form.addWidget(name_label)
        self._name_edit = QLineEdit()
        self._name_edit.setObjectName("inputLine")
        form.addWidget(self._name_edit)

        proc_label = QLabel("门控进程（逗号分隔，留空 = 任意窗口）")
        proc_label.setObjectName("fieldLabel")
        form.addWidget(proc_label)
        self._proc_edit = QLineEdit()
        self._proc_edit.setObjectName("inputLine")
        form.addWidget(self._proc_edit)

        self._meta = QLabel()
        self._meta.setObjectName("metaLabel")
        self._meta.setWordWrap(True)
        form.addWidget(self._meta)

        form.addStretch()

        btn_col = QHBoxLayout()
        create_btn = QPushButton("＋ 新建方案")
        create_btn.setObjectName("ghostBtn")
        create_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        create_btn.clicked.connect(self._on_create)
        btn_col.addWidget(create_btn)

        self._delete_btn = QPushButton("删除")
        self._delete_btn.setObjectName("clearBtn")
        self._delete_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._delete_btn.clicked.connect(self._on_delete)
        btn_col.addWidget(self._delete_btn)
        form.addLayout(btn_col)

        save_btn = QPushButton("保存修改")
        save_btn.setObjectName("dialogBtnPrimary")
        save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        save_btn.clicked.connect(self._on_save)
        form.addWidget(save_btn)

        close_btn = QPushButton("关闭")
        close_btn.setObjectName("dialogBtn")
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.clicked.connect(self.reject)
        form.addWidget(close_btn)

    # ---------- 数据 ----------

    def _reload_list(self) -> None:
        current = self._current_id()
        self._list.blockSignals(True)
        self._list.clear()
        for profile_id, display, processes, bound, is_active in self._mw.ui_profile_brief():
            mark = "  ●当前" if is_active else ""
            item = QListWidgetItem(f"{display}{mark}")
            item.setData(Qt.ItemDataRole.UserRole, profile_id)
            item.setToolTip("门控: " + (", ".join(processes) or "任意窗口"))
            self._list.addItem(item)
        self._list.blockSignals(False)
        if current:
            self._select_by_id(current)

    def _select_first(self) -> None:
        if self._list.count() > 0:
            self._list.setCurrentRow(0)

    def _current_id(self) -> str | None:
        item = self._list.currentItem()
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def _select_by_id(self, profile_id: str) -> None:
        for row in range(self._list.count()):
            if self._list.item(row).data(Qt.ItemDataRole.UserRole) == profile_id:
                self._list.setCurrentRow(row)
                return

    def _on_select(self, current, _previous) -> None:
        if current is None:
            return
        profile_id = current.data(Qt.ItemDataRole.UserRole)
        for pid, display, processes, bound, is_active in self._mw.ui_profile_brief():
            if pid == profile_id:
                self._name_edit.setText(display)
                self._proc_edit.setText(", ".join(processes))
                gate = "任意窗口" if not processes else ", ".join(processes)
                self._meta.setText(f"标识 {pid} · 已绑定 {bound} 个键 · 门控 {gate}")
                self._delete_btn.setEnabled(True)
                return

    @staticmethod
    def _split_processes(text: str) -> List[str]:
        parts = [p.strip() for chunk in text.split(",") for p in chunk.split("\n")]
        return [p for p in parts if p]

    # ---------- 操作 ----------

    def _on_create(self) -> None:
        from PyQt6.QtWidgets import QInputDialog

        profile_id, ok = QInputDialog.getText(
            self, "新建方案", "方案标识（英文/数字/下划线，作为配置文件名）："
        )
        if not ok:
            return
        display, ok = QInputDialog.getText(
            self, "新建方案", "显示名：", text=profile_id
        )
        if not ok:
            return
        ok_, error = self._mw.ui_create_profile(profile_id.strip(), display.strip())
        if not ok_:
            QMessageBox.warning(self, "无法创建", error)
            return
        self._reload_list()
        self._select_by_id(profile_id.strip())

    def _on_save(self) -> None:
        profile_id = self._current_id()
        if profile_id is None:
            return
        ok_, error = self._mw.ui_rename_profile(profile_id, self._name_edit.text().strip())
        if not ok_:
            QMessageBox.warning(self, "无法保存", error)
            return
        ok_, error = self._mw.ui_set_profile_processes(
            profile_id, self._split_processes(self._proc_edit.text())
        )
        if not ok_:
            QMessageBox.warning(self, "无法保存", error)
            return
        self._reload_list()
        self._select_by_id(profile_id)

    def _on_delete(self) -> None:
        profile_id = self._current_id()
        if profile_id is None:
            return
        ok, error = self._mw.ui_delete_profile(profile_id)
        if not ok:
            QMessageBox.warning(self, "无法删除", error)
            return
        self._reload_list()
        self._select_first()
