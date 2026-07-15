# JD Gold Widget

一个用于跟踪京东实时金价页面的轻量级 Windows 桌面挂件。

它会以悬浮窗形式常驻桌面，自动读取京东金价页面中的实时数据，并显示：

- 伦敦金价格 `USD/oz`
- 换算后的人民币金价 `CNY/g`

适合希望在桌面上快速查看金价，而不想每次都手动打开网页的人。

## 功能特性

- 无边框、置顶悬浮窗
- 叠放在任务栏区域时仍保持最前；点击任务栏后会自动回到最前
- 重复启动不会新开进程，始终只保留一个挂件实例
- 支持鼠标拖拽移动
- 自动刷新页面数据
- 双击挂件可打开京东金价页面
- 右键菜单支持：
  - 打开页面
  - 启用开机自启动
  - 关闭开机自启动
  - 退出程序
- 支持命令行诊断模式
- 支持打包为单文件 `exe`
- 已修复随机生成大量 `jd-gold-chrome-*` 目录的问题
- 运行时数据不再污染仓库目录

## 项目结构

```text
jd-gold-widget/
  README.md
  .gitignore
  requirements.txt
  requirements-dev.txt
  gold_widget_app.py
  gold_widget.pyw
  gold_widget_cli.py
  docs/
    jd-gold-widget-ai-build-guide.md
    github-release-checklist.md
  scripts/
    build_windows.ps1
```

## 文件说明

- `gold_widget_app.py`
  项目的核心逻辑，包括浏览器发现、隐藏浏览器启动、DOM 读取、自动刷新、自启动管理、运行时检测和 Tk 界面逻辑。
- `gold_widget.pyw`
  GUI 入口，双击或命令行运行后会启动桌面挂件。
- `gold_widget_cli.py`
  CLI 入口，用于 `--once`、`--runtime-check`、自启动开关等诊断用途。
- `scripts/build_windows.ps1`
  Windows 打包脚本，会生成 GUI 版和 CLI 版单文件 `exe`。
- `docs/jd-gold-widget-ai-build-guide.md`
  面向 AI 的快速构建说明文档，可直接发给 AI 让其复刻或定制插件。
- `docs/github-release-checklist.md`
  面向 GitHub 发布的整理文档，包含首个提交信息建议、仓库描述建议和发布模板。

## 运行环境

推荐环境：

- Windows 10 / Windows 11
- Python `3.10+`
- 至少安装一个 Chromium 内核浏览器：
  - Google Chrome
  - Microsoft Edge
  - Brave
  - Chromium

## 安装依赖

基础运行依赖：

```powershell
python -m pip install -r requirements.txt
```

如果需要打包：

```powershell
python -m pip install -r requirements-dev.txt
```

## 源码运行

启动桌面挂件：

```powershell
python .\gold_widget.pyw
```

命令行单次抓取：

```powershell
python .\gold_widget_cli.py --once
```

查看运行环境信息：

```powershell
python .\gold_widget_cli.py --runtime-check
```

查看或管理自启动：

```powershell
python .\gold_widget_cli.py --startup-status
python .\gold_widget_cli.py --enable-startup
python .\gold_widget_cli.py --disable-startup
```

## 打包 Windows 可执行文件

执行：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build_windows.ps1
```

打包完成后会生成：

- `dist/JDGoldWidget.exe`
- `dist/JDGoldWidgetCli.exe`

说明：

- `JDGoldWidget.exe` 是日常给普通用户使用的 GUI 版本，双击即可
- `JDGoldWidgetCli.exe` 是命令行诊断版本，**不要双击运行**；请在终端里带参数使用，例如：

```powershell
.\dist\JDGoldWidgetCli.exe --once
.\dist\JDGoldWidgetCli.exe --runtime-check
```

如果挂件一直显示 `----.--` 或「获取失败」，通常是上次残留的隐藏 Chrome 占用了 profile。退出挂件后重新打开即可；程序启动时会自动清理这些残留进程。

## 运行时数据位置

为了避免仓库目录越来越乱，程序运行时数据不会写回项目目录，而是统一存放到：

```text
%LOCALAPPDATA%\JDGoldWidget
```

这里通常会包含：

- 浏览器 profile 数据
- 备用 session profile 数据
- 窗口位置配置

## 兼容性说明

本项目已经尽量提高在不同 Windows 机器上的可用性：

- 自动查找 Chrome / Edge / Brave / Chromium
- 会从 `Program Files`、`Program Files (x86)`、`LOCALAPPDATA`、`PATH`、注册表 `App Paths` 中查找浏览器
- 支持环境变量覆盖浏览器路径：
  - `JD_GOLD_BROWSER`
  - `CHROME_PATH`
  - `GOOGLE_CHROME_BIN`
- 浏览器启动时会优先尝试 `--headless=new`
- 如不兼容，会自动回退到 `--headless --disable-gpu`

但需要说明：

- 这不代表“所有历史 Windows 版本”都能保证运行
- 更准确的目标是“主流受支持的 Windows 10 / 11 环境”

## 当前已解决的问题

- 不再每次运行都生成一堆随机 `jd-gold-chrome-*` 目录
- 支持 Windows 开机自启动
- 打包版不会把运行时数据写进 PyInstaller 临时目录
- CLI 和 GUI 共用一套核心逻辑，行为更一致
- 项目目录已清理为适合 GitHub 托管的结构

## 适合 GitHub 提交的内容

建议提交这些：

- 源码文件
- `README.md`
- `requirements.txt`
- `requirements-dev.txt`
- `docs/`
- `scripts/`
- `.gitignore`

不建议提交这些：

- `build/`
- `dist/`
- `__pycache__/`
- `*.spec`
- 本地 profile / 位置文件
- 本机打包产物

## AI 构建说明

如果你想把这个项目发给 AI，让它快速构建 macOS 版、扩展功能版、或你的个人定制版，请直接使用：

- [docs/jd-gold-widget-ai-build-guide.md](./docs/jd-gold-widget-ai-build-guide.md)

## GitHub 发布建议

如果你准备把它放到 GitHub 并做第一版发布，可以直接参考：

- [docs/github-release-checklist.md](./docs/github-release-checklist.md)
