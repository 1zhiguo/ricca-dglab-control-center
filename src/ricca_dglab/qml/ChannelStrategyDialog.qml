pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Dialog {
    id: dialog
    objectName: "channelStrategyDialog"
    required property var controller
    signal queueEditorRequested(string channel)
    property string channel: "A"
    property var draft: ({})
    property var catalog: []
    property string category: "battle"
    property string battleFilter: "all"
    property string selectedMode: "hp"
    property string selectedStoryMode: "fixed"
    readonly property var storyModes: [
        {key:"fixed",name:"固定波形"}, {key:"queue",name:"循环队列"},
        {key:"audio",name:"实时音频"}, {key:"fixed_audio",name:"固定＋音频"},
        {key:"queue_audio",name:"循环＋音频"}, {key:"off",name:"关闭剧情输出"}
    ]
    readonly property color accent: channel === "A" ? "#8fbd83" : "#ccab77"
    readonly property var modes: [
        {key:"hp", name:"HP 伤害"}, {key:"action", name:"动作反馈"},
        {key:"both", name:"HP + 动作"}, {key:"none", name:"不接收战斗事件"},
        {key:"off", name:"关闭整个通道"}
    ]
    property var tiers: []
    property var ruleRows: []
    property string errorText: ""
    parent: Overlay.overlay
    anchors.centerIn: parent
    width: Math.min(1100, parent.width - 48)
    height: Math.min(790, parent.height - 40)
    modal: true
    padding: 0
    closePolicy: Popup.CloseOnEscape
    background: Rectangle { color: "#25251c"; radius: 20; border.color: "#574a36" }

    function indexOf(values, key) {
        for (var i=0; i<values.length; ++i) if (values[i].key === key) return i
        return 0
    }
    function setRule(key, field, value) { draft.rules[key][field] = value }
    function setStoryMode(value) {
        selectedStoryMode = value
        draft.story_mode = value
        setRule("defeat_interaction", "playback", value === "queue" || value === "queue_audio" ? "queue" : "wave")
    }
    function refreshRows() {
        if (!draft.rules) { ruleRows = []; return }
        var rows = []
        var order = ["player_down","damage_light","damage_medium","damage_heavy","struggle","hit_small","hit_normal","heavy_land","wall_bounce","armor_break","boss_catch"]
        for (var i=0; i<order.length; ++i) {
            var key = order[i]
            var hp = key.indexOf("damage_") === 0
            var cg = key.indexOf("defeat_") === 0 || key === "player_down"
            var group = key === "player_down" || key === "armor_break" ? "penalty" : hp ? "hp" : "action"
            if (battleFilter !== "all" && battleFilter !== group) continue
            if ((cg && selectedMode !== "off") || (hp && (selectedMode === "hp" || selectedMode === "both")) ||
                (!hp && !cg && (selectedMode === "action" || selectedMode === "both" || selectedMode === "action_audio")))
                rows.push({key:key, rule:draft.rules[key], hp:hp, cg:cg})
        }
        ruleRows = rows
    }
    function filterBattle(value) {
        battleFilter = value
        refreshRows()
        ruleScroll.contentItem.contentY = 0
    }
    function openChannel(value) {
        channel = value
        category = "battle"
        battleFilter = "all"
        catalog = controller.waveformCatalog
        tiers = [
            {key:"low",name:"低 · " + controller.lowStrength},
            {key:"medium",name:"中 · " + controller.mediumStrength},
            {key:"high",name:"高 · " + controller.highStrength},
            {key:"death",name:"死亡 · " + controller.deathStrength},
            {key:"custom",name:"自定义数值"}
        ]
        draft = JSON.parse(JSON.stringify(controller.channelPolicies[value]))
        selectedMode = draft.mode === "action_audio" ? "action" : draft.mode === "audio" ? "none" : draft.mode
        selectedStoryMode = draft.story_mode || (draft.mode === "audio" ? "audio" : (draft.rules.defeat_interaction.playback === "queue" ? "queue" : "fixed") + (draft.mode === "action_audio" ? "_audio" : ""))
        modeChoice.currentIndex = indexOf(modes, selectedMode)
        lightMax.value = Math.round(draft.damage_light_max * 100)
        mediumMax.value = Math.round(draft.damage_medium_max * 100)
        errorText = ""
        refreshRows()
        ruleScroll.contentItem.contentY = 0
        storyScroll.contentItem.contentY = 0
        open()
    }
    function save() {
        if (lightMax.value >= mediumMax.value) {
            errorText = "中伤害上限必须大于小伤害上限。"
            return false
        }
        draft.mode = selectedMode
        draft.story_mode = selectedStoryMode
        draft.damage_light_max = lightMax.value / 100
        draft.damage_medium_max = mediumMax.value / 100
        if (controller.saveChannelPolicy(channel, draft)) { close(); return true }
        errorText = "保存失败，请查看诊断与事件。"
        return false
    }

    component Label: LocalizedText {
        color: "#f3ecd9"; font.family: backend.uiFontFamily; font.pixelSize: 12
        renderType: Text.NativeRendering
    }
    component ActionButton: Button {
        id: button
        implicitHeight: 40; implicitWidth: 100
        contentItem: Label { sourceText: button.text; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter }
        background: Rectangle { color: button.down ? "#4a402c" : "#353025"; radius: 11; border.color: "#6b5c43" }
    }
    component Choice: ComboBox {
        id: choice
        implicitHeight: 38; leftPadding: 12; rightPadding: 28
        font.family: backend.uiFontFamily; font.pixelSize: 11
        background: Rectangle { color: "#353025"; radius: 10; border.color: "#65573f" }
        contentItem: Label { sourceText: choice.displayText; verticalAlignment: Text.AlignVCenter; elide: Text.ElideRight; font.pixelSize: 11 }
        indicator: Label { sourceText: "⌄"; x: choice.width - 22; anchors.verticalCenter: parent.verticalCenter; color: "#aaa68d" }
        delegate: ItemDelegate {
            required property int index
            width: choice.width - 12; height: 40
            contentItem: Label { sourceText: choice.textAt(index); verticalAlignment: Text.AlignVCenter; elide: Text.ElideRight; font.pixelSize: 11 }
            background: Rectangle { radius: 8; color: highlighted ? "#4a402d" : "#25251c" }
        }
        popup: Popup {
            y: choice.height + 4; width: choice.width; padding: 6
            implicitHeight: Math.min(contentItem.implicitHeight + 12, 320)
            background: Rectangle { color: "#25251c"; radius: 12; border.color: "#65573f" }
            contentItem: ListView { clip: true; implicitHeight: contentHeight; model: choice.popup.visible ? choice.delegateModel : null; currentIndex: choice.highlightedIndex; ScrollIndicator.vertical: ScrollIndicator {} }
        }
    }
    component HpInput: SpinBox {
        id: hpInput
        from: 1; to: 100000000; stepSize: 100; editable: true
        implicitWidth: 148; implicitHeight: 38
        validator: DoubleValidator { bottom: 0.01; top: 1000000; decimals: 2; locale: "en_US" }
        textFromValue: function(v, locale) { return (v / 100).toFixed(2) }
        valueFromText: function(text, locale) { return Math.round(Number(text) * 100) }
        contentItem: TextInput {
            text: hpInput.textFromValue(hpInput.value, hpInput.locale)
            color: "#f3ecd9"; font.family: backend.uiFontFamily; font.pixelSize: 12
            horizontalAlignment: Qt.AlignHCenter; verticalAlignment: Qt.AlignVCenter
            readOnly: !hpInput.editable; validator: hpInput.validator; inputMethodHints: Qt.ImhFormattedNumbersOnly
        }
        background: Rectangle { color: "#353025"; radius: 10; border.color: "#65573f" }
        up.indicator: Rectangle { x: hpInput.width - width; width: 26; height: hpInput.height / 2; color: "#443b2b"; Label { anchors.centerIn: parent; sourceText: "+"; font.pixelSize: 12 } MouseArea { anchors.fill: parent; onClicked: hpInput.increase() } }
        down.indicator: Rectangle { x: hpInput.width - width; y: hpInput.height / 2; width: 26; height: hpInput.height / 2; color: "#443b2b"; Label { anchors.centerIn: parent; sourceText: "−"; font.pixelSize: 12 } MouseArea { anchors.fill: parent; onClicked: hpInput.decrease() } }
    }
    component ValueSlider: Slider {
        id: valueSlider
        implicitHeight: 30
        background: Rectangle { x: valueSlider.leftPadding; y: valueSlider.topPadding + valueSlider.availableHeight/2 - height/2; width: valueSlider.availableWidth; height: 5; radius: 3; color: "#5c5038"
            Rectangle { width: parent.width * valueSlider.visualPosition; height: parent.height; radius: 3; color: dialog.accent }
        }
        handle: Rectangle { x: valueSlider.leftPadding + valueSlider.visualPosition * (valueSlider.availableWidth-width); y: valueSlider.topPadding + valueSlider.availableHeight/2-height/2; width: 16; height: 20; radius: 5; color: dialog.accent; border.color: "#f4f1dc"; border.width: valueSlider.pressed ? 2 : 0 }
    }
    component WavePlot: Canvas {
        id: plot
        property var points: []
        property color stroke: "#8fbd83"
        onPointsChanged: requestPaint()
        onWidthChanged: requestPaint()
        onHeightChanged: requestPaint()
        onStrokeChanged: requestPaint()
        onVisibleChanged: if (visible) requestPaint()
        onAvailableChanged: if (available) requestPaint()
        Connections {
            target: dialog
            function onOpened() { Qt.callLater(function() { plot.requestPaint() }) }
        }
        onPaint: {
            var ctx = getContext("2d"); ctx.reset()
            ctx.strokeStyle = "#443e2e"; ctx.lineWidth = 1
            for (var r=1; r<4; ++r) { ctx.beginPath(); ctx.moveTo(0,height*r/4); ctx.lineTo(width,height*r/4); ctx.stroke() }
            if (!points || points.length < 2) return
            ctx.strokeStyle = stroke; ctx.lineWidth = 2.5; ctx.lineJoin = "round"; ctx.beginPath()
            for (var i=0; i<points.length; ++i) {
                var x = i * width / (points.length-1)
                var y = height-5 - points[i]*(height-10)/100
                if (i === 0) ctx.moveTo(x,y); else ctx.lineTo(x,y)
            }
            ctx.stroke()
        }
    }

    component RuleEditor: Rectangle {
        id: row
        required property var modelData
        property var rule: modelData.rule
        property string strengthMode: rule.custom_strength != null ? "custom" : rule.tier
        property real customValue: rule.custom_strength == null ? dialog.controller[rule.tier + "Strength"] : rule.custom_strength
        property real durationValue: rule.duration == null ? 0.1 : rule.duration
        readonly property bool sustained: key === "struggle" || key === "defeat_interaction"
        property string key: modelData.key
        property var waveOptions: key === "defeat_interaction" ? dialog.catalog.concat([{key:"story-queue",name:"自定义队列 → 剧情（保存并跳转）",points:[],color:dialog.accent}]) : dialog.catalog
        property var wave: waveOptions[waveChoice.currentIndex] || ({points:[],color:dialog.accent,frequency:0})
        Layout.fillWidth: true; Layout.preferredHeight: (customStrength.visible ? 176 : 140)
        property bool standalone: false
        radius: standalone ? 0 : 13; color: standalone ? "transparent" : "#353025"; border.color: standalone ? "transparent" : "#574a36"
        ColumnLayout {
            anchors.fill: parent; anchors.margins: 12; spacing: 6
            RowLayout { Layout.fillWidth: true; spacing: 10
                Switch { checked: row.rule.enabled; onToggled: dialog.setRule(row.key, "enabled", checked) }
                Label { sourceText: row.modelData.cg ? (row.key === "player_down" ? "死亡惩罚" : "CG · 剧情输出") : (row.modelData.hp ? "HP · " : "动作 · ") + row.rule.label; font.bold: true; Layout.preferredWidth: 176 }
                Choice {
                    Layout.preferredWidth: 145; model: dialog.tiers; textRole: "name"; valueRole: "key"
                    currentIndex: dialog.indexOf(dialog.tiers, row.strengthMode)
                    onActivated: {
                        row.strengthMode = currentValue
                        if (currentValue === "custom") dialog.setRule(row.key,"custom_strength",Math.round(strengthSlider.value))
                        else { dialog.setRule(row.key,"tier",currentValue); dialog.setRule(row.key,"custom_strength",null) }
                    }
                    id: strengthChoice
                    enabled: !(row.key === "defeat_interaction" && (dialog.selectedStoryMode === "queue" || dialog.selectedStoryMode === "queue_audio" || dialog.selectedStoryMode === "off"))
                    objectName: row.key + "StrengthChoice"
                }
                Choice {
                    id: waveChoice
                    displayText: row.key === "defeat_interaction" && dialog.selectedStoryMode === "audio" ? "实时音频包络（自动生成）" : currentText
                    enabled: row.key !== "defeat_interaction" || (dialog.selectedStoryMode !== "audio" && dialog.selectedStoryMode !== "off")
                    objectName: row.key + "WaveChoice"
                    Layout.fillWidth: true; model: row.waveOptions; textRole: "name"; valueRole: "key"
                    currentIndex: dialog.indexOf(row.waveOptions, row.key === "defeat_interaction" && (dialog.selectedStoryMode === "queue" || dialog.selectedStoryMode === "queue_audio") ? "story-queue" : row.rule.wave)
                    onActivated: {
                        if (currentValue === "story-queue") {
                            dialog.setStoryMode(dialog.selectedStoryMode.indexOf("audio") >= 0 ? "queue_audio" : "queue")
                            if (dialog.save()) dialog.queueEditorRequested(dialog.channel)
                        } else {
                            dialog.setRule(row.key,"wave",currentValue)
                            if (row.key === "defeat_interaction") dialog.setStoryMode(dialog.selectedStoryMode.indexOf("audio") >= 0 ? "fixed_audio" : "fixed")
                        }
                    }
                    delegate: ItemDelegate {
                        id: waveOption
                        required property int index
                        width: waveChoice.width - 12; height: 52
                        contentItem: RowLayout {
                            Label { Layout.preferredWidth: 125; sourceText: waveChoice.textAt(index); elide: Text.ElideRight; font.pixelSize: 11 }
                            WavePlot { Layout.fillWidth: true; Layout.preferredHeight: 36; points: row.waveOptions[waveOption.index].points; stroke: row.waveOptions[waveOption.index].color }
                        }
                        background: Rectangle { radius: 8; color: highlighted ? "#4a402d" : "#25251c" }
                    }
                }
            }
            RowLayout {
                id: customStrength
                visible: row.strengthMode === "custom" && !(row.key === "defeat_interaction" && (dialog.selectedStoryMode === "queue" || dialog.selectedStoryMode === "queue_audio" || dialog.selectedStoryMode === "off"))
                Layout.fillWidth: true
                Label { sourceText: "自定义强度"; color: "#aaa68d"; Layout.preferredWidth: 95; font.pixelSize: 11 }
                ValueSlider { id: strengthSlider; objectName: row.key + "CustomStrength"; Layout.fillWidth: true; from: 0; to: 100; stepSize: 1; value: row.customValue; onMoved: { row.customValue = Math.round(value); dialog.setRule(row.key,"custom_strength",row.customValue) } }
                Label { sourceText: Math.round(strengthSlider.value); color: dialog.accent; Layout.preferredWidth: 48 }
            }
            RowLayout { Layout.fillWidth: true; spacing: 14
                Label { sourceText: row.sustained ? "持续方式" : "持续时间"; color: "#aaa68d"; Layout.preferredWidth: 70; font.pixelSize: 11 }
                ValueSlider { id: durationSlider; objectName: row.key + "Duration"; visible: !row.sustained; Layout.fillWidth: true; from: 0.1; to: row.rule.max_duration || 3.0; stepSize: 0.1; value: row.durationValue; onMoved: { row.durationValue = Math.round(value*100)/100; dialog.setRule(row.key,"duration",row.durationValue) } }
                Label { sourceText: row.key === "defeat_interaction" ? "登记场景内循环 · 离开即解除" : row.sustained ? "持续至挣脱 · 不按秒计时" : durationSlider.value.toFixed(2) + " 秒"; color: dialog.accent; Layout.fillWidth: row.sustained; Layout.preferredWidth: row.sustained ? 220 : 68 }
                ActionButton { objectName:"openStoryQueueFromStrategy"; visible:row.key === "defeat_interaction" && (dialog.selectedStoryMode === "queue" || dialog.selectedStoryMode === "queue_audio"); Layout.preferredWidth:200; text:"编辑队列 → 剧情"; onClicked:{ if(dialog.save()) dialog.queueEditorRequested(dialog.channel) } }
                Rectangle { visible:!(row.key === "defeat_interaction" && (dialog.selectedStoryMode === "queue" || dialog.selectedStoryMode === "queue_audio" || dialog.selectedStoryMode === "audio" || dialog.selectedStoryMode === "off")); Layout.preferredWidth: 200; Layout.preferredHeight: 44; radius: 8; color: "#142017"
                    WavePlot { anchors.fill: parent; anchors.margins: 5; points: row.wave.points; stroke: row.wave.color }
                }
            }
            Label { sourceText: row.key === "defeat_interaction" ? "已登记场景从剧情开始循环，包含回想 / 鉴赏；离开、插件暂停或读数失效立即停止。" : row.key === "player_down" ? "仅 HP 从正数归零触发一次，持续 0.1–10 秒；进入 CG 不重复触发，优先于普通暂停，仍受硬上限与紧急归零约束。" : row.sustained ? "受困期间保持所选强度与波形，不按秒计时；挣脱、暂停或读取失效时停止。" : "按所选档位或自定义数值触发，逐渐回落；碎甲升敏后仍受安全上限约束。"; color: row.modelData.cg ? "#e6be73" : "#aaa68d"; font.pixelSize: 9; Layout.fillWidth: true; wrapMode: Text.WordWrap }
        }
    }

    contentItem: ColumnLayout {
        anchors.fill: parent; anchors.margins: 22; spacing: 12
        Item {
            Layout.fillWidth: true; Layout.preferredHeight: 54
            ColumnLayout { anchors.left: parent.left; anchors.right: cancelButton.left; anchors.rightMargin: 14; anchors.verticalCenter: parent.verticalCenter; spacing: 3
                Label { sourceText: dialog.channel + " 通道策略"; font.pixelSize: 23; font.bold: true; color: dialog.accent }
                Label { sourceText: "独立配置 · 重叠时较强者接管，同强度刷新时长，较弱者忽略"; color: "#aaa68d"; font.pixelSize: 11 }
            }
            ActionButton { id: cancelButton; anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter; text: "取消"; onClicked: dialog.close() }
        }
        RowLayout {
            Layout.fillWidth: true; spacing: 12
            Repeater {
                model: [{key:"battle",name:"战斗反馈",object:"strategyBattleTab"}, {key:"story",name:"剧情 / 鉴赏",object:"strategyStoryTab"}]
                delegate: ActionButton {
                    required property var modelData
                    objectName: modelData.object
                    text: modelData.name; Layout.fillWidth:true; implicitHeight:44
                    onClicked:dialog.category = modelData.key
                    background: Rectangle { radius:11; color:dialog.category === modelData.key ? "#4a5036" : "#353025"; border.color:dialog.category === modelData.key ? dialog.accent : "#65573f" }
                }
            }
        }
        RowLayout {
            visible:dialog.category === "battle"
            Layout.fillWidth: true; spacing: 14
            Label { sourceText: "战斗来源"; font.bold: true }
            Choice {
                id: modeChoice
                objectName: "channelModeChoice"
                Layout.preferredWidth: 220; model: dialog.modes; textRole: "name"; valueRole: "key"
                onActivated: { dialog.selectedMode = currentValue; dialog.refreshRows() }
            }
            Label { Layout.fillWidth: true; wrapMode: Text.WordWrap; sourceText: dialog.selectedMode === "off" ? "此通道整体关闭，包括剧情和死亡惩罚。" : dialog.selectedMode === "none" ? "不接收 HP、动作或捕获事件；剧情输出与死亡惩罚仍按独立设置执行。" : "仅设置战斗来源；剧情 / 鉴赏请切换顶部分类。HP 与动作重叠只取较强者，不叠加强度。"; color: "#aaa68d"; font.pixelSize: 10 }
        }
        Rectangle {
            visible: dialog.category === "battle" && (dialog.battleFilter === "all" || dialog.battleFilter === "hp") && (dialog.selectedMode === "hp" || dialog.selectedMode === "both")
            Layout.fillWidth: true; Layout.preferredHeight: 88; color: "#142017"; radius: 12; border.color: "#574a36"
            ColumnLayout { anchors.fill: parent; anchors.margins: 12; spacing: 7
                RowLayout { spacing: 12; Label { sourceText: "小伤害 ≤" } HpInput { id: lightMax } Label { sourceText: "HP"; color: "#aaa68d" } Label { sourceText: "中伤害 ≤" } HpInput { id: mediumMax } Label { sourceText: "HP · 超出为重伤害"; color: "#aaa68d" } }
                Label { sourceText: "按实际扣血量分级，含上限；300 ms 内连续掉血合并计算。支持小数。"; color: "#aaa68d"; font.pixelSize: 10 }
            }
        }
        Rectangle {
            visible: dialog.category === "battle" && dialog.selectedMode === "off"
            Layout.fillWidth: true; Layout.fillHeight: dialog.selectedMode === "off"; Layout.preferredHeight: 150; color: "#142017"; radius: 14; border.color: "#574a36"
            ColumnLayout { anchors.fill: parent; anchors.margins: 22; spacing: 14
                Label { sourceText: dialog.selectedMode === "action_audio" ? "战斗动作 → 剧情音频队列" : dialog.selectedMode === "audio" ? "剧情实时音频包络（兼容模式）" : "此通道关闭"; font.pixelSize: 19; font.bold: true }
                Label { Layout.fillWidth: true; wrapMode: Text.WordWrap; sourceText: dialog.selectedMode === "action_audio" ? "在音频共感页启用监听；在下方 CG 剧情循环选择自定义队列。波形按队列播放，音量只缩放当前段强度；静音归零，战斗不响应音频。" : dialog.selectedMode === "audio" ? "旧模式保留：仅在剧情响应，波形随音频包络生成。新设计请选择“动作＋剧情音频队列”。" : "不会接收 HP、动作或剧情音频信号。"; color: "#aaa68d"; font.pixelSize: 13 }
                Label { visible: dialog.selectedMode === "audio"; sourceText: dialog.controller.audioEmpathyEnabled ? "音频总开关已启用" : "音频总开关当前关闭"; color: dialog.accent }
                Item { Layout.fillHeight: true }
            }
        }
        RowLayout {
            visible:dialog.category === "battle" && dialog.selectedMode !== "off"
            Layout.fillWidth:true; spacing:10
            Label { sourceText:"事件筛选"; color:"#aaa68d"; Layout.preferredWidth:70 }
            Repeater {
                model:[{key:"all",name:"全部"}, {key:"hp",name:"HP"}, {key:"action",name:"动作"}, {key:"penalty",name:"高强度惩罚"}]
                delegate:ActionButton {
                    required property var modelData
                    objectName:"battleFilter_" + modelData.key
                    text:modelData.name; Layout.preferredWidth:modelData.key === "penalty" ? 145 : 100
                    onClicked:dialog.filterBattle(modelData.key)
                    background:Rectangle { radius:10; color:dialog.battleFilter === modelData.key ? "#4a5036" : "#353025"; border.color:dialog.battleFilter === modelData.key ? dialog.accent : "#65573f" }
                }
            }
            Item { Layout.fillWidth:true }
        }
        Label { visible:dialog.category === "battle" && dialog.selectedMode !== "off" && dialog.ruleRows.length === 0; Layout.fillWidth:true; wrapMode:Text.WordWrap; color:"#aaa68d"; sourceText:"当前战斗来源下没有这类事件。筛选仅改变显示，不启用或停用反馈。" }
        ScrollView {
            id: ruleScroll
            visible: dialog.category === "battle" && dialog.selectedMode !== "off"
            Layout.fillWidth: true; Layout.fillHeight: true; clip: true
            rightPadding: 14; contentWidth: availableWidth
            ScrollBar.vertical: ScrollBar {
                parent: ruleScroll
                anchors.top: parent.top; anchors.bottom: parent.bottom; anchors.right: parent.right
                policy: ScrollBar.AsNeeded; width: 8
                contentItem: Rectangle { implicitWidth: 6; radius: 3; color: "#7d7056" }
                background: Rectangle { color: "#142017"; radius: 4 }
            }
            ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
            ColumnLayout {
                width: ruleScroll.availableWidth; spacing: 10
                Repeater {
                    model: dialog.ruleRows
                    delegate: RuleEditor {}
                }
            }
        }
        ScrollView {
            id:storyScroll
            objectName:"storyStrategyPanel"
            visible:dialog.category === "story"
            Layout.fillWidth:true; Layout.fillHeight:true; clip:true
            contentWidth:availableWidth
            ColumnLayout {
                width:storyScroll.availableWidth; spacing:16
                Label { sourceText:"剧情 / 鉴赏策略"; font.pixelSize:19; font.bold:true; color:dialog.accent }
                Label { Layout.fillWidth:true; wrapMode:Text.WordWrap; color:"#aaa68d"; sourceText:"只配置进入剧情、Scene 或鉴赏后的输出；与战斗反馈独立配置，底部统一保存。死亡惩罚仍优先。"; font.pixelSize:11 }
                RowLayout {
                    Layout.fillWidth:true; spacing:14
                    Label { sourceText:"播放方式"; font.bold:true }
                    Choice { objectName:"storyModeChoice"; Layout.preferredWidth:240; model:dialog.storyModes; textRole:"name"; valueRole:"key"; currentIndex:dialog.indexOf(dialog.storyModes,dialog.selectedStoryMode); onActivated:dialog.setStoryMode(currentValue) }
                    Label { Layout.fillWidth:true; wrapMode:Text.WordWrap; color:dialog.accent; font.pixelSize:11; sourceText:dialog.selectedStoryMode.indexOf("audio") >= 0 ? "音频须开启监听；＋音频只缩放强度，静音归零。" : "固定重复同一波形；循环按队列逐段播放，不依赖音频。" }
                }
                Rectangle { Layout.fillWidth:true; height:1; color:"#574a36" }
                RuleEditor {
                    objectName:"storyStrategySettings"
                    standalone:true
                    modelData: ({key:"defeat_interaction", rule:dialog.draft.rules ? dialog.draft.rules.defeat_interaction : dialog.controller.channelPolicies[dialog.channel].rules.defeat_interaction, hp:false, cg:true})
                }
                Label { visible:dialog.selectedMode === "off"; Layout.fillWidth:true; wrapMode:Text.WordWrap; color:"#e6be73"; sourceText:"注意：该通道整体关闭，剧情配置可以保存，但不会输出。请在战斗反馈页恢复通道来源后使用。" }
            }
        }
        Label { visible: dialog.errorText !== ""; sourceText: dialog.errorText; color: "#ff5d7a" }
        RowLayout { Layout.fillWidth: true
            Label { Layout.fillWidth: true; sourceText: "档位跟随个性化范围 · 当前硬上限 " + dialog.controller.hardCap + " · 保存后自动应用，保留手动暂停状态"; color: "#aaa68d"; font.pixelSize: 10 }
            ActionButton { text: "保存 " + dialog.channel + " 通道策略"; implicitWidth: 190; onClicked: dialog.save() }
        }
    }
}
