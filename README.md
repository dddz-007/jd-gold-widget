# JD Gold Widget

Windows 桌面悬浮挂件，实时显示京东金价：伦敦金 `USD/oz` 与换算人民币 `CNY/g`。

## 下载使用（推荐）

无需安装 Python，从 [Releases](https://github.com/dddz-007/jd-gold-widget/releases/latest) 下载后直接运行：

| 文件 | 说明 |
| --- | --- |
| **JDGoldWidget.exe** | 桌面挂件，双击即可使用 |
| JDGoldWidgetCli.exe | 命令行工具，请在终端运行（勿双击） |

系统要求：Windows 10 / 11，并已安装 Chrome / Edge / Brave / Chromium 之一。

首次运行若被 Windows SmartScreen 拦截，选择「仍要运行」即可（开源项目本地打包，无数字签名）。

## 功能

- 无边框置顶、可拖拽，记住窗口位置
- 自动刷新；双击打开京东金价页
- 单实例运行；右键可开关开机自启、退出
- 可打包为单文件 `exe`

## 源码运行

环境：Windows 10 / 11，Python 3.10+，Chromium 内核浏览器。

```powershell
python -m pip install -r requirements.txt
python .\gold_widget.pyw
```

常用 CLI：

```powershell
python .\gold_widget_cli.py --once
python .\gold_widget_cli.py --runtime-check
python .\gold_widget_cli.py --enable-startup
python .\gold_widget_cli.py --disable-startup
```

## 自行打包

```powershell
python -m pip install -r requirements-dev.txt
powershell -ExecutionPolicy Bypass -File .\scripts\build_windows.ps1
```

生成 `dist/JDGoldWidget.exe`（GUI）与 `dist/JDGoldWidgetCli.exe`（命令行）。

推送形如 `v0.1.0` 的 tag 后，GitHub Actions 会自动打包并发布到 Releases。

## 说明

运行时数据在 `%LOCALAPPDATA%\JDGoldWidget`，不会写入项目目录。

若显示 `----.--` 或获取失败，退出后重新打开即可（启动时会清理残留隐藏 Chrome 进程）。

可用环境变量指定浏览器：`JD_GOLD_BROWSER` / `CHROME_PATH` / `GOOGLE_CHROME_BIN`。
