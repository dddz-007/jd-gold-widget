# JD Gold Widget AI 构建指南

本文档可直接发给 AI 编程助手，让其快速复刻、定制或移植 `jd-gold-widget` 桌面挂件。

## 这个插件是什么

构建一个轻量级桌面挂件，用于显示：

- 伦敦金价格 `USD/oz`
- 换算后的人民币金价 `CNY/g`
- 数据来源页面：`https://gold-price-pro.pf.jd.com/`

挂件应当：

- 悬浮在桌面最上层
- 无边框
- 可拖拽
- 记住窗口位置
- 自动刷新
- 双击或菜单操作可打开京东金价页面
- 支持开机自启动
- 避免生成大量随机 Chrome profile 目录
- 复用一个稳定的浏览器 profile；仅在必要时使用一个固定的备用 session profile

## 当前推荐架构

使用 Python + Tkinter + Chromium DevTools Protocol。

推荐技术栈：

- Python `3.10+`
- `tkinter` 负责挂件 UI
- `websocket-client` 负责 DevTools WebSocket 通信
- 基于 Chromium 的浏览器负责隐藏页面渲染：
  - Google Chrome
  - Microsoft Edge
  - Chromium
  - Brave

## 行为要求

请严格实现以下功能：

1. 应用启动一个启用远程调试的隐藏 Chromium 浏览器。
2. 应用打开 `https://gold-price-pro.pf.jd.com/`。
3. 应用从以下 DOM 节点读取数值：
   - `.main-price-row .main-price-item .main-value`
   - `.update-time`
4. 应用在页面中安装 DOM observer，仅在数值变化时更新挂件。
5. 应用窗口必须保持置顶。
6. 应用将窗口位置保存到本地 JSON 文件或应用数据目录。
7. 应用支持右键菜单，包含：
   - `打开京东金价页面`
   - `启用开机自启动`
   - `关闭开机自启动`
   - `退出`
8. 应用支持以下 CLI 命令：
   - `--once`
   - `--startup-status`
   - `--enable-startup`
   - `--disable-startup`
   - `--runtime-check`

## Windows 兼容性目标

目标环境：主流受支持的 Windows 桌面系统，尤其是 Windows 10 和 Windows 11。

为尽量提高兼容性：

- 在以下位置搜索浏览器可执行文件：
  - `Program Files`
  - `Program Files (x86)`
  - `LOCALAPPDATA`
  - Windows 注册表 `App Paths`
  - `PATH`
- 支持这些浏览器二进制文件：
  - `chrome.exe`
  - `msedge.exe`
  - `brave.exe`
  - `chromium.exe`
- 支持环境变量覆盖：
  - `JD_GOLD_BROWSER`
  - `CHROME_PATH`
  - `GOOGLE_CHROME_BIN`
- 启动无头模式时优先尝试：
  - `--headless=new`
  - 不兼容时回退到 `--headless --disable-gpu`
- 使用稳定的主 profile 目录，例如：
  - `jd-gold-chrome-profile`
- 若主 profile 被占用，则使用一个固定备用 profile，例如：
  - `jd-gold-chrome-session`
- 切勿生成无限制的随机 profile 目录。

## 自启动策略

### Windows

可优先采用以下任一方式：

- 用户 Startup 文件夹脚本
- `HKCU\Software\Microsoft\Windows\CurrentVersion\Run`

使用 Startup 文件夹实现更易维护，也可以接受。

### macOS

使用 LaunchAgent plist，路径位于：

- `~/Library/LaunchAgents/`

## macOS 移植要求

如果要重建为 macOS 版本，请保持相同行为，但调整这些细节：

- 浏览器路径发现应包含：
  - `/Applications/Google Chrome.app/Contents/MacOS/Google Chrome`
  - `/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge`
  - `/Applications/Brave Browser.app/Contents/MacOS/Brave Browser`
  - `/Applications/Chromium.app/Contents/MacOS/Chromium`
- 自启动应使用 LaunchAgent，而不是 Windows Startup 文件夹
- 右键行为可能需要同时支持这两种 Tk 事件：
  - `<Button-2>`
  - `<Button-3>`
- 打包可采用：
  - `py2app`
  - `PyInstaller`

## 个人定制扩展点

在设计代码时，应便于做这些定制：

- 更换数据源 URL
- 增加更多价格或符号
- 根据涨跌改变颜色
- 增加精简模式和完整模式
- 增加刷新间隔设置
- 增加点击穿透模式
- 增加系统托盘或菜单栏模式
- 增加价格提醒阈值
- 增加日志与诊断模式
- 增加导出为 JSON 或 CSV

## 工程规范

- 将代码保持在一个小模块，或非常少的一组模块中。
- 对 URL、颜色、超时、选择器和路径使用明确常量。
- 让浏览器启动逻辑与 UI 入口分离。
- 让运行时检查可从 CLI 调用。
- 找不到兼容浏览器时，给出可读的错误信息。
- 退出时清理备用 session profile。
- 不要静默创建大量临时目录。
- 为挂件主进程保留稳定的主 profile。

## 验收标准

只有满足以下全部条件，才算构建完成：

1. 启动挂件后，能看到显示实时金价的置顶悬浮窗。
2. 双击可打开京东金价页面。
3. 右键可打开可用的操作菜单。
4. 重启后窗口位置仍会保留。
5. 可以启用和关闭开机自启动。
6. `--once` 能输出包含价格字段的有效 JSON。
7. `--runtime-check` 能输出浏览器路径、自启动状态和 profile 目录信息。
8. 多次启动不会生成大量随机 `jd-gold-chrome-*` 目录。
9. 若已有挂件实例占用主浏览器 profile，第二次短生命周期运行可以回退到固定备用 profile。

## 建议文件结构

```text
project/
  README.md
  requirements.txt
  requirements-dev.txt
  gold_widget_app.py
  gold_widget.pyw
  gold_widget_cli.py
  docs/
    jd-gold-widget-ai-build-guide.md
  scripts/
    build_windows.ps1
```

## 建议依赖

`requirements.txt`

```text
websocket-client>=1.8
```

`requirements-dev.txt`

```text
pyinstaller>=6.21
```

## 可直接复制给 AI 的提示词

```text
请使用 Python 和 Tkinter 构建一个名为“JD Gold Widget”的桌面挂件。

需求：
- 显示伦敦金价格（USD/oz）和换算后的人民币金价（CNY/g）
- 数据来源：https://gold-price-pro.pf.jd.com/
- 启动一个启用远程调试的隐藏 Chromium 浏览器
- 从渲染后的 DOM 中读取价格
- 在页面中安装 mutation observer，仅在数值变化时更新
- 无边框、可拖拽、置顶窗口
- 将挂件位置持久化到应用数据目录
- 双击打开来源页面
- 右键菜单：打开京东金价页面 / 启用开机自启动 / 关闭开机自启动 / 退出
- CLI 命令：--once、--startup-status、--enable-startup、--disable-startup、--runtime-check
- 浏览器发现必须支持 Chrome、Edge、Chromium 和 Brave
- 浏览器查找必须覆盖 Program Files、Program Files (x86)、LOCALAPPDATA、PATH 以及 Windows App Paths 注册表
- 支持环境变量覆盖：JD_GOLD_BROWSER、CHROME_PATH、GOOGLE_CHROME_BIN
- 优先尝试 --headless=new，然后回退到 --headless --disable-gpu
- 复用名为 jd-gold-chrome-profile 的稳定浏览器 profile 目录
- 若该 profile 被占用，回退到固定备用 profile：jd-gold-chrome-session
- 切勿创建大量随机临时 profile 目录
- 增加 Windows 开机自启动
- 保持实现尽量小、可读，并具备可上线使用的稳健性

如果改为面向 macOS 而不是 Windows：
- 用 LaunchAgent 替换 Windows 自启动逻辑
- 增加 macOS 浏览器路径发现
- 保持相同的挂件行为和 CLI 命令

请返回代码、简短 README，以及打包说明。
```
