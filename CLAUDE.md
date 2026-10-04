# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 仓库构成

仓库里只有一个项目：`gamepad_mapper_qt/`，PyQt6 手柄映射器 v2.0。根目录只放 `CLAUDE.md`、`CONTEXT.md` 和 `docs/`。

早期的 tkinter 版本（`gamepad_mapper/`，v1 / v2 / v3.5 Pro）曾以嵌套 Git 仓库的形式存在于此，remote 指向 `longsongline/gamepad_mapper`，现已从本地删除。它从未被根仓库跟踪，所以本仓库历史里找不到它。

## 常用命令（gamepad_mapper_qt）

项目自带 venv（Python 3.11），依赖已装好：

```powershell
cd E:\Project\Python\pythonProject\gamepad_mapper_qt; .\.venv\Scripts\Activate.ps1; python main.py
```

```bash
gamepad_mapper_qt/.venv/Scripts/python.exe gamepad_mapper_qt/main.py
```

```bash
gamepad_mapper_qt/.venv/Scripts/pip.exe install -r gamepad_mapper_qt/requirements.txt
```

跑测试（pytest，配置在 `gamepad_mapper_qt/pytest.ini`）：

```bash
gamepad_mapper_qt/.venv/Scripts/python.exe -m pytest
```

```bash
gamepad_mapper_qt/.venv/Scripts/python.exe -m pytest tests/test_edge_detector.py -k 长按
```

测试覆盖 `core/gamepad_input.py`（边沿判定与接线）、`core/mapping_engine.py`（按键/鼠标输出、闸门、RT 语音、失败上报）和 `core/keyboard_output.py`（组合键回滚），全部不需要手柄也不需要 Qt。

`MappingEngine` 和 `KeyboardOutput` 都接受注入的依赖，测试传假对象即可 —— 靠鸭子类型，没有定义 Protocol。`MouseOutput` 在 `__init__` 里抓 `ctypes.windll`，`KeyboardOutput` 默认 new 一个 pynput controller（可用 `controller=` 覆盖），但测试里都不需要构造它们。

**仍无覆盖**：`ui/` 全部、`config_store` 的存取往返、`window_focus` 的 Win32 调用。

没有 linter、没有 CI，也没有打包步骤（不出 exe，直接跑源码）。开发依赖在 `requirements-dev.txt`。

Windows 专属：`core/mouse_output.py`、`core/window_focus.py`、`core/autostart.py` 直接调 `ctypes.windll` 和 `winreg`，非 Windows 上 import 即失败。

## 架构（gamepad_mapper_qt）

### 逻辑槽位索引是全局契约

`core/slots.py` 的 `SLOTS` 是一个 24 项元组，**它的下标就是整个系统里唯一的按键标识符**：profile JSON 的 `mappings` 键、`MappingTable` 的行号、`MappingEngine._mappings` 的键、`InputFrame.pressed` 的下标，全都是同一套 0–23。

因此**往 `SLOTS` 中间插入或重排任何一项，都会静默改写磁盘上所有 profile 的含义**。要加按键只能追加到末尾。

每个 `Slot` 一条记录带齐名字、颜色、面板坐标和渲染形态。颜色从前以**名字**为键（`BTN_COLOR`），改一个按钮的名字颜色就静默丢失退回默认色；现在同处一条记录，不可能失联。面板坐标放在 `core/` 是有意的分层妥协 —— 拆去 `ui/` 就等于把一个槽位重新劈成两半。

`render` 只有两种：`button`（带标签圆形，槽位 0–15）和 `dot`（摇杆方向小点，16–23）。LT/RT 的指示灯读 `pressed[6]/[7]`，与其余槽位一致 —— 从前它们单独读 `lt_value/rt_value > 0.5`，在轴数 <6 的手柄上会导致指示灯永不点亮。

注意 20–23 的顺序是 `Right Stick Up / Down / Right / Left`——右摇杆的左右和左摇杆（18=Left, 19=Right）是反的，这是有意的，`joystick_manager.poll()` 与之对应。

每个 `Slot` 还带一个 `source`，声明它的状态从手柄哪里读：`button`（物理按钮，由 `apply_hardware_buttons` 按布局填）、`hat`（十字键，axis 0=x/1=y 加正负号）、`stick`（摇杆方向，与 threshold 比）、`trigger`（扳机，归一化后 >0.5）。`poll()` 遍历 `SLOTS` 按声明取值，不再是硬编码过程。**加一个槽位现在只改 `SLOTS` 一处。**

轴是成对出现的（左摇杆 0/1、右摇杆 2/3、扳机 4/5），取用某个轴要求它所在的那一对都存在 —— `轴数 < (axis // 2 + 1) * 2` 就跳过，与改造前的判断一致。

### 硬件 → 逻辑的转换层

`core/button_map.py` 负责把 pygame 的物理按钮号翻译成逻辑槽位。Xbox 布局下物理 6/7（Back/Start）落到逻辑 8/9，物理 8/9（L3/R3）落到逻辑 10/11；而逻辑 6/7（LT/RT）**不来自按钮，来自 axis 4/5**，由 `JoystickManager.poll()` 单独填充。手柄名称经 `detect_layout()` 判定用 `xbox` 还是 `direct` 布局。

### 唯一的 tick 与唯一的采样点

`MainWindow._tick`（`QTimer`，16ms ≈ 60Hz，主线程）是全应用唯一的循环。`GamepadInput.tick()` 是唯一调用 `JoystickManager.poll()` 的地方 —— 所有消费者读**同一帧**：

```
frame = input.tick(now)
engine.consume(frame)      # 键盘/鼠标输出
_分派保留槽位(frame)         # LT / Start
_更新表格高亮(frame)
每两帧 → panel.update_state(frame)   # 重绘维持 30Hz
```

`MappingEngine` 是 `QObject` 不是 `QThread`，自己不计时也不轮询。`JoystickManager` 里的 `RLock` 现在已无必要（只剩单线程调用），留着无害。

**不要再引入第二个 `poll()` 调用点** —— 之前正是两条回路各自采样、各自维护上一帧状态，导致 LT 长短按完全失效、Start 一半几率不响应。

### 边沿判定集中在 GamepadInput

`core/gamepad_input.py` 拥有全部边沿逻辑，对外只有 `tick(now) -> InputFrame` 一个方法。`InputFrame` 同时携带边沿集合（`just_pressed` / `just_released` / `just_long_pressed` / `just_short_released`）和连续量（`pressed` / `left_stick` / `right_stick` / `lt_value` / `rt_value`）。

长按阈值通过构造参数配置（`long_press_after={IDX_LT: LT_LONG_PRESS_SEC}`），module 因此不需要知道 LT 是什么意思 —— **语义在 `MainWindow`，判定在 module**。

内部的 `EdgeDetector` 是私有 seam，只有 `tests/test_edge_detector.py` 穿过它。改边沿逻辑先补测试。

**所有 24 个槽位共用一条按下/抬起规则**（`just_pressed` → press，`just_released` → release）。历史上 `MappingEngine` 里有个 `bi < 12` 的分支看似区分两种语义，实为同一逻辑的两种写法，已删除。

### 被硬编码占用的槽位（不走通用映射路径）

| 槽位 | 行为 | 位置 |
|------|------|------|
| 6 (LT) | 引擎跳过。短按 → 聚焦当前方案窗口；长按 ≥ `LT_LONG_PRESS_SEC`(0.4s) → 循环切方案 | `MainWindow._分派保留槽位` |
| 7 (RT) | 硬编码按住 `VOICE_KEY`（`ctrl_r`），**profile 里给 7 配的映射不生效** | `MappingEngine._处理语音` |
| 9 (Start) | 被主循环吃掉用于启停映射 | `MainWindow._分派保留槽位` |
| 10 / 11 (L3/R3) | 由 `UNIVERSAL_MOUSE_MAPPINGS` 提供哨兵动作 `@mouse:left` / `@mouse:right`，引擎特判为鼠标按下/抬起 | `constants.py` + `MappingEngine._按下` |

左摇杆 → 鼠标移动、右摇杆 Y → 滚轮同样**硬编码在 `MappingEngine._处理鼠标` 里，不由映射表驱动**；映射表中 16–23 的摇杆方向槽位是另一套并行机制（可同时把左摇杆映射成 WASD，但鼠标移动依然在跑）。

### 前台闸门（gate）

`MappingEngine` 每 tick 调用 `_gate_checker`，实际指向 `MainWindow._check_gate` → `window_focus.is_process_foreground(profile.process_names)`。

**`process_names` 为空列表时闸门恒开**（`general` / 通用方案就靠这个对任意窗口生效）。闸门关闭时引擎会 `release_all()` 并抬起鼠标键，防止切窗时按键卡住。

### ActiveProfile 拥有当前方案

`core/active_profile.py` 是**唯一持有「当前生效方案」的地方**。对外接口很窄：

```python
ActiveProfile(profile_id, on_save_failed=回调)
  .mappings / .profile / .savable          # 只读
  .switch_to(id)
  .set_mappings(dict)
  .set_threshold / set_mouse_sensitivity / set_scroll_sensitivity
```

它藏起来三件事：

**统一鼠标层的合并/剥离往返** —— 读时 `effective_mappings()` 合并 `UNIVERSAL_MOUSE_MAPPINGS`，写时 `_剥离统一鼠标层()` 把取值相同的条目剔除。**这一对互逆操作必须待在同一个 module 里**，分开放会让「合并再剥离等于原样」这个不变式无人负责（历史上剥离曾在 `MainWindow`）。所以磁盘 JSON 里正常看不到 `"10"` / `"11"`，只有改绑成别的值才出现。profile 设 `"universal_mouse": false` 可整体关掉。

**落盘时机** —— 任何 setter 立即写盘，调用方不需要知道 `save()` 存在。代价是拖一次滑块会写几十次文件；这是有意接受的，换取「没有未保存状态」这个简化。

**落盘失败** —— 文件损坏时 `save_profile` 抛 `ConfigNotSavable`，`ActiveProfile` 内部捕获去重后走 `on_save_failed` 回调，**对调用方永不抛**。否则每个 setter 的调用点都得处理一个它没请求的操作的失败模式。

`MainWindow` 因此不再持有 `_mappings`（那曾是个纯中间变量，三次读取全是转手推给别人），`_apply_profile` 收敛成 `switch_to` + `_把方案推给各消费者()`。`MappingTable` 和 `MappingEngine` 仍各持一份工作副本 —— widget 需要自己的显示模型，引擎在 60Hz 热路径上不能每帧跨对象查询 —— 但**只从 ActiveProfile 这一个源头拿**。

### 持久化

`core/config_store.py` 是唯一的读写入口：

- `config/profiles/<id>.json` —— 每个方案一份；`PROFILE_ORDER` 决定下拉框顺序，磁盘上多出来的 json 会排在后面
- `config/app_state.json` —— 当前方案 id、开机自启、启动后自动映射

保存时机很密：改映射、改滑块、切方案、关窗口都会立刻 `save_profile()`，没有"取消"路径；误改靠 `MappingHistory`（Ctrl+Z，仅绑定变更、不跨方案）兜底。

### 读不了的文件绝不写回去

`HarnessProfile` 和 `AppState` 都有 `savable` 字段。加载时区分三种情况：

| 情况 | `load_profile` 返回 |
|------|------|
| 文件不存在 | `None`（合法，新方案） |
| 文件存在但 JSON/OS 读取失败 | `savable=False` 的对象 |
| 正常 | `savable=True` 的对象 |

`save_profile` / `save_app_state` 在碰磁盘之前检查 `savable`，为假则抛 `ConfigNotSavable`。

**守卫故意放在写入侧而不是读取侧**：即使调用方忘记检查，文件也不会被覆盖。曾经的 bug 正是「损坏 → 静默替换成空 profile → 下一次保存覆盖原文件」，六个保存触发点无一幸免。

UI 侧全部经由 `MainWindow._安全保存()` 这一个漏斗接住 `ConfigNotSavable`，按消息去重（拖一次滑块会触发几十次保存）。`_apply_profile` 里包住 `save_active_profile_id` 是必须的 —— 它每次切方案和启动都跑，不接住会让应用启动失败。

损坏的方案在下拉框里显示 `⚠ <id>（读取失败）`。`_提示损坏方案()` 在 `__init__` 里 `_refresh_joystick()` **之后**再调一次，否则状态栏的解释会被「手柄已连接」冲掉。

### 键名格式

映射值是 pynput 风格的小写键名，`+` 分隔组合键（如 `ctrl+shift+tab`）。`KeyboardOutput._resolve_key` 里有一张别名表（`pageup`→`page_up`、`win`/`super`→`cmd`）。新增可绑定按键通常要同时动三处：`constants.KEYBOARD_KEYS`、`key_bind_dialog._QT_KEY_MAP`（Qt 键码 → pynput 名）、以及必要时的别名表。`_KEY_PRESETS` 里放的是对话框抓不到的系统级快捷键（Win+Tab 等），只能预设写入。

### 开机自启

`core/autostart.py` 写 HKCU 的 `Software\Microsoft\Windows\CurrentVersion\Run`，值名 `GamepadVibeController`，命令里把 `python.exe` 换成同目录 `pythonw.exe` 以免弹黑框。

**注册表是「是否开机自启」的真相源**，不是 `app_state.json`。启动时 `_load_app_settings` 读 `is_enabled()` 决定复选框状态，并把 JSON 同步过来。从前反过来 —— JSON 说启用就无条件重写注册表，于是用户在任务管理器里禁用启动项后，下次开应用又被静默加回去。

仅当注册表**已启用**时才重写一次，以刷新命令里的解释器与源码路径（移动项目或重建 venv 后自愈），同时不会把用户的禁用覆盖回去。

## UI 层

`ui/main_window.py` 是全部胶水：持有 joystick / input / keyboard / mouse / engine，widget 只通过 pyqtSignal 往上报，不直接碰 core。样式由 `ui/styles/tokens.py` 的 `build_qss()` 在运行时生成（配色/字号/圆角的唯一事实源），没有静态 qss 文件。界面文案与注释用中文，**标识符用英文**。

### 手柄图是绑定的编辑面

`GamepadCanvas` 不只是状态显示，**点它上面的键就是绑定入口**：`mousePressEvent` → `slots.hit_test()` → 按 `binding_kind()` 分流（可绑选中右侧 BindingPanel / 冲突先提示再选中 / 保留在面板里说明占用）。`BindingPanel`（`ui/widgets/binding_panel.py`）就地编辑，三态提示的展示位在这里；捕获逻辑在 `ui/widgets/key_capture.py`，引擎不持 UI，宿主把 QKeyEvent 转进去。`GamepadPanel` 只做信号转发，不参与命中 —— 它的坐标系是容器的，拿去做 hit_test 会全错（这个错误犯过一次）。

图按 Xbox 真实布局绘制，轮廓是**基本图形求并集**（中央圆角矩形 ∪ 两个护翼圆 ∪ 两条胶囊握把），不是手调贝塞尔 —— 后者每个控制点都要靠眼睛，改起来没有着力点。

**x、y、半径一律按画框宽度缩放**，画框是固定 1.42:1 的居中内接矩形。曾经 x 用宽度、y 用高度各自缩放，窗口一变形 ABXY 的菱形、D-Pad 的十字、摇杆的扇形就全被拉扁。

右侧列表是「已绑定」视图，默认只列真正绑了的（约 12 行），不是固定 24 行。

### 拿真实 config 跑冒烟测试会改写你的方案

`ActiveProfile` 任何变更立即落盘，所以构造 `MainWindow` 的探针脚本必须先 `monkeypatch` 掉 `config_store._profiles_dir` 和 `_app_state_path` 到临时目录。**已经因此丢过一次真实数据**（`general.json` 里的一条映射被删）。

## Agent skills

### Issue tracker

本地 markdown —— issue 以文件形式存在 `.scratch/<feature>/` 下，不使用 GitHub Issues（本机也未安装 `gh`）。见 `docs/agents/issue-tracker.md`。

### Triage labels

五个 triage 角色使用中文标签：`待分拣` / `缺信息` / `可交agent` / `需人工` / `不做`。见 `docs/agents/triage-labels.md`。

### Domain docs

单上下文：根目录一份 `CONTEXT.md` + `docs/adr/`，两者都尚未创建，由 `/domain-modeling` 按需懒创建。见 `docs/agents/domain.md`。
