# 发布到 GitHub Releases

目标：用户打开仓库 → 进入 **Releases** → 点击下载 `JDGoldWidget.exe` → 双击即可使用。

## 推荐：打 tag，Actions 自动发版

仓库已配置 [`.github/workflows/release.yml`](../.github/workflows/release.yml)。推送版本 tag 后会自动构建并上传两个 exe。

```powershell
# 1. 确认 master 已推到 GitHub，且本地改动已提交
git status

# 2. 打 tag（版本号自定，须以 v 开头）
git tag v0.1.0

# 3. 推送 tag
git push origin v0.1.0
```

几分钟后到仓库 **Releases** 页确认：

- 存在 Release `v0.1.0`
- Assets 中有 `JDGoldWidget.exe`、`JDGoldWidgetCli.exe`
- README 里的 [latest Release](https://github.com/dddz-007/jd-gold-widget/releases/latest) 可点开下载

## 手动发版（可选）

若不用 Actions，可在网页上操作：

1. 本地打包：

   ```powershell
   python -m pip install -r requirements-dev.txt
   powershell -ExecutionPolicy Bypass -File .\scripts\build_windows.ps1
   ```

2. GitHub 仓库页 → **Releases** → **Draft a new release**

3. 填写：

   | 字段 | 填什么 |
   | --- | --- |
   | **Choose a tag** | 新建如 `v0.1.0`（建议与本次发布一致） |
   | **Release title** | 如 `v0.1.0` 或 `JD Gold Widget v0.1.0` |
   | **Describe this release** | 简要变更说明（见下方模板） |
   | **Attach binaries** | 上传 `dist\JDGoldWidget.exe` 与 `dist\JDGoldWidgetCli.exe` |

4. 勾选 **Set as the latest release**（若适用）→ **Publish release**

### Release 说明模板

```markdown
## 下载说明

- **JDGoldWidget.exe**：桌面挂件，双击即可使用
- **JDGoldWidgetCli.exe**：命令行工具，请在终端运行（勿双击）

## 系统要求

- Windows 10 / 11
- 已安装 Chrome / Edge / Brave / Chromium 之一

## 本版变更

- （在此列出修复 / 功能）
```

## 只需上传哪些文件

| 上传 | 不上传 |
| --- | --- |
| `JDGoldWidget.exe` | 源码、`requirements*.txt` |
| `JDGoldWidgetCli.exe`（可选，给需要命令行的用户） | `build\`、`*.spec`、整个仓库 zip（除非你想附源码包） |

用户日常使用：**只下载 `JDGoldWidget.exe` 即可**。

## 不要做的事

- 不要把 `exe` / `build/` / `dist/` / `*.spec` 提交进 Git
- 不要把运行时目录 `%LOCALAPPDATA%\JDGoldWidget` 或 Chrome profile 打进仓库
