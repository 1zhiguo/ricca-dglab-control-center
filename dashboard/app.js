"use strict";

const $ = (id) => document.getElementById(id);
const ui = {};
let latestSnapshot = null;
let activeFilter = "all";
let hiddenThroughId = 0;
let polling = false;

const pageCopy = {
  overview: ["实时总览", "玩家、Boss、动作与输出门控状态"],
  story: ["剧情监视", "ADV 台词、进度与过场控制状态"],
  diagnostics: ["读取诊断", "采样健康度、对象地址与完整快照"],
  events: ["事件记录", "伤害聚合、动作边沿、剧情与场景切换"],
};

const ids = [
  "pageTitle", "pageSubtitle", "sampleClock", "connectionPill", "errorBanner", "eventCount",
  "gateState", "sceneBadge", "pauseBadge", "playerPtrBadge", "playerStateChip", "hpGauge",
  "hpPercent", "hpValues", "mpValues", "mpBar", "defenceValue", "speedValue", "invincibleValue",
  "aiValue", "actionLed", "actionName", "actionHash", "actionTime", "actionTimeBar",
  "characterState", "triggerEnabled", "checkHash", "bossBattleChip", "bossHpPercent", "bossHpBar",
  "bossHpValues", "bossCount", "bossState", "bossAction", "targetActor", "channelAValue",
  "channelABar", "channelBValue", "channelBBar", "signalChart", "chartEmpty", "stageLoadedChip",
  "stageName", "sceneIndex", "masterScale", "directionScale", "stageScale", "pauseMask", "userPause",
  "resourcesLoaded", "gameOver", "storyModeChip", "storyAsset", "storyLine", "storySpeaker",
  "storyMessage", "storyWait", "storyShowUi", "storySkip", "advSceneName", "advLineIndex", "advState",
  "displayState", "nextAction", "actCutMode", "actScreenPaused", "advTimeScale", "healthChip", "pollHz",
  "latencyMs", "sampleCount", "damageWindow", "pointerTable", "rawJson", "copyJson",
  "clearVisualEvents", "eventList"
];
ids.forEach((id) => { ui[id] = $(id); });

function value(v, digits = 2) {
  if (v === null || v === undefined || v === "") return "—";
  if (typeof v === "number") {
    if (!Number.isFinite(v)) return "—";
    return Number.isInteger(v) ? String(v) : v.toFixed(digits).replace(/\.?0+$/, "");
  }
  return String(v);
}

function truth(v) {
  if (v === null || v === undefined) return "—";
  return v ? "YES" : "NO";
}

function pct(v) {
  const n = Number(v);
  return Number.isFinite(n) ? Math.max(0, Math.min(100, n * 100)) : 0;
}

function width(el, amount) {
  el.style.width = `${Math.max(0, Math.min(100, Number(amount) || 0))}%`;
}

function text(el, content) {
  el.textContent = content === null || content === undefined || content === "" ? "—" : String(content);
}

function formatClock(iso) {
  if (!iso) return "尚无样本";
  const date = new Date(iso);
  return `SAMPLE ${date.toLocaleTimeString("zh-CN", { hour12: false })}.${String(date.getMilliseconds()).padStart(3, "0")}`;
}

function updateConnection(state, meta) {
  const connected = Boolean(state.connected);
  ui.connectionPill.className = `connection-pill ${connected ? "online" : "error"}`;
  ui.connectionPill.querySelector("strong").textContent = connected ? `已连接 · PID ${state.process_id}` : "等待游戏";
  text(ui.sampleClock, formatClock(state.sampled_at));
  const problem = !connected ? state.message : (state.telemetry_errors || []).join(" · ");
  ui.errorBanner.classList.toggle("hidden", !problem);
  text(ui.errorBanner, problem || "");
  ui.healthChip.className = `chip ${connected && !(state.telemetry_errors || []).length ? "good" : "warn"}`;
  text(ui.healthChip, connected ? ((state.telemetry_errors || []).length ? "PARTIAL" : "HEALTHY") : "WAITING");
  text(ui.pollHz, value(meta.poll_hz));
  text(ui.latencyMs, value(meta.read_latency_ms));
  text(ui.sampleCount, value(meta.sample_count, 0));
  text(ui.damageWindow, value(meta.damage_window_ms, 0));
}

function updateOverview(state, events) {
  const connected = Boolean(state.connected);
  const gameplay = state.scene === "gameplay";
  const paused = Boolean(state.is_paused);
  text(ui.gateState, !connected ? "等待游戏进程" : !gameplay ? "场景非战斗 · 输出应关闭" : paused ? "游戏暂停 · 输出应冻结" : "战斗读取有效 · 可计算联动");

  ui.sceneBadge.className = `chip ${gameplay ? "good" : state.scene === "adv" ? "accent" : "neutral"}`;
  text(ui.sceneBadge, (state.scene || "NO SCENE").toUpperCase());
  ui.pauseBadge.className = `chip ${paused ? "warn" : connected ? "good" : "neutral"}`;
  text(ui.pauseBadge, paused ? `PAUSED · ${value(state.pause_mask, 0)}` : connected ? "RUNNING" : "PAUSE —");
  text(ui.playerPtrBadge, state.player_address ? `PLAYER ${state.player_address}` : "PLAYER —");

  const hpRatio = pct(state.hp_ratio);
  const circumference = 2 * Math.PI * 72;
  ui.hpGauge.style.strokeDasharray = String(circumference);
  ui.hpGauge.style.strokeDashoffset = String(circumference * (1 - hpRatio / 100));
  ui.hpGauge.style.stroke = hpRatio < 25 ? "var(--red)" : hpRatio < 55 ? "var(--amber)" : "var(--pink)";
  text(ui.hpPercent, state.current_hp === undefined ? "—" : `${Math.round(hpRatio)}%`);
  text(ui.hpValues, state.current_hp === undefined ? "— / —" : `${value(state.current_hp)} / ${value(state.max_hp)}`);

  const mpRatio = state.max_magic > 0 ? pct(state.current_magic / state.max_magic) : 0;
  text(ui.mpValues, state.current_magic === undefined ? "— / —" : `${value(state.current_magic)} / ${value(state.max_magic)}`);
  width(ui.mpBar, mpRatio);
  text(ui.defenceValue, value(state.defence));
  text(ui.speedValue, value(state.speed_scale));
  text(ui.invincibleValue, state.invincible_type === undefined ? "—" : `${value(state.invincible_type, 0)} / ${value(state.invincible_count, 0)}`);
  text(ui.aiValue, truth(state.control_ai_enabled));
  text(ui.playerStateChip, state.character_state_name || "—");

  const action = state.action_trigger_name && state.action_trigger_name !== "Unknown" ? state.action_trigger_name : (state.action_trigger_hash === undefined ? "等待动作数据" : "Unknown action");
  text(ui.actionName, action);
  text(ui.actionHash, state.action_trigger_hash === undefined ? "HASH —" : `HASH ${state.action_trigger_hash}`);
  text(ui.actionTime, value(state.action_time, 3));
  width(ui.actionTimeBar, ((Number(state.action_time) || 0) % 1) * 100);
  text(ui.characterState, state.character_state === undefined ? "—" : `${value(state.character_state, 0)} · ${state.character_state_name || "Unknown"}`);
  text(ui.triggerEnabled, truth(state.action_trigger_enabled));
  text(ui.checkHash, value(state.action_check_trigger_hash, 0));
  ui.actionLed.classList.toggle("on", Boolean(state.action_trigger_enabled));

  const bossRatio = pct(state.boss_hp_ratio);
  text(ui.bossHpPercent, state.boss_current_hp === undefined ? "—" : `${Math.round(bossRatio)}%`);
  text(ui.bossHpValues, state.boss_current_hp === undefined ? "— / —" : `${value(state.boss_current_hp)} / ${value(state.boss_max_hp)}`);
  width(ui.bossHpBar, bossRatio);
  text(ui.bossCount, value(state.boss_count, 0));
  text(ui.bossState, state.boss_character_state_name || "—");
  text(ui.bossAction, state.boss_action_trigger_name || "—");
  text(ui.targetActor, state.player_controller?.target_actor_address || "—");
  ui.bossBattleChip.className = `state-chip ${state.boss_battling ? "" : "muted"}`;
  text(ui.bossBattleChip, state.boss_battling ? "BATTLE" : "未交战");

  const stage = state.stage || {};
  text(ui.stageName, stage.system_name || (connected ? "未命名场景" : "—"));
  text(ui.sceneIndex, stage.current_scene_index === undefined ? "Scene —" : `Scene ${stage.current_scene_index} · Mode ${value(stage.mode, 0)}`);
  text(ui.masterScale, value(state.master_time_scale));
  text(ui.directionScale, value(state.direction_time_scale));
  text(ui.stageScale, value(stage.game_time_scale));
  text(ui.pauseMask, value(state.pause_mask, 0));
  text(ui.userPause, truth(state.game_ui?.is_user_pause));
  text(ui.resourcesLoaded, truth(stage.all_resource_loaded));
  text(ui.gameOver, truth(stage.is_game_over));
  ui.stageLoadedChip.className = `state-chip ${stage.act_scene_loaded ? "" : "muted"}`;
  text(ui.stageLoadedChip, stage.act_scene_loaded ? "SCENE LOADED" : "NOT LOADED");

  updateOutputPreview(events);
}

function updateOutputPreview(events) {
  const now = Date.now();
  const damage = events.find((event) => event.kind === "damage");
  const action = events.find((event) => event.kind === "action");
  let a = 0;
  if (damage) {
    const age = now - new Date(damage.time).getTime();
    if (age < 5000) a = Math.min(100, (Number(damage.data?.ratio) || 0) * 360 * Math.max(0, 1 - age / 5000));
  }
  width(ui.channelABar, a);
  text(ui.channelAValue, `${Math.round(a)}%`);

  let b = 0;
  let label = "IDLE";
  if (action) {
    const age = now - new Date(action.time).getTime();
    if (age < 2400) {
      b = Math.max(0, 100 * (1 - age / 2400));
      label = String(action.title).toUpperCase();
    }
  }
  width(ui.channelBBar, b);
  text(ui.channelBValue, label);
}

function updateStory(state) {
  const story = state.story || {};
  const adv = state.adv_scene || {};
  const online = state.scene === "adv" || Object.keys(story).length > 0;
  ui.storyModeChip.className = `chip ${online ? "accent" : "neutral"}`;
  text(ui.storyModeChip, online ? "ADV ONLINE" : "ADV OFFLINE");
  text(ui.storyAsset, story.asset_name || "NO ASSET");
  text(ui.storyLine, story.line_index === undefined ? "LINE —" : `LINE ${story.line_index}`);
  text(ui.storySpeaker, story.speaker || (online ? "旁白" : "等待剧情"));
  text(ui.storyMessage, story.stripped_message || story.message || "进入 ADV 场景后，这里会显示当前说话人和台词。");
  text(ui.storyWait, truth(story.wait_next));
  text(ui.storyShowUi, truth(story.show_ui));
  text(ui.storySkip, value(story.skip_mode, 0));
  text(ui.advSceneName, adv.scene_name || "—");
  text(ui.advLineIndex, value(story.line_index, 0));
  text(ui.advState, value(story.adv_state, 0));
  text(ui.displayState, value(story.display_state, 0));
  text(ui.nextAction, value(story.next_action, 0));
  text(ui.actCutMode, value(story.act_cut_mode, 0));
  text(ui.actScreenPaused, truth(story.act_screen_paused));
  text(ui.advTimeScale, value(adv.game_time_scale));
}

function updateDiagnostics(state) {
  const pointers = [
    ["GameAssembly", state.module_base], ["Act Class", state.act_class_address],
    ["Static Fields", state.static_fields_address], ["Game Controller", state.game_controller_address],
    ["Player Actor", state.player_address], ["Player Controller", state.player_controller_address],
    ["Action Info", state.action_info_address], ["Boss Actor", state.boss_address],
    ["Stage Controller", state.stage_controller_address], ["Game UI", state.game_ui_controller_address],
    ["ADV Scene", state.adv_scene_controller_address], ["ADV Controller", state.adv_controller_address],
  ];
  ui.pointerTable.replaceChildren(...pointers.map(([label, address]) => {
    const row = document.createElement("div");
    const name = document.createElement("span");
    const code = document.createElement("code");
    name.textContent = label;
    code.textContent = address || "—";
    row.append(name, code);
    return row;
  }));
  ui.rawJson.textContent = JSON.stringify(state, null, 2);
}

const systemKinds = new Set(["attach", "detach", "scene", "pause", "rebind", "hit_stop", "heal"]);
function matchesFilter(event) {
  if (activeFilter === "all") return true;
  if (activeFilter === "damage") return event.kind === "damage" || event.kind === "heal";
  if (activeFilter === "system") return systemKinds.has(event.kind);
  return event.kind === activeFilter;
}

function eventIcon(kind) {
  return ({ damage: "−", heal: "+", action: "◆", story: "◇", pause: "Ⅱ", hit_stop: "※", scene: "↗", rebind: "↻", attach: "●", detach: "○" })[kind] || "·";
}

function updateEvents(events) {
  const visible = events.filter((event) => event.id > hiddenThroughId && matchesFilter(event));
  text(ui.eventCount, events.length);
  if (!visible.length) {
    const empty = document.createElement("div");
    empty.className = "empty-state";
    empty.textContent = "当前筛选下没有事件";
    ui.eventList.replaceChildren(empty);
    return;
  }
  const nodes = visible.map((event) => {
    const row = document.createElement("div");
    row.className = `event-item ${event.severity || "info"}`;
    const clock = document.createElement("div");
    clock.className = "event-time";
    clock.textContent = new Date(event.time).toLocaleTimeString("zh-CN", { hour12: false }) + `.${String(new Date(event.time).getMilliseconds()).padStart(3, "0")}`;
    const icon = document.createElement("div");
    icon.className = "event-icon";
    icon.textContent = eventIcon(event.kind);
    const title = document.createElement("div");
    title.className = "event-title";
    title.textContent = event.title;
    const detail = document.createElement("div");
    detail.className = "event-detail";
    detail.textContent = event.detail || "—";
    row.append(clock, icon, title, detail);
    return row;
  });
  ui.eventList.replaceChildren(...nodes);
}

function drawChart(history) {
  const canvas = ui.signalChart;
  const parent = canvas.parentElement;
  const cssWidth = Math.max(10, parent.clientWidth);
  const cssHeight = Math.max(10, parent.clientHeight);
  const dpr = Math.min(2, window.devicePixelRatio || 1);
  if (canvas.width !== Math.floor(cssWidth * dpr) || canvas.height !== Math.floor(cssHeight * dpr)) {
    canvas.width = Math.floor(cssWidth * dpr);
    canvas.height = Math.floor(cssHeight * dpr);
  }
  const ctx = canvas.getContext("2d");
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, cssWidth, cssHeight);
  ui.chartEmpty.classList.toggle("hidden", history.length >= 2);
  if (history.length < 2) return;

  const pad = { left: 5, right: 5, top: 10, bottom: 8 };
  const w = cssWidth - pad.left - pad.right;
  const h = cssHeight - pad.top - pad.bottom;
  ctx.strokeStyle = "rgba(142,154,175,.10)";
  ctx.lineWidth = 1;
  for (let i = 1; i < 4; i += 1) {
    const y = pad.top + h * i / 4;
    ctx.beginPath(); ctx.moveTo(pad.left, y); ctx.lineTo(cssWidth - pad.right, y); ctx.stroke();
  }

  const plot = (ratioAt, color, widthPx = 2) => {
    ctx.beginPath();
    let moved = false;
    history.forEach((point, index) => {
      const ratio = ratioAt(point);
      if (!Number.isFinite(ratio)) return;
      const x = pad.left + w * index / Math.max(1, history.length - 1);
      const y = pad.top + h * (1 - Math.max(0, Math.min(1, ratio)));
      if (!moved) { ctx.moveTo(x, y); moved = true; } else ctx.lineTo(x, y);
    });
    ctx.strokeStyle = color; ctx.lineWidth = widthPx; ctx.lineJoin = "round"; ctx.stroke();
  };
  plot((p) => Number(p.max_hp) > 0 ? Number(p.hp) / Number(p.max_hp) : NaN, "#ff6fae", 2.2);
  plot((p) => Number(p.boss_max_hp) > 0 ? Number(p.boss_hp) / Number(p.boss_max_hp) : NaN, "#ff5d7a", 1.3);
  plot((p) => Number(p.direction_time_scale), "rgba(93,224,234,.7)", 1);
}

function render(snapshot) {
  latestSnapshot = snapshot;
  const state = snapshot.state || {};
  const events = snapshot.events || [];
  updateConnection(state, snapshot.meta || {});
  updateOverview(state, events);
  updateStory(state);
  updateDiagnostics(state);
  updateEvents(events);
  drawChart(snapshot.history || []);
}

async function poll() {
  if (polling) return;
  polling = true;
  try {
    const response = await fetch("/api/snapshot", { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    render(await response.json());
  } catch (error) {
    ui.connectionPill.className = "connection-pill error";
    ui.connectionPill.querySelector("strong").textContent = "服务已断开";
    ui.errorBanner.classList.remove("hidden");
    ui.errorBanner.textContent = `Dashboard API: ${error.message}`;
  } finally {
    polling = false;
  }
}

document.querySelectorAll(".nav-item").forEach((button) => {
  button.addEventListener("click", () => {
    document.querySelectorAll(".nav-item").forEach((item) => item.classList.toggle("active", item === button));
    document.querySelectorAll(".view-section").forEach((section) => section.classList.toggle("active", section.id === button.dataset.target));
    const copy = pageCopy[button.dataset.target];
    text(ui.pageTitle, copy[0]);
    text(ui.pageSubtitle, copy[1]);
    if (button.dataset.target === "overview" && latestSnapshot) requestAnimationFrame(() => drawChart(latestSnapshot.history || []));
  });
});

document.querySelectorAll(".filter").forEach((button) => {
  button.addEventListener("click", () => {
    activeFilter = button.dataset.filter;
    document.querySelectorAll(".filter").forEach((item) => item.classList.toggle("active", item === button));
    if (latestSnapshot) updateEvents(latestSnapshot.events || []);
  });
});

ui.clearVisualEvents.addEventListener("click", () => {
  hiddenThroughId = Math.max(0, ...(latestSnapshot?.events || []).map((event) => event.id));
  if (latestSnapshot) updateEvents(latestSnapshot.events || []);
});

ui.copyJson.addEventListener("click", async () => {
  try {
    await navigator.clipboard.writeText(ui.rawJson.textContent);
    ui.copyJson.textContent = "已复制";
  } catch (_) {
    ui.copyJson.textContent = "复制失败";
  }
  setTimeout(() => { ui.copyJson.textContent = "复制"; }, 1200);
});

window.addEventListener("resize", () => { if (latestSnapshot) drawChart(latestSnapshot.history || []); });
poll();
setInterval(poll, 150);
