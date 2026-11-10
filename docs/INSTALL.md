# Installing LabToolbox · 安装指南

> **[English](#english)** · **[中文](#中文安装指南)**
> Module documentation / 模块文档: [docs/modules/README.md](modules/README.md)
> Release notes: <https://github.com/DrFermion/LabToolbox/releases>

LabToolbox is a single desktop application for Windows and macOS. The installer
and the macOS DMGs already contain everything the app needs: **Python runtime,
ImageJ 1.54 and a private Java runtime**. You do not need Python, ImageJ, Fiji or
Java installed, and the app never downloads anything on first use.

---

## English

### 1. Which download do I need?

| Platform | Download | Use it if |
|---|---|---|
| 🪟 Windows 10/11 (x64) | `LabToolbox-Setup-<version>.exe` | Recommended on Windows (installer, Start-menu entry, uninstaller) |
| 🪟 Windows 10/11 (x64) | `LabToolbox-Windows-x64.zip` | Portable use: unzip and run, no installer |
| 🍎 macOS 11+ — Apple Silicon | `LabToolbox-macOS-AppleSilicon.dmg` | Mac with Apple M1/M2/M3/M4 chip |
| 🍎 macOS 11+ — Intel | `LabToolbox-macOS-Intel.dmg` | Mac with an Intel processor |

**Which Mac do I have?** Apple menu → *About This Mac*. If the *Chip* line says
"Apple M…" (or *Processor* says "Apple M…") use the **Apple Silicon** DMG; if it
says "Intel" use the **Intel** DMG. Running an Intel build on Apple Silicon works
only through Rosetta and is not recommended — always pick the native build.

All builds are **unsigned** (see §6) and are shipped as GitHub Release assets.

### 2. Windows

**Installer (recommended)**

1. Run `LabToolbox-Setup-<version>.exe`.
2. Windows SmartScreen shows *"Windows protected your PC"* because the installer
   is not code-signed: click **More info** → **Run anyway**.
3. Follow the wizard (Chinese or English is selected automatically from the
   Windows display language), then start LabToolbox from the Start menu or the
   desktop shortcut.
4. Uninstall from *Settings → Apps → LabToolbox* (or *Apps and Features*).

The application itself is installed to `Program Files\LabToolbox`. Bundled
ImageJ/Java live in `Program Files\LabToolbox\_internal\imagej\` and are not
modified by normal use.

**Portable ZIP**

1. Extract `LabToolbox-Windows-x64.zip` to a normal folder. **Extract everything**
   — the app needs the `_internal` folder next to `LabToolbox.exe`; do not copy
   the .exe elsewhere.
2. Double-click `LabToolbox.exe`.

No administrator rights are needed for the portable version; the first launch can
take a few seconds because Windows Defender scans the new files.

### 3. macOS

1. Open the DMG that matches your Mac and drag **LabToolbox** into
   `/Applications`.
2. First launch: macOS Gatekeeper blocks unsigned apps with *"Apple could not
   verify that LabToolbox is free of malware"* (or *"LabToolbox is damaged and
   can't be opened"*). Use one of:
   - **Control-click** the app in Finder → **Open** → **Open** again
     (right-click → Open also works), or
   - *System Settings → Privacy & Security* → scroll down →
     **Open Anyway**, or
   - Terminal: `xattr -dr com.apple.quarantine /Applications/LabToolbox.app`
     (removes the quarantine flag; this is the same warning, not a corrupted
     download).
3. Later launches work normally (double-click).

The app is **ad-hoc signed only** (not notarized by Apple); this is expected for
these unsigned releases and is what the above workaround addresses. Apple Silicon
requires the ad-hoc signature to launch native binaries — the DMG already has it.

### 4. Bundled ImageJ (nothing to install)

The LIVE/DEAD fluorescence cell counter uses classic **ImageJ 1.54** with
`Analyze Particles` as its default (`backend="imagej"`) engine. In the packaged
app this ImageJ is **embedded** together with a native Java runtime:

| Platform | Bundled paths (read-only, inside the app) |
|---|---|
| Windows | `…\LabToolbox\_internal\imagej\ij.jar`, `…\imagej\jre\bin\java.exe` |
| macOS | `LabToolbox.app/Contents/Frameworks/imagej/ij.jar`, `…/imagej/jre/Contents/Home/bin/java` |

The counting macro `count_livedead.ijm` is bundled read-only at
`…/scripts/imagej/count_livedead.ijm` (never copied into the ImageJ folder).

- No system Java, ImageJ, Fiji or Python is required, and **no download happens
  at run time**; the app works offline.
- ImageJ 1.54 was verified to produce identical counts on Java 11 (bundled) and
  Java 8, so results are independent of the embedded runtime.
- Advanced users can point the counter at their own ImageJ/Fiji installation by
  setting the environment variable `LABTOOLBOX_IMAGEJ_DIR` to the ImageJ folder
  that contains `ij.jar` (and optionally its own `jre`).
- ImageJ/JRE license and provenance files are inside `imagej/` (`NOTICE.txt`,
  `LICENSE-ImageJ.txt`, `LICENSE-OpenJDK.txt`); the repository-level list is
  [THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md).

### 5. Data, examples and documentation

- Input data is read from wherever you select it (local disk, OneDrive, network
  share). Results are written to the output folder chosen in the app.
- Example tables and a LIVE/DEAD demo image set are bundled (GUI "open example"
  buttons, `examples/` folder).
- Algorithms, parameters and references for every module:
  [docs/modules/README.md](modules/README.md).

### 6. Unsigned releases — and how to add signing later

These releases use **no code-signing certificates**:

- Windows: no Authenticode signature → SmartScreen warning; no publisher name.
- macOS: no Apple Developer ID signature, no notarization → Gatekeeper warning.

This is intentional (certificates cost money and were not available for these
builds). To add signing later:

- **Windows**: buy a code-signing certificate (EV or standard, e.g. from a CA),
  install it on the CI runner, sign `LabToolbox.exe` / the installer with
  `signtool sign /fd sha256 /tr <timestamp-url> /td sha256`, and set `SignTool` +
  `SignedUninstaller=yes` in `installer.iss` (a placeholder is already there).
- **macOS**: join the Apple Developer Program, get a *Developer ID Application*
  certificate, then add to the release workflow after PyInstaller:
  `codesign --force --deep --options runtime --sign "Developer ID Application: …"
  dist/LabToolbox.app`, `xcrun notarytool submit …`, `xcrun stapler staple …`.
  In `labtoolbox.spec` pass `codesign_identity=...` and an entitlements file to
  `BUNDLE(...)`.
- Store the certificate/secrets as GitHub Actions secrets and gate the steps on
  their presence, so unsigned builds keep working for forks.

### 7. Troubleshooting

| Symptom | Fix |
|---|---|
| Windows: "Windows protected your PC" | More info → Run anyway (unsigned build) |
| Windows: app removed by antivirus | Add the install folder to the AV exclusion list, or use the portable ZIP in a local folder |
| Windows: smart card / no admin | Use the portable ZIP (no installation) |
| macOS: "cannot be opened because the developer cannot be verified" | Control-click → Open, or see §3 `xattr` command |
| macOS: "damaged and can't be opened" | `xattr -dr com.apple.quarantine /Applications/LabToolbox.app` |
| macOS: wrong Mac type warning / app won't start on M-series | Download the Apple Silicon DMG (not the Intel one) |
| Cell counter says ImageJ is missing | The install is incomplete — reinstall from the official installer/DMG (the ImageJ bundle is part of it) |
| Language of the UI | Switch 中文/English with the button in the app's top-right corner |

Please report platform/version details in
<https://github.com/DrFermion/LabToolbox/issues>.

---

## 中文安装指南

LabToolbox 是一个 Windows + macOS 的**单一桌面应用**。安装包和 DMG 里已经包含
应用运行所需的全部内容：**Python 运行时、ImageJ 1.54 和私有 Java 运行时**。因此
不需要另外安装 Python、ImageJ、Fiji 或 Java，应用**首次使用也不会联网下载任何东西**。

### 1. 下载哪个文件？

| 平台 | 下载文件 | 适用情况 |
|---|---|---|
| 🪟 Windows 10/11 (x64) | `LabToolbox-Setup-<版本>.exe` | Windows 推荐（安装向导、开始菜单、卸载程序） |
| 🪟 Windows 10/11 (x64) | `LabToolbox-Windows-x64.zip` | 便携版：解压即可用，不写注册表/不安装 |
| 🍎 macOS 11+ — Apple 芯片 | `LabToolbox-macOS-AppleSilicon.dmg` | M1/M2/M3/M4 芯片的 Mac |
| 🍎 macOS 11+ — Intel | `LabToolbox-macOS-Intel.dmg` | Intel 处理器的 Mac |

**怎么知道是哪种 Mac？** 苹果菜单 →「关于本机」：*芯片* 一栏显示 "Apple M…"
就用 **Apple Silicon** 版；显示 "Intel" 就用 **Intel** 版。Intel 版在 Apple 芯片
上只能通过 Rosetta 运行，不推荐，请优先下载对应架构的原生版本。

所有构建都是**未签名**的（见第 6 节），以 GitHub Release 附件形式发布。

### 2. Windows

**安装版（推荐）**

1. 运行 `LabToolbox-Setup-<版本>.exe`。
2. 由于安装包未做代码签名，Windows SmartScreen 会提示「Windows 已保护你的电脑」：
   点 **更多信息** → **仍要运行**。
3. 按向导安装（向导语言会按 Windows 显示语言自动选择中文或英文），完成后从
   开始菜单或桌面快捷方式启动。
4. 卸载：*设置 → 应用 → LabToolbox*（或「应用和功能」）。

应用安装在 `Program Files\LabToolbox`；内置的 ImageJ/Java 位于
`Program Files\LabToolbox\_internal\imagej\`，日常使用不会修改它们。

**便携 ZIP 版**

1. 把 `LabToolbox-Windows-x64.zip` **完整解压**到一个普通文件夹——`LabToolbox.exe`
   旁边必须有 `_internal` 文件夹，只复制 .exe 无法运行。
2. 双击 `LabToolbox.exe`。

便携版不需要管理员权限；首次启动可能慢几秒（Windows Defender 扫描新文件）。

### 3. macOS

1. 打开与你的 Mac 匹配的 DMG，把 **LabToolbox** 拖进 `/Applications`。
2. 首次启动时，因为应用未签名，Gatekeeper 会提示「无法验证 LabToolbox 是否包含
   恶意软件」（或「LabToolbox 已损坏，无法打开」）。任选一种方式：
   - 在 Finder 里 **按住 Control 点按**应用 → **打开** → 再点 **打开**
     （右键 →「打开」同样有效）；或
   - *系统设置 → 隐私与安全性* → 向下滚动 → **仍要打开**；或
   - 终端执行：`xattr -dr com.apple.quarantine /Applications/LabToolbox.app`
     （清除隔离标记，属于同一个提示，不是下载损坏）。
3. 之后可正常双击启动。

本应用只有 **ad-hoc 签名**（未经过 Apple 公证），这是当前未签名发布的正常状态，上面
的绕行方法就是针对它的。Apple 芯片必须要有 ad-hoc 签名才能运行原生二进制，DMG 中
已经包含该签名。

### 4. 内置 ImageJ（无需另外安装）

LIVE/DEAD 荧光细胞计数默认使用经典 **ImageJ 1.54** 的 `Analyze Particles`
（`backend="imagej"`）。在打包版本中，ImageJ 与**原生 Java 运行时**一起内嵌：

| 平台 | 内置路径（只读，位于应用内部） |
|---|---|
| Windows | `…\LabToolbox\_internal\imagej\ij.jar`、`…\imagej\jre\bin\java.exe` |
| macOS | `LabToolbox.app/Contents/Frameworks/imagej/ij.jar`、`…/imagej/jre/Contents/Home/bin/java` |

计数宏 `count_livedead.ijm` 以只读方式内置在
`…/scripts/imagej/count_livedead.ijm`（不会再被复制到 ImageJ 目录）。

- 不需要系统 Java / ImageJ / Fiji / Python，且**运行时不会联网下载**，可离线使用。
- ImageJ 1.54 已在 Java 11（内置）与 Java 8 上验证计数结果完全一致，结果与内置
  运行时无关。
- 进阶用户可设置环境变量 `LABTOOLBOX_IMAGEJ_DIR` 指向自己的 ImageJ/Fiji 安装目录
  （含 `ij.jar`，可选自带 `jre`）。
- ImageJ/JRE 的许可证与来源文件在 `imagej/` 内（`NOTICE.txt`、
  `LICENSE-ImageJ.txt`、`LICENSE-OpenJDK.txt`）；仓库级清单见
  [THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md)。

### 5. 数据、示例与文档

- 输入数据从你选择的位置读取（本地磁盘、OneDrive、网络共享均可），结果写入应用里
  指定的输出目录。
- 内置示例表格和 LIVE/DEAD 演示图集（GUI 的「打开范例」按钮、`examples/` 目录）。
- 每个模块的算法、参数与参考文献：[docs/modules/README.md](modules/README.md)。

### 6. 未签名发布——以及以后如何加签名

当前发布**不使用任何代码签名证书**：

- Windows：无 Authenticode 签名 → SmartScreen 警告、不显示发布者。
- macOS：无 Apple Developer ID 签名、未公证 → Gatekeeper 警告。

这是有意的（证书需要付费且本批构建没有证书）。以后要加签名：

- **Windows**：购买代码签名证书，在 CI runner 上安装后用
  `signtool sign /fd sha256 /tr <时间戳服务> /td sha256` 签
  `LabToolbox.exe` 和安装包，并在 `installer.iss` 里配置 `SignTool` +
  `SignedUninstaller=yes`（文件中已留好注释占位）。
- **macOS**：加入 Apple Developer Program，取得 *Developer ID Application* 证书，
  在发布流程里 PyInstaller 之后加
  `codesign --force --deep --options runtime --sign "Developer ID Application: …"
  dist/LabToolbox.app`、`xcrun notarytool submit …`、`xcrun stapler staple …`；
  并在 `labtoolbox.spec` 的 `BUNDLE(...)` 传入 `codesign_identity` 和 entitlements。
- 证书/密钥放在 GitHub Actions secrets 中，并用「存在才执行」的条件包住签名步骤，
  保证 fork 的未签名构建仍可运行。

### 7. 常见问题

| 现象 | 解决 |
|---|---|
| Windows：「Windows 已保护你的电脑」 | 更多信息 → 仍要运行（未签名构建的正常提示） |
| Windows：被杀毒软件删除 | 把安装目录加入杀毒软件排除项，或改用便携 ZIP 放在本地目录 |
| Windows：没有管理员权限 | 使用便携 ZIP，无需安装 |
| macOS：「无法验证开发者」 | 按住 Control 点按 → 打开；或见第 3 节 `xattr` 命令 |
| macOS：「已损坏，无法打开」 | `xattr -dr com.apple.quarantine /Applications/LabToolbox.app` |
| macOS：提示架构不符 / M 系列芯片无法启动 | 下载 Apple Silicon 版 DMG（不是 Intel 版） |
| 细胞计数提示缺少 ImageJ | 安装不完整——请用官方安装包/DMG 重新安装（ImageJ 已包含在其中） |
| 界面语言 | 用应用右上角的按钮切换 中文/English |

遇到问题请在 <https://github.com/DrFermion/LabToolbox/issues> 反馈，并附上平台与版本信息。