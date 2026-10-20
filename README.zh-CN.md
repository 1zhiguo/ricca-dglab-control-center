# Ricca × DG-LAB Control Center

简体中文 · [English](README.md) · [产品网站](https://ricca-dglab.web.app) · [游戏 Dashboard](https://dglab-x-game.web.app)

将 **Holy Knight Ricca** 的游戏状态同步到郊狼 DG-LAB 的独立 Windows 软件。
外部只读检测，**无需 BepInEx，不注入 DLL，不修改游戏文件或内存**。

## 核心功能

- 掉血、受击动作、破甲、持续受困／挣扎和死亡反馈。
- A/B 通道独立设置战斗与剧情／鉴赏策略：固定波形、循环队列、音频及组合模式。
- 官方波形、自定义波形编辑器、实时监视与游戏内 HUD。
- Socket 扫码连接、网卡地址切换与连接诊断。
- 中／英／日界面；默认 **Ctrl+F12** 全局急停，支持直接按键录入和单键。

## 快速开始

1. [网站下载区](https://ricca-dglab.web.app/#downloads)开放链接后，下载 Windows ZIP，**完整解压**并启动 `Ricca-x-DGlab.exe`，无需安装 Python。
2. 完成新手教程，手动设置较低的安全硬上限。
3. 启动支持的游戏版本。手机与电脑连接同一局域网，用 DG-LAB 3.0 App 的 Socket 模式扫码。

连接成功后，软件按有效游戏状态自动输出；不想立即输出时，请先暂停。

**急停会归零并锁定两个通道，再按不会恢复，须手动恢复输出。**
死亡惩罚可能优先于普通暂停。软件上限不保证体感或物理安全；Windows 包尚未签名。

## 兼容与详细说明

支持 Windows x64，以及已核对指纹的 Ricca **1.4.1 中／英文构建**。
游戏更新、模组或不同二进制文件可能导致检测失效。

- [使用指南：输出逻辑、剧情／音频与配置](docs/USAGE.zh-CN.md)
- [构建指纹与故障排查](docs/USAGE.zh-CN.md#支持的构建与故障排查)
- [源码运行与参与开发（英文）](CONTRIBUTING.md)
- [打包发布（英文）](RELEASING.md) · [安全问题反馈（英文）](SECURITY.md)

当前源码版本：**1.0.1**。下载镜像另行发布；GitHub 自动生成的 Source code ZIP 不是可直接运行的软件。

## 许可证

代码采用 [GPL-3.0-only](LICENSE)。不分发游戏本体、存档、个人配置或遥测记录。
第三方原画及商标权利不变，见[第三方声明](THIRD_PARTY_NOTICES.md)。
