# 贡献指南

感谢你愿意为 ModeCalc 提交 Issue 或 Pull Request。

## 开发环境

- Windows 10 / 11，或 macOS（构建与验证范围见 [macOS 构建说明](docs/MACOS_BUILD.md)）
- Python 3.12

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## 运行与测试

```powershell
python app.py     # 桌面版
pytest -q         # 全部单元测试
```

提交 PR 前请确保 `pytest -q` 全部通过；涉及界面的改动建议附一张截图或录屏。

## 分支与提交

- 从 `main` 拉出功能分支，例如 `feat/xxx`、`fix/xxx`。
- 提交信息建议使用 `类型: 简述` 的形式，例如：
  - `feat: 支持自定义调式`
  - `fix: 修复切换设备后音符残留`
  - `docs: 更新 README`
- 一个 PR 尽量只做一件事，便于 review。

## 代码约定

- Python 侧保持纯函数、无副作用（`mode_engine.py` / `chord_engine.py` 是纯函数模块）。
- 新功能请补充对应的 `tests/` 用例。
- 前端保持原生 JavaScript，不引入构建步骤；新增第三方库需在 `THIRD_PARTY_NOTICES.md` 中登记许可证。

## 隐私与安全

- 不要提交任何个人信息、密钥、令牌、绝对路径（如 `C:\Users\...`）。
- 提交前可自查：

```powershell
git grep -n -E "token|secret|password|C:\\\\Users"
```

- 打包产物、虚拟环境、本地设置文件已在 `.gitignore` 中忽略，请勿强制加入。

## 许可证

提交代码即表示同意以本项目的 [MIT License](LICENSE) 授权。

## macOS 开发与构建

Mac 使用 Python 3.12 framework + py2app；Windows 保留 PyInstaller。执行 `bash scripts/build_macos.sh` 构建，使用 `python scripts/smoke_macos.py dist/macos-arm64/ModeCalc.app` 验证真实 CoreMIDI 和 WKWebView。测试配置与用户数据隔离，详见 [构建说明](docs/MACOS_BUILD.md)。
