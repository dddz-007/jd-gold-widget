# JD Gold Widget AI 构建指南

本文档描述**当前仓库已实现**的架构与约定，可直接发给 AI 编程助手，用于复刻、定制、修 bug 或移植。

> 仓库：`jd-gold-widget`。主平台为 **Windows 10/11**；以下行为以现有 Python 实现为准。

## 这个应用是什么

轻量级 Windows 桌面挂件，显示：

- 伦敦金价格 `USD/oz`
- 换算后的人民币金价 `CNY/g`
- 数据来源：`https://gold-price-pro.pf.jd.com/`

已实现能力：

- 无边框、置顶、可拖拽，重启后记住位置
- 自动刷新（页面 DOM mutation observer + 挂件侧轮询）
- 双击打开京东金价页；右键菜单可开自启 / 关自启 / 退出
- GUI 单实例（Windows mutex）
- 首次启动 GUI 时默认写入开机自启（可用 `JD_GOLD_SKIP_AUTO_STARTUP=1` 跳过；CLI 入口已设置该变量）
- 稳定 Chromium user-data 目录；占用时回退到固定备用 session，不创建随机 profile
- PyInstaller 单文件 `exe`：`JDGoldWidget.exe`（窗口）+ `JDGoldWidgetCli.exe`（控制台）
- 用户通过 **GitHub Releases** 下载 exe 使用；源码仓库不提交构建产物

## 当前架构（实现真相）

技术栈：

| 层 | 技术 |
| --- | --- |
| UI | Python 3.10+ + `tkinter`；Windows 色键透明（`-transparentcolor`）+ 近透明 hit overlay 接收鼠标 |
| 采价 | 隐藏 Chromium 远程调试 + DevTools WebSocket（`websocket-client`） |
| 数据目录 | `%LOCALAPPDATA%\JDGoldWidget`（位置 JSON、Chrome profile，不写项目目录） |
| 自启 | 用户 Startup 文件夹中的 `.vbs` 脚本 |
| 打包 | PyInstaller onefile → `dist\`；`scripts/build_windows.ps1`；tag `v*` 触发 GitHub Actions Release |

核心模块：

| 文件 | 职责 |
| --- | --- |
| `gold_widget_app.py` | 全部业务：浏览器发现/启动、CDP 读价、挂件 UI、自启、CLI 标志、单实例 |
| `gold_widget.pyw` | GUI 入口（无控制台） |
| `gold_widget_cli.py` | CLI 入口（设 `JD_GOLD_SKIP_AUTO_STARTUP`，调用 `main(allow_gui=False)`） |

运行时路径常量（以代码为准）：

- `APP_DIR` = `%LOCALAPPDATA%\JDGoldWidget`
- `widget_position.json`
- `jd-gold-chrome-profile`（主）
- `jd-gold-chrome-session`（备用；退出时可清理）
- Startup 脚本：`%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\JD Gold Widget AutoStart.vbs`

## 行为要求（须保持）

1. 启动启用远程调试的隐藏 Chromium，打开 `https://gold-price-pro.pf.jd.com/`。
2. 从 DOM 读取：
   - `.main-price-row .main-price-item .main-value`
   - `.update-time`
3. 页面内安装 mutation observer，数值变化时再推送给挂件。
4. 窗口置顶；位置持久化到 `APP_DIR`。
5. 右键菜单：打开京东金价页面 / 启用开机自启动 / 关闭开机自启动 / 退出。
6. CLI（打包体为 `JDGoldWidgetCli.exe`；源码为 `gold_widget_cli.py`）：
   - `--once`
   - `--startup-status`
   - `--enable-startup`
   - `--disable-startup`
   - `--runtime-check`
7. GUI 单实例；二次启动短生命周期 CLI 在主 profile 被占用时应回退固定备用 profile。
8. 启动时可清理残留隐藏浏览器进程与陈旧 `jd-gold-chrome-*` 目录（保留当前活动 profile）。

## Windows 兼容性（现有策略）

浏览器查找顺序覆盖：

- 环境变量：`JD_GOLD_BROWSER` / `CHROME_PATH` / `GOOGLE_CHROME_BIN`
- 常见 `Program Files` / `Program Files (x86)` 路径
- `%LOCALAPPDATA%` 下用户安装路径
- 注册表 `App Paths`（`chrome.exe` / `msedge.exe` / `brave.exe`）
- `PATH` 中的 `chrome` / `msedge` / `brave` / `chromium`

二进制名：`chrome.exe`、`msedge.exe`、`brave.exe`、`chromium.exe`。

无头启动：优先 `--headless=new`，失败再回退 `--headless --disable-gpu`。

profile 规则：

- 主目录固定：`jd-gold-chrome-profile`
- 占用或不兼容：固定备用 `jd-gold-chrome-session`
- **禁止**无限制随机 profile 目录

## 自启动策略

### Windows（当前实现）

Startup 文件夹中的 VBS，启动打包后的 GUI exe 或源码入口。注册表 `Run` 键不是当前默认，但可接受为备选。

### macOS（移植目标，仓库尚未实现）

使用 `~/Library/LaunchAgents/` 下 LaunchAgent plist。

## macOS 移植要点

保持相同行为，替换平台细节：

- 浏览器路径：`/Applications` 下 Chrome / Edge / Brave / Chromium
- 自启：LaunchAgent，不是 Windows Startup
- 右键同时绑定 `<Button-2>` / `<Button-3>`
- 打包：`py2app` 或 PyInstaller
- 运行时数据：宜用 `~/Library/Application Support/JDGoldWidget` 一类目录，勿写源码树

## 个人定制扩展点

设计上应便于：

- 更换数据源 URL / 选择器
- 更多价格或符号；涨跌变色
- 精简 / 完整模式；刷新间隔
- 点击穿透；系统托盘
- 价格提醒；诊断日志；导出 JSON/CSV

## 工程规范

- 逻辑集中在少量模块（当前以 `gold_widget_app.py` 为主）。
- URL、颜色、超时、选择器、路径用明确常量。
- 浏览器启动与 UI 入口分离（`.pyw` / CLI 薄包装）。
- 找不到浏览器时给出可读错误；`--runtime-check` 可诊断路径与自启状态。
- 退出时清理备用 session profile；保留稳定主 profile。
- 运行时数据只写 `%LOCALAPPDATA%\JDGoldWidget`（或目标平台等效目录）。
- 构建产物仅出现在 `build/`、`dist/`、`*.spec`，由 `.gitignore` 忽略，**不提交 Git**；对外分发走 GitHub Releases。

## 打包与分发（当前约定）

本地：

```powershell
python -m pip install -r requirements-dev.txt
powershell -ExecutionPolicy Bypass -File .\scripts\build_windows.ps1
```

产物：

- `dist\JDGoldWidget.exe`（`--windowed`）
- `dist\JDGoldWidgetCli.exe`（`--console`）

发版：

1. **推荐**：推送 `v*` tag → `.github/workflows/release.yml` 自动构建并上传上述两个 exe 到 Releases
2. **手动**：把 `dist\` 下两个 exe 作为 Release Assets 上传（步骤见 `docs/releasing.md`）

不要把 exe 放进仓库根目录或提交进 Git。

## 验收标准

全部满足才算完成：

1. 挂件置顶显示实时金价。
2. 双击打开京东金价页；右键菜单可用。
3. 重启后窗口位置保留。
4. 可启用 / 关闭开机自启。
5. `--once` 输出含价格字段的有效 JSON。
6. `--runtime-check` 输出浏览器路径、自启状态、profile 目录。
7. 多次启动不产生大量随机 `jd-gold-chrome-*` 目录。
8. 主 profile 被占用时，短生命周期运行可回退固定备用 profile。
9. 本地打包产物位于 `dist\`；用户可从 GitHub Releases 下载 `JDGoldWidget.exe` 直接使用。

## 建议文件结构（与仓库一致）

```text
jd-gold-widget/
  README.md
  requirements.txt
  requirements-dev.txt
  .gitignore
  gold_widget_app.py
  gold_widget.pyw
  gold_widget_cli.py
  docs/
    jd-gold-widget-ai-build-guide.md
    releasing.md
  scripts/
    build_windows.ps1
  .github/
    workflows/
      release.yml
```

本地打包后会出现（不入库）：

```text
  build/
  dist/
  *.spec
```

## 依赖

`requirements.txt`：

```text
websocket-client>=1.8
```

`requirements-dev.txt`：

```text
pyinstaller>=6.21
```

## 可直接复制给 AI 的提示词

```text
请基于现有 jd-gold-widget 仓库约定，用 Python + Tkinter 实现或修改 Windows 桌面挂件 “JD Gold Widget”。

已实现/必须对齐的需求：
- 显示伦敦金 USD/oz 与换算人民币 CNY/g
- 数据来源：https://gold-price-pro.pf.jd.com/
- 隐藏 Chromium + 远程调试 + DevTools WebSocket 读 DOM
- 页面 mutation observer，仅数值变化时更新
- 无边框、可拖拽、置顶；Windows 色键透明 + hit overlay
- 位置与 Chrome profile 写入 %LOCALAPPDATA%\JDGoldWidget
- 主 profile：jd-gold-chrome-profile；占用时固定备用：jd-gold-chrome-session；禁止随机临时 profile
- 双击打开来源页；右键：打开页面 / 启停开机自启 / 退出
- GUI 单实例（mutex）；首次 GUI 启动默认可写入 Startup 文件夹 VBS（JD_GOLD_SKIP_AUTO_STARTUP=1 可跳过）
- CLI：--once、--startup-status、--enable-startup、--disable-startup、--runtime-check
- 浏览器发现：Chrome/Edge/Brave/Chromium；环境变量 JD_GOLD_BROWSER、CHROME_PATH、GOOGLE_CHROME_BIN；覆盖 Program Files、LOCALAPPDATA、App Paths、PATH
- headless 优先 --headless=new，再回退 --headless --disable-gpu
- 入口：gold_widget.pyw（GUI）、gold_widget_cli.py（CLI）、逻辑集中在 gold_widget_app.py
- 打包：scripts/build_windows.ps1 → 仅输出到 dist/；CI 在 tag v* 时把 dist 下 exe 发到 GitHub Releases；构建产物不入库

若改为 macOS：
- LaunchAgent 替换 Startup VBS
- 增加 macOS 浏览器路径与 Application Support 数据目录
- 保持相同挂件行为与 CLI 命令

请返回最小必要改动的代码、简短 README，以及打包说明。
```
