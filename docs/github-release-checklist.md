# GitHub 发布检查清单

这个文档用于帮助你把 `jd-gold-widget` 整理后发布到 GitHub。

## 首个提交信息建议

推荐首个提交信息：

```text
feat: 初始化 JD Gold Widget，支持桌面挂件、自启动与 Windows 打包
```

英文备选：

```text
feat: initialize JD Gold Widget with Windows widget, startup support, and packaging scripts
```

## 仓库名称建议

推荐：

```text
jd-gold-widget
```

## 仓库简介建议

可以直接填：

```text
一个轻量级的 Windows 桌面挂件，用于跟踪京东实时金价。
```

英文备选：

```text
A lightweight Windows desktop widget for tracking JD real-time gold prices.
```

## 仓库标签建议

建议添加这些 topics：

- `python`
- `tkinter`
- `windows`
- `desktop-widget`
- `gold-price`
- `automation`
- `pyinstaller`

## 首次提交前检查

- 确认 `README.md` 已更新为当前项目结构
- 确认 `docs/jd-gold-widget-ai-build-guide.md` 已在仓库内
- 确认 `.gitignore` 已忽略 `build/`、`dist/`、`__pycache__/`、`*.spec`
- 确认没有提交本地 profile 数据和位置文件
- 确认运行时数据已写入 `%LOCALAPPDATA%\JDGoldWidget`
- 确认 `scripts/build_windows.ps1` 可以正常打包

## 推荐提交顺序

如果你想让提交历史更清晰，建议分成这几次：

1. `feat: 初始化挂件核心逻辑与运行时`
2. `feat: 增加 Windows 自启动与浏览器兼容回退`
3. `chore: 调整项目结构以便发布到 GitHub`
4. `docs: 增加中文 README 与 AI 构建指南`

如果你不想拆分，直接一次提交也完全可以。

## 建议发布内容

如果你做 GitHub Release，建议上传：

- `JDGoldWidget.exe`
- `JDGoldWidgetCli.exe`

## Release 标题建议

```text
v0.1.0 - 首个公开版本
```

英文备选：

```text
v0.1.0 - First public release
```

## Release 说明模板

```text
## 亮点

- 新增轻量级 Windows 桌面悬浮挂件，用于跟踪京东金价
- 支持 Windows 登录后自动启动
- 自动发现 Chromium 浏览器，并带有回退逻辑
- 修复不受控地生成大量 jd-gold-chrome-* 目录的问题
- 增加 PyInstaller 打包脚本，可生成 Windows 单文件可执行程序
- 整理仓库结构，便于发布到 GitHub

## 包含文件

- JDGoldWidget.exe：GUI 桌面挂件
- JDGoldWidgetCli.exe：命令行诊断与实用工具

## 说明

- 推荐用于 Windows 10 / Windows 11
- 需要安装基于 Chromium 的浏览器，例如 Chrome 或 Edge
- 运行时数据存放在 %LOCALAPPDATA%\\JDGoldWidget
```

## 可继续增强的发布项

后续如果你想让仓库更完整，可以再加：

- `LICENSE`
- GitHub Actions 自动打包
- 应用图标 `.ico`
- 截图或演示 GIF
- `CHANGELOG.md`
- 中英文双语 README

## 当前最推荐的下一步

1. 先提交源码和文档
2. 本地运行一次打包脚本
3. 上传到 GitHub
4. 再创建一个 `v0.1.0` Release，并附上两个 `exe`
