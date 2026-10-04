# -*- coding: utf-8 -*-
"""主窗口"""

import os
import re
import time

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QShortcut, QKeySequence
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QFrame, QMessageBox, QComboBox, QCheckBox,
)

from core.button_map import IDX_LT, IDX_START
from core.constants import (
    APP_NAME, APP_VERSION,
    LT_LONG_PRESS_SEC, PROFILE_ORDER,
)
from ui.styles.tokens import build_qss
from core import paths
from core.active_profile import ActiveProfile
from core.mapping_history import MappingHistory
from core.slots import CONFLICT, RESERVED, binding_kind, conflict_reason
from core.autostart import (
    apply_enabled as apply_autostart,
    is_enabled as autostart_enabled,
    is_supported as autostart_supported,
)
from core.config_store import (
    AppState,
    ConfigNotSavable,
    HarnessProfile,
    delete_profile,
    list_profile_ids,
    load_app_state,
    load_active_profile_id,
    load_profile,
    save_app_state,
    save_active_profile_id,
    save_profile,
)
from core.gamepad_input import GamepadInput
from core.joystick_manager import JoystickManager
from core.keyboard_output import KeyboardOutput
from core.mapping_engine import MappingEngine
from core.mouse_output import MouseOutput
from core.window_focus import focus_process, is_process_foreground
from ui.app_icon import make_gamepad_icon, make_gamepad_pixmap
from ui.tray import Tray
from ui.widgets.binding_panel import BindingPanel
from ui.widgets.gamepad_panel import GamepadPanel
from ui.widgets.mapping_table import MappingTable
from ui.widgets.profile_manager_dialog import ProfileManagerDialog
from ui.widgets.settings_dialog import SettingsDialog
from ui.widgets.status_bar import StatusBar
from ui.widgets.status_pill import StatusPill


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{APP_NAME}  v{APP_VERSION}")
        # 任务栏 / Alt+Tab 的图标，跟托盘同一枚手柄徽章；启停映射时换色
        self.setWindowIcon(make_gamepad_icon(False))
        self.setMinimumSize(1180, 800)
        self.resize(1280, 880)

        self._joystick = JoystickManager()
        self._input = GamepadInput(
            self._joystick,
            long_press_after={IDX_LT: LT_LONG_PRESS_SEC},
        )
        self._keyboard = KeyboardOutput()
        self._mouse = MouseOutput()
        self._engine = MappingEngine(self._keyboard, self._mouse)
        self._active: ActiveProfile | None = None
        self._profile_ids: list[str] = []
        self._gate_open = False
        self._app_state = AppState()
        self._frame_count = 0
        self._reported_refusals: set[str] = set()
        self._history = MappingHistory()
        self._really_quitting = False      # 区分「关窗口」和「真退出」

        self._load_styles()
        self._setup_ui()
        self._connect_signals()
        self._load_app_settings()
        self._load_profiles()
        self._refresh_joystick()
        self._warn_unreadable_profile()   # 必须在 _refresh_joystick 之后，否则会被它冲掉

        # 全应用唯一的 tick：60Hz 采样，面板每两帧重绘一次
        self._poll_timer = QTimer(self)
        self._poll_timer.timeout.connect(self._tick)
        self._poll_timer.start(16)

        self._tray = Tray(self)
        self._tray.show_requested.connect(self._restore_from_tray)
        self._tray.toggle_mapping_requested.connect(self._toggle_mapping)
        self._tray.quit_requested.connect(self._quit_for_real)
        self._engine.state_changed.connect(self._tray.set_running)
        self._tray.show()

        QTimer.singleShot(800, self._try_auto_start_mapping)

    # ---------- 托盘 ----------

    def _restore_from_tray(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def _quit_for_real(self):
        """托盘菜单的「退出」—— 只有这条路和 F9 之外的真退出才会关进程"""
        self._really_quitting = True
        self.close()

    def _load_styles(self):
        # 样式由 ui/styles/tokens.py 生成 —— 配色只有这一份事实
        self.setStyleSheet(build_qss())

    def _setup_ui(self):
        central = QWidget()
        central.setObjectName("centralWidget")
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        header = QFrame()
        header.setObjectName("headerFrame")
        header.setFixedHeight(76)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(24, 0, 24, 0)
        header_layout.setSpacing(16)

        logo = QLabel()
        logo.setPixmap(make_gamepad_pixmap(running=False, size=44))
        header_layout.addWidget(logo)

        title_col = QVBoxLayout()
        title_col.setSpacing(2)
        title = QLabel(APP_NAME)
        title.setObjectName("titleLabel")
        subtitle = QLabel("Harness / 浏览器 / 通用 · 统一鼠标层")
        subtitle.setObjectName("subtitleLabel")
        title_col.addWidget(title)
        title_col.addWidget(subtitle)
        header_layout.addLayout(title_col)

        header_layout.addStretch()

        harness_label = QLabel("当前方案")
        harness_label.setObjectName("fieldLabel")
        header_layout.addWidget(harness_label)

        self._profile_combo = QComboBox()
        self._profile_combo.setMinimumWidth(200)
        self._profile_combo.setCursor(Qt.CursorShape.PointingHandCursor)
        self._profile_combo.currentIndexChanged.connect(self._on_profile_changed)
        header_layout.addWidget(self._profile_combo)

        header_layout.addSpacing(8)

        self._gate_pill = StatusPill("未对准", "warn")
        header_layout.addWidget(self._gate_pill)

        self._conn_pill = StatusPill("未连接", "warn")
        header_layout.addWidget(self._conn_pill)

        refresh_btn = QPushButton("⟳  刷新")
        refresh_btn.setObjectName("refreshBtn")
        refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        refresh_btn.clicked.connect(self._refresh_joystick)
        header_layout.addWidget(refresh_btn)

        manage_btn = QPushButton("⚙")
        manage_btn.setObjectName("iconBtn")
        manage_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        manage_btn.setToolTip("管理方案：新建 / 重命名 / 删除 / 门控进程")
        manage_btn.clicked.connect(self._open_profile_manager)
        header_layout.addWidget(manage_btn)

        root.addWidget(header)

        body = QHBoxLayout()
        body.setContentsMargins(20, 20, 20, 12)
        body.setSpacing(20)

        self._gamepad_panel = GamepadPanel()
        body.addWidget(self._gamepad_panel, stretch=4)

        right_col = QVBoxLayout()
        right_col.setSpacing(12)

        # 绑定面板在上（选中槽位后就地编辑），列表在下（结果视图）
        self._binding_panel = BindingPanel()
        right_col.addWidget(self._binding_panel)

        table_header = QHBoxLayout()
        table_header.setSpacing(12)
        table_title = QLabel("已绑定")
        table_title.setObjectName("sectionLabel")
        table_header.addWidget(table_title)
        table_header.addStretch()

        focus_btn = QPushButton("聚焦窗口")
        focus_btn.setObjectName("refreshBtn")
        focus_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        focus_btn.clicked.connect(self._focus_current_harness)
        table_header.addWidget(focus_btn)

        self._show_unbound_check = QCheckBox("显示未绑定")
        self._show_unbound_check.setObjectName("optionCheck")
        self._show_unbound_check.setCursor(Qt.CursorShape.PointingHandCursor)
        self._show_unbound_check.setToolTip(
            "默认只列出已绑定的键；勾选后显示其余可绑槽位（摇杆方向在图上不好点）"
        )
        self._show_unbound_check.toggled.connect(
            lambda on: self._mapping_table.set_show_unbound(on)
        )
        table_header.addWidget(self._show_unbound_check)

        self._undo_btn = QPushButton("↩ 撤销")
        self._undo_btn.setObjectName("ghostBtn")
        self._undo_btn.setEnabled(False)
        self._undo_btn.setToolTip("恢复上一次的绑定改动（Ctrl+Z）")
        self._undo_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._undo_btn.clicked.connect(self._undo_mapping_change)
        table_header.addWidget(self._undo_btn)

        clear_all_btn = QPushButton("全部清除")
        clear_all_btn.setObjectName("clearBtn")
        clear_all_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        clear_all_btn.clicked.connect(self._clear_all_mappings)
        table_header.addWidget(clear_all_btn)
        right_col.addLayout(table_header)

        self._mapping_table = MappingTable()
        right_col.addWidget(self._mapping_table, stretch=1)

        body.addLayout(right_col, stretch=6)
        root.addLayout(body, stretch=1)

        self._status_bar = StatusBar()
        root.addWidget(self._status_bar)

    def _connect_signals(self):
        self._mapping_table.bind_requested.connect(self._request_bind)
        self._mapping_table.row_selected.connect(self._on_table_row_selected)
        # 每个信号只接一处：_on_slot_clicked 内部会调 _request_bind，
        # 再直连一次就会弹两个编辑视图（表现为要取消两次）。
        self._gamepad_panel.slot_clicked.connect(self._on_slot_clicked)
        self._gamepad_panel.slot_refused.connect(self._on_slot_refused)
        self._binding_panel.bind_committed.connect(self._on_bind_committed)
        self._binding_panel.bind_cleared.connect(self._on_bind_cleared)
        self._binding_panel.selection_changed.connect(self._on_panel_selection_changed)
        self._mapping_table.mapping_changed.connect(self._on_mapping_changed)
        self._status_bar.start_stop_clicked.connect(self._toggle_mapping)
        self._status_bar.settings_clicked.connect(self._open_settings)
        self._status_bar.launch_at_startup_changed.connect(self._on_launch_at_startup_changed)
        self._status_bar.auto_start_mapping_changed.connect(self._on_auto_start_mapping_changed)

        self._engine.state_changed.connect(self._on_engine_state)
        self._engine.error_occurred.connect(self._on_engine_error)
        self._engine.gate_changed.connect(self._on_gate_changed)

        shortcut = QShortcut(QKeySequence("F9"), self)
        shortcut.activated.connect(self._toggle_mapping)

        undo_shortcut = QShortcut(QKeySequence("Ctrl+Z"), self)
        undo_shortcut.activated.connect(self._undo_mapping_change)

    def _load_app_settings(self) -> None:
        self._app_state = load_app_state()
        self._status_bar.set_auto_start_mapping(self._app_state.auto_start_mapping)

        # 注册表是「是否开机自启」的真相源，不是 app_state.json。
        # 从前反过来：JSON 说启用就无条件重写注册表，于是用户在任务管理器里
        # 禁用启动项后，下次开应用又被静默加回去。
        enabled = autostart_enabled() if autostart_supported() else False
        self._status_bar.set_launch_at_startup(enabled)
        if enabled != self._app_state.launch_at_startup:
            self._app_state.launch_at_startup = enabled
            self._save_app_settings()

        # 仍然重写一次，但只在确实已启用时 —— 保留「移动项目后路径自愈」，
        # 同时不会把用户的禁用覆盖回去。
        if enabled:
            try:
                apply_autostart(True)
            except OSError as exc:
                self._status_bar.set_status(f"自启动注册失败: {exc}")

    def _save_app_settings(self) -> None:
        self._save_guarded(lambda: save_app_state(self._app_state))

    def _on_launch_at_startup_changed(self, enabled: bool) -> None:
        if not autostart_supported():
            self._status_bar.set_launch_at_startup(False)
            QMessageBox.warning(self, "提示", "开机自启动目前仅支持 Windows。")
            return
        try:
            apply_autostart(enabled)
        except OSError as exc:
            self._status_bar.set_launch_at_startup(not enabled)
            QMessageBox.warning(self, "自启动失败", str(exc))
            return
        self._app_state.launch_at_startup = enabled
        self._save_app_settings()
        self._status_bar.set_status("已开启开机自启动" if enabled else "已关闭开机自启动")

    def _on_auto_start_mapping_changed(self, enabled: bool) -> None:
        self._app_state.auto_start_mapping = enabled
        self._save_app_settings()
        self._status_bar.set_status("已开启启动后自动映射" if enabled else "已关闭启动后自动映射")

    def _try_auto_start_mapping(self) -> None:
        if not self._app_state.auto_start_mapping or self._engine.is_active:
            return
        if not self._joystick.connected:
            self._joystick.refresh()
        self._start_mapping(silent=True)

    def _load_profiles(self):
        self._reload_profile_combo()
        self._apply_profile(self._profile_combo.currentData() or PROFILE_ORDER[0])

    def _reload_profile_combo(self) -> None:
        """从磁盘重建方案下拉框 —— 启动、增删改方案后都走这里"""
        self._profile_ids = list_profile_ids()
        active_id = load_active_profile_id()
        if active_id not in self._profile_ids:
            self._profile_ids = list(PROFILE_ORDER)
            active_id = self._profile_ids[0]

        self._profile_combo.blockSignals(True)
        self._profile_combo.clear()
        for pid in self._profile_ids:
            profile = load_profile(pid)
            if profile and not profile.savable:
                label = f"⚠ {pid}（读取失败）"
            elif profile:
                label = profile.display_name
            else:
                label = pid
            self._profile_combo.addItem(label, pid)
            if profile:
                gate = ", ".join(profile.process_names) or "任意窗口"
                self._profile_combo.setItemData(
                    self._profile_combo.count() - 1,
                    f"门控: {gate}",
                    Qt.ItemDataRole.ToolTipRole,
                )
        idx = self._profile_ids.index(active_id) if active_id in self._profile_ids else 0
        self._profile_combo.setCurrentIndex(idx)
        self._profile_combo.blockSignals(False)

    def _open_profile_manager(self) -> None:
        ProfileManagerDialog(self).exec()

    def _open_settings(self) -> None:
        """滑杆走对话框；信号连的是与旧底栏相同的处理器，改动即时生效"""
        profile = self._active.profile
        dialog = SettingsDialog(
            threshold=profile.threshold,
            mouse_sensitivity=profile.mouse_sensitivity,
            scroll_sensitivity=profile.scroll_sensitivity,
            parent=self,
        )
        dialog.threshold_changed.connect(self._on_threshold_changed)
        dialog.mouse_sensitivity_changed.connect(self._on_mouse_sensitivity_changed)
        dialog.scroll_sensitivity_changed.connect(self._on_scroll_sensitivity_changed)
        dialog.exec()

    # ---------- 方案管理（对话框只走这几个 ui_* 接口，不直接碰 core） ----------

    def ui_profile_brief(self):
        """(id, 显示名, 门控进程, 绑定数, 是否当前) 的列表"""
        briefs = []
        for pid in self._profile_ids:
            profile = load_profile(pid)
            if profile is None:
                continue
            briefs.append((
                pid,
                profile.display_name,
                list(profile.process_names),
                len(profile.mappings),
                self._active is not None and pid == self._active.profile.id,
            ))
        return briefs

    def ui_create_profile(self, profile_id: str, display_name: str):
        profile_id = (profile_id or "").strip()
        if not profile_id:
            return False, "方案标识不能为空"
        if not re.fullmatch(r"[A-Za-z0-9_\-]+", profile_id):
            return False, "标识只能用英文、数字、下划线或连字符（它同时是配置文件名）"
        if profile_id in self._profile_ids:
            return False, f"方案 {profile_id} 已存在"
        try:
            save_profile(HarnessProfile(id=profile_id, display_name=display_name or profile_id))
        except ConfigNotSavable as exc:
            return False, str(exc)
        except OSError as exc:
            return False, f"写入失败: {exc}"
        self._reload_profile_combo()
        return True, ""

    def ui_rename_profile(self, profile_id: str, display_name: str):
        display_name = (display_name or "").strip()
        if not display_name:
            return False, "显示名不能为空"
        if self._active and profile_id == self._active.profile.id:
            self._active.set_display_name(display_name)
        else:
            profile = load_profile(profile_id)
            if profile is None:
                return False, f"方案 {profile_id} 不存在"
            profile.display_name = display_name
            try:
                save_profile(profile)
            except ConfigNotSavable as exc:
                return False, str(exc)
        self._reload_profile_combo()
        return True, ""

    def ui_set_profile_processes(self, profile_id: str, names):
        cleaned = [n.strip() for n in names if n and n.strip()]
        if self._active and profile_id == self._active.profile.id:
            self._active.set_process_names(cleaned)
            self._engine.set_process_names(cleaned)
            self._update_gate_display()
        else:
            profile = load_profile(profile_id)
            if profile is None:
                return False, f"方案 {profile_id} 不存在"
            profile.process_names = cleaned
            try:
                save_profile(profile)
            except ConfigNotSavable as exc:
                return False, str(exc)
        self._reload_profile_combo()
        return True, ""

    def ui_delete_profile(self, profile_id: str):
        if len(self._profile_ids) <= 1:
            return False, "至少要保留一个方案"
        if self._active and profile_id == self._active.profile.id:
            # 先切走再删，别让 ActiveProfile 悬在已删除的方案上
            others = [p for p in self._profile_ids if p != profile_id]
            was_running = self._engine.is_active
            if was_running:
                self._engine.stop_mapping()
            self._apply_profile(others[0])
            if was_running:
                self._engine.start_mapping()
        delete_profile(profile_id)
        self._reload_profile_combo()
        return True, ""

    def _apply_profile(self, profile_id: str) -> None:
        if self._active is None:
            self._active = ActiveProfile(profile_id, on_save_failed=self._report_save_refused)
        else:
            self._active.switch_to(profile_id)

        # 撤销栈不跨方案 —— 上一个方案的快照还原到这个方案是灾难
        self._history.clear()
        self._update_undo_enabled()

        # app_state.json 损坏时这里会拒写；不能让它把切方案和启动一起搞挂
        self._save_guarded(lambda: save_active_profile_id(profile_id))
        self._push_profile_to_consumers()

        self._warn_unreadable_profile()

    def _warn_unreadable_profile(self) -> None:
        """当前方案文件读不了时，把原因写到状态栏

        在 __init__ 末尾要再调一次：_refresh_joystick 会写状态栏，
        否则启动时这条解释会被「手柄已连接」冲掉。
        """
        if self._active and not self._active.savable:
            self._status_bar.set_status(
                f"⚠ config/profiles/{self._active.profile.id}.json 读取失败（JSON 格式有误）。"
                "映射显示为空，已停止写入以免覆盖你原有的配置。修复文件后重启生效。"
            )

    def _apply_stick_settings(self, profile: HarnessProfile) -> None:
        self._engine.set_mouse_settings(
            profile.mouse_sensitivity,
            profile.stick_deadzone,
            profile.scroll_sensitivity,
        )

    def _check_gate(self) -> bool:
        if not self._active:
            return True
        return is_process_foreground(self._active.profile.process_names)

    def _update_gate_display(self) -> None:
        """门控状态 → 顶栏胶囊

        每 tick 都会被调（引擎不跑时引擎侧不查），但 StatusPill 对
        相同的 (文字, 色调) 直接忽略，不会再每帧 setStyleSheet。
        """
        open_ = self._check_gate()
        self._gate_open = open_
        name = self._active.profile.display_name if self._active else ""
        if self._active and not self._active.profile.process_names:
            self._gate_pill.set_state(f"{name} · 任意窗口", "ok")
        elif open_:
            self._gate_pill.set_state(f"已对准 {name}", "ok")
        else:
            self._gate_pill.set_state(f"未对准 {name}", "warn")

    def _push_profile_to_consumers(self) -> None:
        """ActiveProfile 是唯一源头；table 和 engine 各持一份工作副本"""
        profile = self._active.profile
        mappings = self._active.mappings

        self._joystick.threshold = profile.threshold
        self._mapping_table.load_mappings(mappings)
        self._binding_panel.set_mappings(mappings)
        self._gamepad_panel.set_bindings(mappings)
        self._engine.set_mappings(mappings)
        self._engine.set_process_names(profile.process_names)
        self._apply_stick_settings(profile)
        self._engine.set_gate_checker(self._check_gate)
        self._update_gate_display()
        self._update_liveness()
        self._warn_unreadable_profile()

    def _report_save_refused(self, message: str) -> None:
        self._status_bar.set_status(message)

    def _on_profile_changed(self, index: int) -> None:
        if index < 0:
            return
        was_running = self._engine.is_active
        if was_running:
            self._engine.stop_mapping()
        profile_id = self._profile_combo.itemData(index)
        if profile_id:
            self._apply_profile(profile_id)
        if was_running:
            self._engine.start_mapping()

    def _cycle_profile(self) -> None:
        if not self._profile_ids:
            return
        current_id = self._profile_combo.currentData() or self._profile_ids[0]
        idx = self._profile_ids.index(current_id) if current_id in self._profile_ids else 0
        next_idx = (idx + 1) % len(self._profile_ids)
        self._profile_combo.setCurrentIndex(next_idx)
        self._status_bar.set_status(
            f"已切换 Harness → {self._profile_combo.currentText()}"
        )

    def _focus_current_harness(self) -> None:
        if not self._active or not self._active.profile.process_names:
            self._status_bar.set_status("当前方案未配置 process_names")
            return
        if focus_process(self._active.profile.process_names):
            self._status_bar.set_status(f"已聚焦 {self._active.profile.display_name}")
        else:
            self._status_bar.set_status(
                f"未找到 {self._active.profile.display_name} 窗口，请检查 process_names"
            )
        self._update_gate_display()

    def _save_guarded(self, action) -> bool:
        """执行一次保存；文件读不了时不写入，只提示一次

        六个保存触发点全部经由这里，所以拒写的上报也只需要写在这一处。
        去重是必须的：拖一次滑块会触发几十次保存。
        """
        try:
            action()
            return True
        except ConfigNotSavable as exc:
            message = str(exc)
            if message not in self._reported_refusals:
                self._reported_refusals.add(message)
                self._status_bar.set_status(message)
            return False

    def _refresh_joystick(self):
        if self._engine.is_active:
            self._engine.stop_mapping()

        connected = self._joystick.refresh()
        # 手柄没插着，「启动后自动开始映射」无从谈起
        self._status_bar.set_auto_start_mapping_enabled(connected)
        if connected:
            name = self._joystick.name
            self._conn_pill.set_state(f"已连接 · {name[:24]}", "ok")
            self._gamepad_panel.set_info(name, True)
            self._status_bar.set_status("手柄已连接")
        else:
            self._conn_pill.set_state("未连接", "warn")
            self._gamepad_panel.set_info("未检测到手柄", False)
            self._status_bar.set_status("请连接手柄后点击刷新")

    def _tick(self):
        """全应用唯一的 tick：一次采样，所有消费者读同一帧"""
        frame = self._input.tick(time.monotonic())
        if not frame.connected:
            return

        self._engine.consume(frame)
        self._dispatch_reserved_slots(frame)
        self._update_table_highlight(frame)
        self._update_gate_display()

        self._frame_count += 1
        if self._frame_count % 2 == 0:
            self._gamepad_panel.update_state(frame)

    def _dispatch_reserved_slots(self, frame) -> None:
        """保留槽位的语义留在这里；边沿判定由 GamepadInput 负责"""
        if IDX_START in frame.just_pressed:
            self._toggle_mapping()
        if IDX_LT in frame.just_long_pressed:
            self._cycle_profile()
        if IDX_LT in frame.just_short_released:
            self._focus_current_harness()

    def _update_table_highlight(self, frame) -> None:
        for slot in frame.just_pressed:
            if slot not in (IDX_LT, IDX_START):
                self._mapping_table.highlight_button(slot)
                self._follow_physical_press(slot)
        for slot in frame.just_released:
            if slot not in (IDX_LT, IDX_START):
                self._mapping_table.clear_highlight_if(slot)

    def _follow_physical_press(self, slot: int) -> None:
        """实体按键即点即亮：面板已在编辑态时，按手柄键直接切到那个槽位

        只在编辑态跟随 —— 否则平时按手柄，面板会自己乱跳；
        运行中绝不跟随，那时每个按键都是真实输出。
        """
        if self._engine.is_active:
            return
        if binding_kind(slot) == RESERVED:
            return
        if self._binding_panel.current_slot is None:
            return
        self._binding_panel.select_slot(slot)

    def _update_liveness(self) -> None:
        """画布三态亮度：运行且对准=全亮 / 运行但门关=半暗 / 停止=全暗"""
        if self._engine.is_active:
            state = "active" if self._gate_open else "gated"
        else:
            state = "idle"
        self._gamepad_panel.set_liveness(state)

    def _on_slot_clicked(self, slot: int) -> None:
        """点手柄图上的键 —— 这是绑定的主入口"""
        if binding_kind(slot) == CONFLICT:
            self._status_bar.set_status(f"注意：{conflict_reason(slot)}")
        self._request_bind(slot)

    def _on_slot_refused(self, slot: int) -> None:
        """保留槽位不给绑 —— 面板里说明它被什么占用"""
        self._request_bind(slot)

    def _on_table_row_selected(self, slot: int) -> None:
        self._request_bind(slot)

    def _request_bind(self, slot: int) -> None:
        """打开一个槽位的绑定编辑；运行中也允许，改动即时生效"""
        self._binding_panel.set_live_hint(self._engine.is_active)
        self._binding_panel.select_slot(slot)

    def _on_panel_selection_changed(self, slot) -> None:
        """面板选中谁，画布呼吸圈和列表就同步谁（含取消选中 None）"""
        self._gamepad_panel.set_selected(slot)
        self._mapping_table.select_slot(slot)

    def _on_bind_committed(self, slot: int, combo: str) -> None:
        self._mapping_table.set_mapping(slot, combo)

    def _on_bind_cleared(self, slot: int) -> None:
        self._mapping_table.clear_slot(slot)

    def _on_mapping_changed(self):
        old = self._active.mappings
        new = self._mapping_table.get_mappings()
        if new != old:
            self._history.push(old)
            # 运行中改绑：先释放被改槽位按住的旧输出，再换表，防止旧键卡死
            self._engine.release_slots(
                {s for s in set(old) | set(new) if old.get(s) != new.get(s)}
            )
        self._apply_mappings(new)
        self._update_undo_enabled()

    def _apply_mappings(self, mappings) -> None:
        """把一张映射表落到 ActiveProfile / 引擎 / 三个视图 —— 改绑与撤销共用"""
        self._active.set_mappings(mappings)
        merged = self._active.mappings
        self._engine.set_mappings(merged)
        self._mapping_table.load_mappings(merged)
        self._binding_panel.set_mappings(merged)
        self._gamepad_panel.set_bindings(merged)

    def _undo_mapping_change(self):
        previous = self._history.undo()
        if previous is None:
            return
        current = self._active.mappings
        self._engine.release_slots(
            {s for s in set(current) | set(previous) if current.get(s) != previous.get(s)}
        )
        self._apply_mappings(previous)
        self._update_undo_enabled()
        self._status_bar.set_status("已撤销上一次绑定改动")

    def _update_undo_enabled(self):
        self._undo_btn.setEnabled(self._history.can_undo)

    def _on_threshold_changed(self, value: float):
        self._joystick.threshold = value
        self._active.set_threshold(self._joystick.threshold)

    def _on_mouse_sensitivity_changed(self, value: float):
        self._active.set_mouse_sensitivity(value)
        self._apply_stick_settings(self._active.profile)

    def _on_scroll_sensitivity_changed(self, value: float):
        self._active.set_scroll_sensitivity(value)
        self._apply_stick_settings(self._active.profile)

    def _clear_all_mappings(self):
        reply = QMessageBox.question(
            self, "确认", "清除所有按键映射？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._mapping_table.clear_all()

    def _toggle_mapping(self):
        if self._engine.is_active:
            self._engine.stop_mapping()
        else:
            self._start_mapping()

    def _start_mapping(self, silent: bool = False):
        # 源头是 ActiveProfile，不是表格 —— 从前这两处各取各的，
        # 只靠 _on_mapping_changed 每次同步才没出事
        mappings = self._active.mappings
        if not self._joystick.connected:
            if silent:
                self._status_bar.set_status("自动映射：未检测到手柄")
            else:
                QMessageBox.warning(self, "警告", "没有检测到手柄，请先连接并刷新！")
            return
        if not mappings:
            if silent:
                self._status_bar.set_status("自动映射：当前方案无按键映射")
            else:
                QMessageBox.warning(self, "警告", "请先绑定至少一个按键映射！")
            return

        self._engine.set_mappings(mappings)
        self._engine.set_gate_checker(self._check_gate)
        self._engine.start_mapping()
        if silent:
            self._status_bar.set_status("已自动开始映射")
        else:
            self._status_bar.set_status("映射运行中… (F9 / Start 停止)")

    def _on_engine_state(self, running: bool):
        self._status_bar.set_running(running)
        self._binding_panel.set_live_hint(running)
        self._update_liveness()
        # 任务栏图标跟托盘同色：运行中亮青，停止时灰
        self.setWindowIcon(make_gamepad_icon(running))
        if not running:
            self._status_bar.set_status("已停止")

    def _on_engine_error(self, msg: str):
        self._status_bar.set_status(f"错误: {msg}")

    def _on_gate_changed(self, open_: bool, _label: str):
        self._gate_open = open_
        self._update_gate_display()
        self._update_liveness()

    def closeEvent(self, event):
        # 点 × 只收进托盘：映射还在跑，关掉窗口不该把它一起关了。
        # 真退出只能走托盘菜单的「退出」。
        if not self._really_quitting:
            event.ignore()
            self.hide()
            self._tray.notify("已收到托盘，映射继续运行；双击图标可恢复窗口")
            return

        self._poll_timer.stop()
        self._engine.stop_mapping()
        self._engine.terminate_engine()
        self._save_app_settings()
        self._joystick.shutdown()
        self._tray.hide()
        event.accept()
