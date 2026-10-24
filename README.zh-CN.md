# Ricca × DG-LAB Control Center

简体中文 · [English](README.md) · [产品网站](https://ricca-dglab.web.app) · [游戏 Dashboard](https://dglab-x-game.web.app)

将 **Holy Knight Ricca** 的游戏状态同步到郊狼 DG-LAB 的独立 Windows 软件。
外部只读检测，**无需 BepInEx，不注入 DLL，不修改游戏文件或内存**。

## 核心功能

- 掉血、受击动作、破甲、持续受困／挣扎和死亡反馈。
- A/B 通道独立设置战斗与剧情／鉴赏策略：固定波形、循环队列、音频及组合模式。
- 官方波形、自定义波形编辑器、实时监视与游戏内 HUD。
- V3／V4 Socket 扫码连接，郊狼电刺激与负鼠振动可同时运行、独立启停。
- 负鼠独立强度、官方振动波形与剧情队列；统一工作台及左侧独立手动控制页。
- HUD 大小、位置、显示内容可调；网卡地址切换与连接诊断。
- 中／英／日界面；默认 **Ctrl+F12** 全局急停，支持直接按键录入和单键。

## 快速开始

1. [网站下载区](https://ricca-dglab.web.app/#downloads)开放链接后，下载 Windows ZIP，**完整解压**并启动 `Ricca-x-DGlab.exe`，无需安装 Python。
2. 完成新手教程，手动设置较低的安全硬上限。
3. 启动支持的游戏版本。手机与电脑连接同一局域网，选择 V3／V4 并用对应 DG-LAB App 的 Socket 模式扫码。V4 核对设备、配件／静音状态及硬上限后，分别启用设备输出。

启用后按有效游戏状态同步输出。V4 自动发现／选择设备不会自动授权输出。手动模式不依赖游戏检测，但保留设备就绪检查、硬上限和急停保护。

**急停会归零并锁定两个通道，再按不会恢复，须手动恢复输出。**
死亡惩罚可能优先于普通暂停。软件上限不保证体感或物理安全；Windows 包尚未签名。

## 兼容与详细说明

支持 Windows x64，以及已核对指纹的 Ricca **1.4.1 中／英文构建**。
游戏更新、模组或不同二进制文件可能导致检测失效。

- [使用指南：输出逻辑、剧情／音频与配置](docs/USAGE.zh-CN.md)
- [构建指纹与故障排查](docs/USAGE.zh-CN.md#支持的构建与故障排查)
- [源码运行与参与开发（英文）](CONTRIBUTING.md)
- [打包发布（英文）](RELEASING.md) · [安全问题反馈（英文）](SECURITY.md)

当前源码版本：**1.1.0**。[V4／负鼠连接说明](docs/V4_TESTING.zh-CN.md)。下载镜像另行发布；GitHub 自动生成的 Source code ZIP 不是可直接运行的软件。

## 许可证

代码采用 [GPL-3.0-only](LICENSE)。不分发游戏本体、存档、个人配置或遥测记录。
第三方原画及商标权利不变，见[第三方声明](THIRD_PARTY_NOTICES.md)。
