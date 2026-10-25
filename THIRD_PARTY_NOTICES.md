# 第三方组件与许可证

本项目包含以下第三方软件与字体，版权归各自作者所有。各组件均按其原始许可证分发。

## VexFlow 5.0.0

- 许可证：MIT
- 版权：Copyright (c) 2023-present VexFlow contributors
- 来源：https://github.com/vexflow/vexflow
- 本仓库文件：`static/vendor/vexflow-core.js`

## traste 1.0.0

- 许可证：MIT
- 版权：Copyright (c) Ramiro Gómez
- 来源：https://github.com/yaph/traste
- 本仓库文件：`static/vendor/traste.min.js`

`traste.min.js` 为打包后的浏览器文件，内含其依赖：

- d3-selection — ISC — Copyright 2010-2021 Mike Bostock — https://github.com/d3/d3-selection
- @tonaljs/tonal — MIT — https://github.com/tonaljs/tonal
- cromatica — MIT — Copyright (c) Ramiro Gómez — https://github.com/yaph/cromatica

## Bravura / Academico 字体

- 许可证：SIL Open Font License 1.1
- 版权：Steinberg Media Technologies GmbH（Bravura）；VexFlow 字体项目（Academico 打包）
- 来源：https://github.com/vexflow/vexflow-fonts
- 本仓库文件：`static/vendor/fonts/bravura/bravura.woff2`、`static/vendor/fonts/academico/academico.woff2`

## Quicksand

- 许可证：SIL Open Font License 1.1
- 版权：The Quicksand Project Authors（Andrew Paglinawan）
- 来源：https://github.com/andrew-paglinawan/QuicksandFamily
- 本仓库文件：`static/fonts/Quicksand-Medium.ttf`

SIL Open Font License 1.1 全文见 [`LICENSES/OFL-1.1.txt`](LICENSES/OFL-1.1.txt)。

## Python 桌面运行时

macOS standalone App 还包含以下运行组件：

- CPython — PSF License — https://www.python.org/psf/license/
- Mido — MIT — https://github.com/mido/mido
- python-rtmidi / RtMidi — MIT 及其上游许可 — https://github.com/SpotlightKid/python-rtmidi
- pywebview — BSD-3-Clause — https://github.com/r0x0r/pywebview
- PyObjC 框架绑定 — MIT — https://github.com/ronaldoussoren/pyobjc
- Bottle — MIT — https://github.com/bottlepy/bottle
- proxy-tools — MIT — https://github.com/jtushman/proxy-tools
- typing_extensions — PSF-2.0 — https://github.com/python/typing_extensions
- packaging — Apache-2.0 / BSD-2-Clause — https://github.com/pypa/packaging

构建脚本将实际运行依赖 wheel 中的许可证文件与发行元数据、CPython 许可证复制到 App 的 `Contents/Resources/ThirdPartyLicenses/`。py2app 和 PyInstaller 为分别用于 Mac 与 Windows 的构建工具。
