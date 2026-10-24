# Manaka：DG-LAB V4 与负鼠接入交接

> 基于 Ricca 本地开发工作区，整理于 2026-10-24。本文是迁移指南，不表示 Manaka 已完成适配，也不表示这些功能已进入 Ricca 已发布的 1.0.1 ZIP。
>
> Ricca 源码根目录：`<RICCA_WORKSPACE>/`。以根目录 `src` 为准，**不要拿 `build`、旧 ZIP 或 `public_repo` 的历史副本当最新实现**。

## 1. 目标与不能改变的东西

为 Manaka 保留原有 V3 郊狼电刺激支持，增加 DG-LAB 4 App 的 V4 Socket 接入，以及独立的负鼠振动控制。

- 郊狼 Pulse 与负鼠不是二选一：可以同时运行，每台设备都有自己的 A/B 通道。
- 郊狼 V3/V4 沿用用户原有电刺激强度、波形和策略，不因切协议重置配置。
- 负鼠的强度、振动波形、事件策略、剧情队列、音频映射独立保存，不能套用或覆盖郊狼配置。
- 新设备自动选择只减少操作，**不等于自动授权输出**。切设备、重连、异常恢复后不得补播旧输出。
- 一台设备暂停、断开、保存设置或报错，不应影响另一台正常设备。全局急停才必须覆盖全部设备。
- 不修改 Manaka 的游戏检测、事件识别或既有暂停语义；把它们作为输入接到新的设备输出层。

## 2. 正确架构：共享连接，独立路由

```text
Manaka 遥测 / 已验证游戏事件 / 音频信号
    ├─ 原电刺激映射、A/B 队列和限幅 ── 郊狼路由 ── V3 Bridge 或 V4 Hub.coyote
    └─ 独立振动映射、A/B 队列和限幅 ── 负鼠路由 ── V4 Hub.ovc

V4 Hub：一个 Socket 服务、一个手机会话/设备目录
    ├─ coyote：独立选择、授权、强度、帧游标、RPC、归零事务
    └─ ovc：   独立选择、授权、强度、帧游标、RPC、归零事务
```

允许两种组合：

| 郊狼 | 负鼠 | 连接方式 |
| --- | --- | --- |
| V4 | V4 | 同一个 DG-LAB 4 App 扫一次 V4 二维码，分别选择两台设备 |
| V3 | V4 | V3 与 V4 独立服务/连接；不能假定同一个手机 App 同时维持两个协议 |

当前默认端口 V3＝9999，V4＝9998。协议下拉只切换郊狼传输，不切换整个软件的配置对象，不关闭负鼠共享的 V4 Hub。

## 3. 代码导航与迁移边界

以下路径相对于 Ricca 根目录；同机器可直接读取。

| 文件 | 用途 / 迁移方式 |
| --- | --- |
| `src/ricca_dglab/dglab_v4.py` | V4 报文、发现、状态合并、通道就绪判断、限幅、输出循环、归零屏障；优先参考 |
| `src/ricca_dglab/dglab_v4_hub.py` | 单连接双角色路由；不要退回“一台设备替换另一台”的早期架构 |
| `src/ricca_dglab/dglab_bridge.py` | V3 实现及 V4 继承使用的线程、暂停、授权和急停机制；迁移 V4 时必须核对基类依赖 |
| `src/ricca_dglab/ovc.py` | 五个官方负鼠波形、独立配置默认值与清洗器；波形可参考，Ricca 事件名/默认策略不要照搬 |
| `src/ricca_dglab/ovc_pipeline.py` | 无 Socket、无 Qt 的独立振动规划器；目前依赖 Ricca mapping、scene、death、safety，必须改接 Manaka 事件 |
| `src/ricca_dglab/ovc_controller.py` | UI 属性/保存入口，独立保存及通道局部更新示例；不能原封不动接 Manaka backend |
| `src/ricca_dglab/backend.py` | `_make_bridge`、`_auto_select_new_v4_devices`、`selectSocketProtocol`、`selectV4Device`、`selectOvcDevice`、`_sync_ovc_output` 及输出阻断原因 |
| `src/ricca_dglab/product_config.py` | `ovc_profile` 子树兼容、`story_queue_switch`、原配置保留与保存失败处理 |
| `src/ricca_dglab/manual_control.py` | 设备独立的显式手动播放会话，不依赖游戏检测，但不绕过硬件/急停保护 |
| `src/ricca_dglab/qml/DeviceWorkbench.qml` | 同一工作台组件，通过 controller/vibration 参数分别编辑郊狼或负鼠 |
| `src/ricca_dglab/qml/ManualControlPage.qml`、`ManualDeviceConsole.qml` | 左侧独立手动 Tab；单郊狼或双设备左右布局 |
| `src/ricca_dglab/qml/ControlCenter.qml` | 连接页、状态提示、各设备启停和导航接线 |
| `src/ricca_dglab/qml/StoryQueueEditor.qml` | 剧情开关立即保存、局部更新而不打断其他通道 |
| `src/ricca_dglab/assets/locales/catalog.json` | 中英日字符串 |
| `docs/V4_TESTING.zh-CN.md` | Ricca 当前连接与实机验收说明 |

另外核对 `audit.py`、`network.py`、`story_queue.py`、映射模型与安全决策依赖；V4 不是复制两个文件就能独立工作的包。当前实现使用 `asyncio.timeout`（Python 3.11+），还需核对 Manaka 的 Python、websockets、PySide6 版本与打包依赖。

## 4. V4 协议接线要点

本节描述 **Ricca 当前实现**，不是对所有未来 App/固件的兼容承诺。协议入口参考：[DG-LAB 官方 dglab-kit](https://github.com/dungeonlab-open/dglab-kit/blob/main/README_CN.md)。迁移实施时重新核对官方协议，不自行猜测字段。

- 插件本地作为 WebSocket 服务；V4 二维码指向 `https://dungeon-lab.cn/s/?v=1&action=socket&url=<URL编码后的 ws://局域网IP:9998/?tid=controllerId>`。
- 校验连接 query 的 `tid`；会话发送 `hello`、`controller_attached`，用 `devices.get` 获取设备。
- 外层 `type: message`，内部 RPC 为 `{t: req, reqId, m, data}`；响应 `t: resp` 必须匹配请求 ID 与手机 client。
- 处理 `devices.snapshot`、`devices.patch`、`slots.patch`；**增量状态递归合并**，不能因只收到静音字段而丢掉蓝牙/配件状态。
- 支持输出：`COYOTE_030`、`OVC_1`。`COYOTE_020` 可发现，但当前 V4 波形格式未验证，禁止输出；不代表 V3 原有支持需要删除。
- 路由身份是 `(clientId, slotId)`，不能只依赖下拉框 index。`coyote:` / `ovc:` 请求前缀和各自 pending 表避免响应串线。
- A/B 在报文中为 `c: 0/1`。当前输出先发 `device.op` 的临时强度任务 `t:4, d:300, v:强度, im:true`，再发波形任务 `t:0, d:100, v:[单帧], im:true`，均带槽位 `s` 和 `p:1`。
- 不用永久非零基准强度任务维持输出；不要把“手机已连接”当作“设备已授权”。

### 状态必须分层

1. 本地 Socket 监听成功：只能说明服务已启动，不亮“手机已连接”的成功边框。
2. 手机 App 已扫码连接：仍不说明硬件蓝牙在线。
3. 设备蓝牙连接：检查 `slotState.hasDevice` / `props.connectState`，明确的否定状态优先。
4. A/B 可输出：逐通道检查静音、配件、故障、App 上限。
5. 已完成选中设备归零确认，且用户明确启用：才允许非零输出。

郊狼 `channelAStatus/BStatus` 的数值 `0` 不是错误，当前 `3/4` 判故障；负鼠对应字段必须是布尔 `true` 才表示配件已插入。不能对不同设备套同一套 truthy/falsy 判断。

## 5. 负鼠强度与波形：已踩过的关键坑

- 负鼠是振动器，不是第三个电刺激通道。独立强度范围 `0–200`，UI 所有强度操作按 **10** 变化；这是软件/协议范围，不是物理安全承诺。
- 最终发送：先取请求值、软件硬上限、App 通道上限和 200 的最小值，再**向下对齐到 10**。请求 38→30，App 上限25→最多20；小于10→0。
- 不要四舍五入到更大值。事件衰减、音频调制和旧配置都可能产生小数/非10倍数，因此 UI 限制之外，发送层必须再次处理。曾实际遇到 `value_must_be_multiple_of_10` 拒绝。
- 郊狼保持原来的0–100限幅与原步进，不能被负鼠200上限或10步进污染。
- 负鼠波形用独立 `ovc_*` key；未知 key 或电刺激 key 返回空帧并禁止输出，不偷偷 fallback 成电刺激波形。
- 五个官方波形：`ovc_pinpoint`、`ovc_soothe`、`ovc_trapezoid`、`ovc_beat`、`ovc_surf_wave`。当前保留官方8字节帧，频率字节 `0A0A0A0A` 后接四个幅值字节，100ms/帧；硬件转换由 DG-LAB 4 App 完成。
- 当前负鼠没有自定义曲线编辑器，不能在 Manaka UI 暗示已支持。
- Ricca 兼容层仍有历史默认低5/中10/高15/死亡20/上限20；发送时5会变0，15会变10。这些不是推荐体感预设。Manaka 应明确选择10步进的首用默认值，不照搬低于10的有效输出档，也不静默改写用户旧值。
- 官方振动数据来自 `dungeonlab-open/dglab-kit/src/waveform/ovc.ts`（源码标注 GPL-3.0）；保留来源及许可，检查 Manaka 的分发许可，不因同为自有项目而移除上游声明。

## 6. 稳定性：必须一起迁移的修复

### 6.1 归零屏障，不能只 clear

每台设备/槽位的接管及停止顺序是：

1. 立即撤销本路由授权、丢弃旧 desired 输出并推进 generation。
2. 向 A/B 发送 `t:7, v:0`，等待两边归零任务完成。
3. 发送 `device.op.clear` 并等待确认。
4. 再向 A/B 发送零值并确认，然后才允许发布 baseline-ready。

归零任务校验返回的 type、reason、slot、channel。使用每路由锁、事务合并及 `asyncio.shield`：快速切设备取消等待者时，不能把正在执行的 clear 事务一起取消。失败保持未就绪，不自动放行。

### 6.2 不阻塞帧循环，不串扰另一通道

- 当前100ms发一帧、300ms强度租期；调度循环20ms检查，500ms无新输出更新撤销授权。RPC响应超时2s、单次写入超时0.3s、归零事务超时1.5s、pending上限128。
- 常规波形发送只等待写入，不同步等待整个任务结束；任务响应通过 pending 表异步跟踪，否则容易卡顿/断续。
- A事件结束使用**只针对A的归零/clear**，不能清整台设备打断B；通道归零异步执行，不占住B的100ms帧流。
- 一台设备的RPC拒绝/超时只关闭该路由授权，不轻易关闭共享手机 Socket；手机会话断开才同时使两台路由失效。
- 保留 generation/selection epoch 校验。旧代郊狼任务的延迟 `cancelled` 响应不能清掉已经恢复的选择；当前有效任务的取消仍须按异常停止，不能一概忽略。

### 6.3 保留选择，但未就绪不输出

- 郊狼槽位还存在、暂时蓝牙未就绪或全部静音：保留下拉选择，显示具体等待原因，禁止输出；不能每次状态 patch 都回退“请选择”。
- 状态恢复后重新做确认归零；仍需手动启用，不自动重播。设备被删除、类型改变或 App 会话断开则失效选择。
- 自动选择仅在新物理连接出现时触发，不在每个 patch 触发，不重选已运行设备；支持用户主动取消选择。
- 每个禁用按钮旁显示原因：未扫码、未选设备、蓝牙断开、未插配件、通道静音、硬上限0、全局暂停/急停、遥测过期、尚未授权等。不要用一个灰色按钮概括所有问题。

## 7. 配置、剧情与暂停语义

新增 `ovc_profile` 子树保存负鼠：`strength_low/medium/high/death`、`hard_cap`、`event_rules`、`channel_policies`、`story_queues`、`audio_gain`、`audio_queue_minimum`。缺失时只补内存默认值；保存负鼠不得重写郊狼规则或自定义波形库。

- 负鼠独立 mapper、死亡状态、捕获状态与A/B队列时钟；共享已验证事件，不共享可变运行状态，也不修改原始事件。
- Manaka 的剧情判定和受击/死亡事件需要自己映射，**不要搬 Ricca Scene 名单、pause_mask 特例、HP 阈值、破甲倍率**。
- 剧情/鉴赏的通道配置独立于战斗。Ricca 模式为 `fixed`、`queue`、`audio`、`fixed_audio`、`queue_audio`、`off`，可按 Manaka 实际需要裁剪。
- “使用本通道剧情队列”开关关闭必须让该通道的剧情输出归零，不是偷偷切回固定波形。重新打开保留原选择/队列；单通道修改不能重置另一通道游标或另一设备。
- 存在死亡优先级的项目要明确：关闭剧情输出不能取消已确认的死亡单次惩罚；仅进入鉴赏也不能凭空制造死亡。沿用 Manaka 自己的规则并测试。
- 用户暂停、游戏暂停、场景内部动画控制器暂停不是同一个概念。不要从 Ricca 复制“某个暂停位可忽略”到 Manaka，更不能让传输层自行绕过游戏安全决策。
- 连接/选择/启用成功只表明链路状态，不保证有事件或可感知体感；记录并区分 requested、实际限幅后的sent与App reported强度。

## 8. UI 与手动保底

- 连接页：先游戏遥测、二维码（郊狼V3/V4选择在此），再郊狼和负鼠设备卡片。地址切换、端口占用及连接失败排查保留。
- 两个工作台用同一布局骨架：强度 / 战斗 / 剧情；分别绑定自己的 controller。不要用全局“当前设备profile”覆盖整个软件。
- 左侧单独“手动控制”Tab：无负鼠只显示郊狼，负鼠连接后双列；每台A/B强度、波形、开始和停止独立。
- 手动模式不依赖游戏检测，但继续检查设备就绪、配件、静音、硬上限及全局急停。强度初始0，编辑/导航不发送，必须显式开始/重新应用。
- 当前手动每次1–300秒，超时归零；暂停/断连/急停结束会话，恢复后必须再次开始。退出手动先归零，设备保持暂停，不突然恢复自动事件。
- HUD可分别显示电刺激和负鼠的A/B数字与5格强度；所有新增状态、阻断原因和教程适配中英日，截图检查最小窗口和双设备布局。

## 9. 日志与验证标准

应保留的日志事件：`socket.v4_send`、`socket.v4_response`、`socket.v4_readiness`、`socket.v4_route_state`、`socket.v4_route_failure`、`socket.v4_auto_selection`、`output.ovc_gate`。至少含role、client/slot、reqId、通道、强度、时长、阻断原因；不记录整段波形载荷。

`written-to-phone-websocket` 仅代表写入连接；任务完成/替换/清理响应不代表硬件真的输出。遇到没体感，应依次查授权→硬件/配件→限幅/步进→实际发送→App响应，而不是先改游戏检测。

优先参考测试：

- `tests/test_v4_bridge.py`：二维码、配对ID、报文、归零确认、短租期、超时、通道隔离、乱序/取消。
- `tests/test_v4_hub.py`：双设备并发、单边故障/暂停不影响另一边、V3+V4共存、App断开双边停止。
- `tests/test_v4_safety_review.py`：配件/静音/蓝牙字段、深合并、错client响应、调度器异常恢复。
- `tests/test_v4_auto_selection.py`：自动选中不启用、重连、旧事件、禁用原因。
- `tests/test_v4_backend.py`、`test_ovc.py`、`test_ovc_controller.py`：配置不互相污染、持久化失败、步进、200上限。
- `tests/test_ovc_pipeline.py`：独立事件映射、捕获、剧情/音频、队列、失效停止；游戏特定输入需换成Manaka。
- `tests/test_story_queue_switch.py`：关闭A剧情输出B继续、保存失败不变更运行态、死亡优先级。
- `tests/test_manual_control.py`：无游戏手动输出、独立超时、断连/急停不自动重播、硬上限与波形类型。
- `tests/verify_unified_workbench_ui.py`、`verify_manual_layout_ui.py`、`verify_manual_control_ui.py`：模拟设备与临时配置的界面/导航检查。

本次交接前 Ricca 全套341项单元测试通过，手动页另做了中英日×窗口尺寸×单双设备截图及模拟播放检查。**这些不替代 Manaka 移植后的测试，也不代表所有V4机型/网络组合实测通过。**

建议实机顺序：V3原功能回归→V4郊狼→V4负鼠A配件/B未插→双设备同时输出→单边暂停/拔配件/断蓝牙→剧情切换与队列关闭→全局急停→断网重连→手动模式。每步先确认用户授权与设备侧停止方式；不由迁移任务自动发送测试脉冲。

## 10. 给 Manaka 项目的执行要求（可直接作为起始指令）

请先读取本交接文档及所列 Ricca 当前源码，检查 Manaka 的架构与配置格式，再制定迁移清单并实现 V4 与负鼠支持。保留 V3、原用户配置、游戏检测和输出及时性。使用共享V4 Hub加独立郊狼/负鼠路由；负鼠独立配置、0–200且10步进，不能覆盖电刺激设置。一起移植归零屏障、通道隔离、异步任务确认、断连授权撤销、配件/静音提示和旧响应防护，不只做二维码与设备列表。

先完成模拟App协议/配置回归，再做中英日UI截图。不要自动启用真实设备、不要发送实机测试输出、不要覆盖用户settings.json，也不要自动发布或修改许可。汇报可复用/需改写的模块、测试结果与仍需用户实测的范围。
