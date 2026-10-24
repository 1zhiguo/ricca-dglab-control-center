"""Independent Opossum settings surface; never changes electrical settings.

The adapter deliberately owns no Socket sender and never authorizes output.
The application applies its saved settings through onOvcSettingsChanged().
"""
from __future__ import annotations

from copy import deepcopy
import math

from PySide6.QtCore import QObject, Property, Signal, Slot

from . import ovc
from .product_config import story_mode, story_queue_switch
from .story_queue import MAX_STEPS, sanitize_steps


class OvcController(QObject):
    changed = Signal()
    languageChanged = Signal()

    def __init__(self, backend: QObject) -> None:
        super().__init__(backend)
        self._backend = backend
        self._catalog = ovc.waveform_catalog()
        self._queue_status: dict = {}
        self._backend.languageChanged.connect(self.languageChanged.emit)

    @property
    def _profile(self) -> dict:
        return self._backend._config.values["ovc_profile"]

    def _toast(self, title: str, detail: str) -> None:
        self._backend.toastRequested.emit(title, detail)

    def _save(self, changes: dict, *, story_channel: str | None = None) -> bool:
        try:
            self._backend._config.update({"ovc_profile": {**self._profile, **changes}})
        except (OSError, ValueError, TypeError) as error:
            self._toast("保存失败", str(error))
            return False
        targeted = getattr(self._backend, "onOvcStoryToggleChanged", None)
        callback = getattr(self._backend, "onOvcSettingsChanged", None)
        if story_channel is not None and callable(targeted):
            targeted(story_channel)
            callback = None
            self.changed.emit()
            self._toast("保存成功", "剧情通道开关已立即保存并应用；设备暂停状态保持不变。")
            return True
        if callable(callback):
            callback()
        else:
            pipeline = getattr(self._backend, "_ovc_pipeline", None)
            if pipeline is not None:
                pipeline.configure(deepcopy(self._profile))
        self.changed.emit()
        self._toast("保存成功", "负鼠设置已保存；郊狼 Pulse 配置保持不变。")
        return True

    @Property(str, constant=True)
    def outputProfile(self) -> str:
        return "ovc"

    @Property(str, notify=languageChanged)
    def language(self) -> str:
        return self._backend.language

    @Slot(str, str, result=str)
    def localize(self, source: str, language: str) -> str:
        return self._backend.localize(source, language)

    @Property("QVariantMap", notify=changed)
    def channelPolicies(self) -> dict:
        return self._profile["channel_policies"]

    @Property("QVariantList", notify=changed)
    def waveformCatalog(self) -> list:
        return self._catalog

    @Property("QVariantMap", notify=changed)
    def storyQueues(self) -> dict:
        return self._profile["story_queues"]

    @Property("QVariantMap", notify=changed)
    def storyQueueStatus(self) -> dict:
        return self._queue_status

    @Slot("QVariantMap")
    def updateStatus(self, status: dict) -> None:
        if self._queue_status != status:
            self._queue_status = deepcopy(status)
            self.changed.emit()

    @Property(int, notify=changed)
    def lowStrength(self) -> int:
        return self._profile["strength_low"]

    @Property(int, notify=changed)
    def mediumStrength(self) -> int:
        return self._profile["strength_medium"]

    @Property(int, notify=changed)
    def highStrength(self) -> int:
        return self._profile["strength_high"]

    @Property(int, notify=changed)
    def deathStrength(self) -> int:
        return self._profile["strength_death"]

    @Property(int, notify=changed)
    def hardCap(self) -> int:
        return self._profile["hard_cap"]

    @Property(bool, notify=changed)
    def audioEmpathyEnabled(self) -> bool:
        return bool(self._backend.audioEmpathyEnabled)

    @Property(float, notify=changed)
    def audioGain(self) -> float:
        return float(self._profile.get("audio_gain", 1.0))

    @Property(int, notify=changed)
    def audioQueueMinimum(self) -> int:
        return min(self.hardCap, int(self._profile.get("audio_queue_minimum", 0)))

    @Slot(str, result=str)
    def channelModeName(self, channel: str) -> str:
        mode = self.channelPolicies.get(channel, {}).get("mode", "off")
        return {"hp": "HP 伤害", "action": "动作反馈", "both": "HP + 动作",
                "none": "不接收战斗事件", "audio": "剧情音频（旧包络）",
                "action_audio": "战斗动作 / 剧情音频队列", "off": "关闭"}.get(mode, "关闭")

    @Slot(str, result="QVariantList")
    def waveformPoints(self, key: str) -> list:
        return next((list(wave["points"]) for wave in self._catalog if wave["key"] == key), [])

    @Slot(str, result=str)
    def waveformName(self, key: str) -> str:
        return next((wave["name"] for wave in self._catalog if wave["key"] == key), key)

    @Slot(int, int, int, int, int, result=bool)
    def saveIntensitySettings(self, low: int, medium: int, high: int,
                              death: int, hard_cap: int) -> bool:
        if not 0 <= low <= medium <= high <= death <= hard_cap <= 200 or any(
                value % 10 for value in (low, medium, high, death, hard_cap)):
            self._toast("保存失败", "负鼠强度须为 0–200 的 10 的倍数，且低 ≤ 中 ≤ 高 ≤ 死亡 ≤ 硬上限。")
            return False
        return self._save(dict(strength_low=low, strength_medium=medium,
                               strength_high=high, strength_death=death, hard_cap=hard_cap))

    @Slot(str, "QVariantMap", result=bool)
    def saveChannelPolicy(self, channel: str, policy: dict) -> bool:
        if channel not in {"A", "B"} or not isinstance(policy, dict):
            return False
        mode = policy.get("mode")
        if not isinstance(mode, str) or mode not in {"hp", "action", "both", "none", "audio", "off", "action_audio"}:
            return False
        if "story_mode" in policy and (not isinstance(policy["story_mode"], str) or policy["story_mode"] not in {"fixed", "queue", "audio", "fixed_audio", "queue_audio", "off"}):
            return False
        try:
            light, medium = float(policy["damage_light_max"]), float(policy["damage_medium_max"])
        except (KeyError, ValueError, TypeError, OverflowError):
            return False
        if not math.isfinite(light) or not math.isfinite(medium) or not 0 < light < medium:
            self._toast("保存失败", "中伤害上限必须大于小伤害上限。")
            return False
        incoming_rules = policy.get("rules")
        if not isinstance(incoming_rules, dict) or set(incoming_rules) != set(self.channelPolicies[channel]["rules"]):
            return False
        allowed = {wave["key"] for wave in self._catalog}
        for key, rule in incoming_rules.items():
            if key not in self.channelPolicies[channel]["rules"] or not isinstance(rule, dict):
                return False
            if rule.get("wave") not in allowed:
                self._toast("保存失败", "负鼠策略只能选择负鼠振动波形。")
                return False
            custom = rule.get("custom_strength")
            if custom is not None and (type(custom) not in (int, float) or not math.isfinite(custom)
                                       or not 0 <= custom <= 200):
                return False
        policies = deepcopy(self.channelPolicies)
        policies[channel] = deepcopy(policy)
        for rule in policies[channel]["rules"].values():
            if rule.get("custom_strength") is not None:
                rule["custom_strength"] = int(rule["custom_strength"] // 10) * 10
        return self._save({"channel_policies": policies})

    @Slot(str, "QVariantList", bool, result=bool)
    def saveStoryQueue(self, channel: str, steps: list, use_queue: bool) -> bool:
        if channel not in {"A", "B"} or not isinstance(steps, list) or not 1 <= len(steps) <= MAX_STEPS:
            self._toast("保存失败", "队列须包含 1–16 段。")
            return False
        if any(isinstance(step, dict) and step.get("custom_strength") is not None and (
                type(step["custom_strength"]) not in (int, float) or not math.isfinite(step["custom_strength"])
                or not 0 <= step["custom_strength"] <= 200) for step in steps):
            return False
        clean = sanitize_steps(steps, max_strength=200)
        for step in clean:
            if step["custom_strength"] is not None:
                step["custom_strength"] = step["custom_strength"] // 10 * 10
        allowed = set(ovc.OVC_WAVEFORMS) | {"idle"}
        if len(clean) != len(steps) or any(step["wave"] not in allowed for step in clean):
            self._toast("保存失败", "负鼠策略只能选择负鼠振动波形。")
            return False
        queues, policies = deepcopy(self.storyQueues), deepcopy(self.channelPolicies)
        queues[channel] = clean
        policy = policies[channel]
        policies[channel] = story_queue_switch(policy, use_queue)
        return self._save({"story_queues": queues, "channel_policies": policies})

    @Slot(str, bool, result=bool)
    def setStoryQueueEnabled(self, channel: str, enabled: bool) -> bool:
        if channel not in {"A", "B"}:
            return False
        if enabled and not self.storyQueues[channel]:
            self._toast("保存失败", "队列须包含 1–16 段。")
            return False
        policies = deepcopy(self.channelPolicies)
        policies[channel] = story_queue_switch(policies[channel], enabled)
        return self._save({"channel_policies": policies}, story_channel=channel)

    @Slot(float, result=bool)
    def saveAudioGain(self, value: float) -> bool:
        if not math.isfinite(value) or not 0 <= value <= 10:
            return False
        return self._save({"audio_gain": round(value, 1)})

    @Slot(int, result=bool)
    def saveAudioQueueMinimum(self, value: int) -> bool:
        if not 0 <= value <= self.hardCap or value % 10:
            return False
        return self._save({"audio_queue_minimum": value})

    @Slot(result=bool)
    def resetEventMappings(self) -> bool:
        defaults = ovc.default_ovc_profile()
        return self._save({key: defaults[key] for key in ("event_rules", "channel_policies")})
