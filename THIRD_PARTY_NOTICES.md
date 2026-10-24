# 第三方内容说明

本项目原创代码由 1zhiguo 以 GPL-3.0-only 许可公开。该许可不替第三方素材授予
额外权利；游戏本体、DLL、存档、原画及商标不属于本项目的原创代码。

## DG-LAB 官方波形

本项目“DG-LAB 官方”分组的郊狼 V3 波形帧来自 `dglab-kit` 官方波形目录：

- 上游项目：https://github.com/dungeonlab-open/dglab-kit
- 源文件：https://github.com/dungeonlab-open/dglab-kit/blob/main/src/waveform/coyote.ts
- 负鼠专用波形源文件：https://github.com/dungeonlab-open/dglab-kit/blob/main/src/waveform/ovc.ts
- 上游许可证：GNU General Public License v3.0
- 许可证全文：https://github.com/dungeonlab-open/dglab-kit/blob/main/LICENSE

Ricca 共感预设、中文名称、事件用途、强度档位和安全上限是本项目的独立设计，
不是上游官方推荐。保留上游作者权利及 GPL-3.0 许可；许可证全文随本项目的
`LICENSE` 一同提供。使用与再分发须遵守适用的 GPL 条款。

`src/ricca_dglab/ovc.py` 中的五组负鼠振动波形使用上述 `ovc.ts` 的原始帧数据，
以振幅序列紧凑表示；未改动帧顺序或字节值。负鼠强度、游戏事件映射和剧情队列
是独立设置，不继承郊狼电刺激配置，也不代表 DG-LAB 官方的安全或体感建议。

## PySide6 / Qt

- 上游：https://www.qt.io/qt-for-python
- PySide6 / Qt 的具体组件采用其各自的 LGPLv3、GPLv3 或商业许可，具体以所安装
  的发行版组件为准。源码仓库只声明依赖，不包含 Qt 二进制运行时。

## 其他 Python 依赖

- `websockets`：BSD-3-Clause，https://github.com/python-websockets/websockets
- `qrcode`：BSD，https://github.com/lincolnloop/python-qrcode
- Pillow：HPND，https://github.com/python-pillow/Pillow
- NumPy：BSD-3-Clause，https://github.com/numpy/numpy

发布带运行时的二进制包时，必须另行收集所打包具体版本的许可证、版权声明及
适用的源代码/再链接要求。当前公开的是源码，不是完整 Python / Qt 运行时包。

## 图标、原画及操作示意图

Ricca 图标使用项目持有者提供的游戏插图；游戏作品、人物、插图及相关权利归
原权利人所有。DG-LAB 标识及手机操作界面图归相应权利人所有。本项目与游戏作者
及 DG-LAB 无官方隶属关系，也不声称拥有这些第三方素材的独占或商业授权。
GPL 源码许可不覆盖这些素材。若需替换、授权确认或下架，请联系项目维护者。

## SoundCard

“音频共感”使用 SoundCard 访问 Windows WASAPI 系统回环与录音输入：

- 上游项目：https://github.com/bastibe/SoundCard
- 许可证：BSD 3-Clause

程序仅实时计算 RMS、峰值和 16 段包络，不保存或上传录音内容。
