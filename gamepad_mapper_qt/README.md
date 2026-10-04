# Gamepad Vibe Controller (PyQt6)

多 Harness 并行时用手柄只控制**一个** Agent 窗口；也可切换 **浏览器** / **通用** 方案做日常操作。鼠标层在所有方案间保持一致。

## 快速使用

```powershell
cd E:\Project\Python\pythonProject\gamepad_mapper_qt
.\.venv\Scripts\Activate.ps1
python main.py
```

1. 顶部选择方案：**Cursor / Claude Code / … / 浏览器 / 通用**
2. 连接手柄，点击 **⟳ 刷新**
3. Agent 类：用 **LT 短按** 聚焦目标窗口；浏览器类：打开 Chrome/Edge 等即可
4. **▶ 启动映射**（或 **Start** / **F9**）
5. 顶栏 **已对准** 后操作；**通用** 方案对任意前台窗口生效

## 界面与交互

- **手柄图即编辑面**：点图上的按键 → 右侧绑定面板就地编辑（搜索目录 / 实体按键捕获 / 清除），不再弹全屏对话框。可绑定 / 有冲突 / 已占用三种状态直接显示在面板横幅里。
- **运行中即时改绑**：映射运行时也能改键，改动即时生效 —— 引擎会先释放被改槽位按住的输出，不会卡键。
- **实体按键即点即亮**：面板处于编辑态且映射未运行时，按手柄上的键，界面自动切到对应槽位（Steam Input 式）。
- **轻量撤销**：误改 / 误清按 **Ctrl+Z** 或点 **↩ 撤销** 恢复（栈深 20,只在当前方案内）。
- **方案管理**：顶栏 **⚙** 新建 / 重命名 / 删除方案、编辑门控进程 `process_names`（不必再手改 JSON）。
- **三态亮度**：画布右上状态胶囊 + 整体亮度回答「现在按手柄有没有用」—— 已停止轻压暗（改绑就在这时做），门未对准明显压暗，映射中全亮且边缘呼吸。
- **设置**：底栏 **⚙ 设置** 里调摇杆灵敏度 / 阈值（按方案保存）。

## 统一鼠标层（所有方案相同）

无论当前是 Agent 还是浏览器，以下操作在各方案中行为一致：

| 输入 | 动作 |
|------|------|
| **左摇杆** | 鼠标移动 |
| **L3** | 鼠标左键（按住/松开） |
| **右摇杆 上下** | 滚轮 |
| **R3** | 鼠标右键 |
| **RT 按住** | 右 Ctrl 语音（`ctrl_r`） |

方案 JSON 里不必重复写 L3/R3；加载时自动合并。若要关闭统一鼠标层，在 profile 中设 `"universal_mouse": false`。

## Agent 方案（Harness）

前台闸门：只有 `process_names` 匹配的进程在前台时才发键。

| 输入 | 动作 |
|------|------|
| **A** | 批准 |
| **B** | 拒绝 |
| **X** | 软打断（Esc） |
| **Y** | 下一会话（ctrl+tab） |
| **LB / RB** | 上/下一会话 |
| **LT 短按** | 聚焦当前 Harness |
| **LT 长按** | 循环切换方案 |
| **Back** | 硬停（ctrl+c） |
| **Start** | 启停映射 |
| **D-Pad 上** | Plan/权限 shift+tab |
| **D-Pad 下** | 发送 |

## 浏览器方案

匹配 Chrome、Edge、Firefox、Brave 等；鼠标层与 Agent 相同，面键为浏览快捷键：

| 输入 | 动作 |
|------|------|
| **A** | Enter（激活链接/按钮） |
| **B** | 后退（alt+left） |
| **X** | 刷新（F5） |
| **Y** | 新标签（ctrl+t） |
| **LB / RB** | 上/下一标签 |
| **Back** | 关闭标签（ctrl+w） |
| **D-Pad 上/下** | Page Up / Page Down |
| **D-Pad 左/右** | 后退 / 前进 |

## 通用方案

`process_names` 为空 → **任意前台窗口** 均生效，适合其它软件的基础操作：

| 输入 | 动作 |
|------|------|
| **A** | Enter |
| **B** | Esc |
| **X** | Space |
| **Y** | Tab |
| **LB / RB** | Shift+Tab / Tab |
| **D-Pad** | 方向键 |

可按需在 UI 里改绑定；保存时不会重复写入统一鼠标层项。

## 配置文件

```
config/
├── app_state.json
└── profiles/
    ├── cursor.json
    ├── claude_code.json
    ├── codex.json
    ├── zcode.json
    ├── dsh.json
    ├── browser.json      # 浏览器
    └── general.json      # 通用（无闸门）
```

每套 profile 字段：`process_names`、`mappings`、`threshold`、`mouse_sensitivity`（左摇杆鼠标，5–50）、`scroll_sensitivity`（右摇杆滚轮，0.1–2.0）、`stick_deadzone`、`universal_mouse`。

`process_names` 与绑定在 UI 里改（顶栏 **⚙** / 点手柄图）；滑杆调优在底栏 **⚙ 设置**，按方案保存；勾选 **开机自启动** / **启动后自动开始映射**（Windows 注册表，当前用户）。

## 开机自启动

1. 勾选底部 **「开机自启动」** → 登录 Windows 后自动打开本程序（无黑框窗口）
2. 勾选 **「启动后自动开始映射」** → 程序打开约 1 秒后，若手柄已连接且当前方案有映射，则自动开始映射
3. 设置保存在 `config/app_state.json`

## 快捷键

| 按键 | 功能 |
|------|------|
| F9 | 启动/停止映射 |
| Start（手柄） | 启动/停止映射 |
| Ctrl+Z | 撤销上一次绑定改动 |
| Esc（绑定面板） | 退出捕获 / 收起面板 |

## 技术栈

PyQt6 · pygame · pynput · ctypes
