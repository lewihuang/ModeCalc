# macOS App 构建与验证

Windows 继续由 `build.bat` / PyInstaller 构建；Mac 使用 py2app standalone。两端共用识别、音阶库和前端代码。

## 源码运行

开发机需要 Python 3.12 framework 构建（python.org、Homebrew 或 GitHub Actions setup-python）和 Xcode Command Line Tools。py2app 0.28.10 不兼容将 zlib 编为内建模块的 uv-managed Python；脚本会在构建前检查并提示。

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python app.py
```

不需要安装 Qt、Node.js、WebView2 或单独的 RtMidi 系统包。MIDI 通过 python-rtmidi wheel 中的 CoreMIDI 后端接入。

## 构建独立 App

```bash
bash scripts/build_macos.sh
```

默认使用 `.venv/bin/python`；也可以设置 `MODECALC_PYTHON=/path/to/python3.12`。构建解释器和所有原生 wheel 必须匹配目标架构。脚本只清理自身对应架构的 `build/macos-*` 和 `dist/macos-*`。

产物示例：

```text
dist/macos-arm64/ModeCalc.app
dist/ModeCalc-v1.2.1-macos-arm64.zip
dist/ModeCalc-v1.2.1-macos-arm64.zip.sha256
```

默认按构建机架构生成单架构包，Apple Silicon 为 `macos-arm64`，Intel 为 `macos-x86_64`；脚本会移除其他架构的原生代码。App 内含 Python 与原生扩展，用户机器无需安装开发工具。解压 ZIP 后，将 `ModeCalc.app` 拖到 Applications 或直接双击运行。

### Universal 2 通用版

使用同时包含 arm64 与 x86_64 的 Python 3.12 framework（例如 python.org 的 Universal 2 安装包）：

```bash
MODECALC_PYTHON=/path/to/universal2/python3.12 bash scripts/build_macos_universal.sh
```

脚本创建独立的 `.venv-universal2`，下载相同版本的两种 RtMidi wheel，通过 delocate 合并原生扩展，再使用 py2app 构建。构建后递归验证每个 Mach-O 均包含两种架构，任何依赖缺少架构即失败。产物为 `dist/macos-universal2/ModeCalc.app` 和 `dist/ModeCalc-v1.2.1-macos-universal2.zip`。

Universal 2 在 Intel 和 M 芯片上均原生运行，日常使用不需要 Rosetta。当前测试 ZIP 约 26 MB；M 专用 ZIP 约 18 MB，功能相同。两种包里的应用都叫 ModeCalc，使用相同设置目录，安装时选择一种即可。

构建使用 `packaging/macos/setup.py`；图标从现有 ICO 的最大 PNG 帧转换生成，版本信息来自 `app_version.py`。应用的 `static/`、本地字体与许可证一起打包。`verify_macos.py` 检查资源、原生架构、最低系统要求、外部符号链接与开发机动态库引用。

## 验证

```bash
python -m pytest -q
python scripts/verify_macos.py dist/macos-arm64/ModeCalc.app arm64
python scripts/smoke_macos.py dist/macos-arm64/ModeCalc.app
python scripts/verify_macos.py dist/macos-universal2/ModeCalc.app universal2
MODECALC_SMOKE_ARCH=arm64 python scripts/smoke_macos.py dist/macos-universal2/ModeCalc.app
MODECALC_SMOKE_ARCH=x86_64 python scripts/smoke_macos.py dist/macos-universal2/ModeCalc.app
```

最后一个命令创建专用 CoreMIDI 虚拟输出，向 App 发送 C–E–G，并检查真实窗口的和弦、桥接、字体、谱表、52 个白键和指板。它从无关的临时工作目录启动 App，移除 Python / DYLD 开发环境覆盖，并使用临时设置和日志；结束后自动退出。它不会向物理 MIDI 输出设备发送数据。

实际设备验收还需覆盖 USB 键盘、踏板、拔插、睡眠唤醒、不同 MIDI 通道与多设备演奏。自动化虚拟输入不替代这些硬件检查。

`MODECALC_SMOKE_ARCH` 用于强制选择通用包的架构，并检查应用实际运行架构。在 M 芯片上测试 x86_64 分支需要安装 Rosetta；这属于兼容性补充验证，不能替代 Intel 真机验收。2026-10-26 两个分支的真实 MIDI 与界面冒烟均通过，M 专用包也通过；每包检查了 68 个原生文件。

2026-10-26 已在 Apple Silicon / macOS 26.4.1 上验证独立 App、实际 CoreMIDI 虚拟输入及设置界面操作，137 项 Python 回归测试通过。还检查了中文空格路径、只读资源与运行后的签名完整性。macOS 14 是当前构建的最低版本目标；最低版本和 Intel 真机尚未验证。CI 已配置 Windows、Mac arm64 与 Intel 单架构构建及检查，Universal 2 当前通过上述脚本本地构建，工作流尚需在 GitHub 上实际运行。

## 设置、日志与桌面行为

- 设置：`~/Library/Application Support/ModeCalc/settings.json`。
- 日志：`~/Library/Logs/ModeCalc/ModeCalc.log`，每份最大 2MiB，保留 3 份历史。
- 旧的 `~/ModeCalc/settings.json` 在规范位置不存在时自动复制，旧文件保留。
- `MODECALC_SETTINGS_DIR` 保持原语义：实际写入 `<该目录>/ModeCalc/settings.json`。
- `MODECALC_LOG` 可覆盖日志文件位置。
- Mac 使用系统标题栏和默认应用 / Edit 菜单；`Cmd+,` 打开设置，`Cmd+Q` 退出。关闭最后窗口也退出。
- MIDI 设备约每秒刷新，亦可在 MIDI Input 中手动刷新。Mac 显示已配置的 IAC / DAW 输入；Windows 保留原有名称过滤策略。

## 签名与正式发布

默认构建执行 ad-hoc 签名，用于本地运行与测试。这不是 Developer ID 签名，不能保证从浏览器下载后通过 Gatekeeper 的正常发行检查。

有 Developer ID Application 证书时：

```bash
export MODECALC_SIGN_IDENTITY='Developer ID Application: Your Name (TEAMID)'
bash scripts/build_macos.sh

# 先使用 notarytool store-credentials 配置自己的 Keychain profile。
export MODECALC_NOTARY_PROFILE='ModeCalc'
bash scripts/notarize_macos.sh dist/macos-arm64/ModeCalc.app
```

签名脚本按由内到外的顺序签署原生代码，启用发行加固运行时与时间戳。PyObjC 动态回调所需的 `allow-jit` 位于 `packaging/macos/entitlements.plist`。不启用 App Sandbox 或禁用 Library Validation。网络声明仅允许本地网络，静态资源服务绑定回环地址。

公证脚本会签署、提交 ZIP、附加票据、验证 Gatekeeper 并重新生成最终 ZIP 和 SHA256。公证需要联网；应用正常使用不需要外网。首版不生成 DMG，也不直接上传 GitHub Release。

`.github/workflows/release-macos.yml` 为手动触发的正式发布包工作流，需要仓库 secret：

```text
MACOS_CERTIFICATE_P12_BASE64
MACOS_CERTIFICATE_PASSWORD
MACOS_KEYCHAIN_PASSWORD
MACOS_SIGN_IDENTITY
MACOS_APPLE_ID
MACOS_TEAM_ID
MACOS_APP_SPECIFIC_PASSWORD
```

凭据只在可信发布任务中使用，结束后清理临时 Keychain。普通 PR 无需这些凭据。未配置凭据时仍可构建本地测试包，正式工作流会明确失败，不自动降级为未公证发行包。

## 发布前剩余检查

1. 使用当前安全补丁版本的 Python 3.12 framework 重新构建正式包；本机初步冻结验证使用临时解包的 python.org 3.12.10 framework，未替换系统 Python。
2. 在 macOS 14 和 Intel 真机运行同样的核心场景。
3. 完成物理 USB 键盘、踏板、拔插和睡眠唤醒检查。
4. 配置 Developer ID，验证加固签名后的动态回调和公证最终下载包。
5. 运行 GitHub CI 并实际验证 Windows exe；本机只验证了共享 Python 回归与 macOS 成品。
