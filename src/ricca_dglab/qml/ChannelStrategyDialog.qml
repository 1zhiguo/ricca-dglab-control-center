pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Dialog {
    id: dialog
    objectName: "channelStrategyDialog"
    required property var controller
    property string channel: "A"
    property var draft: ({})
    property var catalog: []
    property string selectedMode: "hp"
    readonly property color accent: channel === "A" ? "#5de0ea" : "#a78bfa"
    readonly property var modes: [
        {key:"hp", name:"HP 伤害"}, {key:"action", name:"动作反馈"},
        {key:"both", name:"HP + 动作"}, {key:"audio", name:"剧情音频"}, {key:"off", name:"关闭"}
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
    background: Rectangle { color: "#101725"; radius: 20; border.color: "#2a3850" }

    function indexOf(values, key) {
        for (var i=0; i<values.length; ++i) if (values[i].key === key) return i
        return 0
    }
    function setRule(key, field, value) { draft.rules[key][field] = value }
    function refreshRows() {
        if (!draft.rules) { ruleRows = []; return }
        var rows = []
        var order = ["defeat_scene_enter","defeat_interaction","damage_light","damage_medium","damage_heavy","capture_start","struggle","hit_small","hit_normal","heavy_land","wall_bounce","armor_break","boss_catch","player_down"]
        for (var i=0; i<order.length; ++i) {
            var key = order[i]
            var hp = key.indexOf("damage_") === 0
            var cg = key.indexOf("defeat_") === 0
            if ((cg && selectedMode !== "off") || (hp && (selectedMode === "hp" || selectedMode === "both")) ||
                (!hp && !cg && (selectedMode === "action" || selectedMode === "both")))
                rows.push({key:key, rule:draft.rules[key], hp:hp, cg:cg})
        }
        ruleRows = rows
    }
    function openChannel(value) {
        channel = value
        catalog = controller.waveformCatalog
        tiers = [
            {key:"low",name:"低 · " + controller.lowStrength},
            {key:"medium",name:"中 · " + controller.mediumStrength},
            {key:"high",name:"高 · " + controller.highStrength},
            {key:"death",name:"死亡 · " + controller.deathStrength},
            {key:"custom",name:"自定义数值"}
        ]
        draft = JSON.parse(JSON.stringify(controller.channelPolicies[value]))
        selectedMode = draft.mode
        modeChoice.currentIndex = indexOf(modes, selectedMode)
        lightMax.value = Math.round(draft.damage_light_max * 100)
        mediumMax.value = Math.round(draft.damage_medium_max * 100)
        errorText = ""
        refreshRows()
        open()
    }
    function save() {
        if (lightMax.value >= mediumMax.value) {
            errorText = "中伤害上限必须大于小伤害上限。"
            return
        }
        draft.mode = selectedMode
        draft.damage_light_max = lightMax.value / 100
        draft.damage_medium_max = mediumMax.value / 100
        if (controller.saveChannelPolicy(channel, draft)) close()
        else errorText = "保存失败，请查看诊断与事件。"
    }

    component Label: Text {
        color: "#f7f9fd"; font.family: "Microsoft YaHei UI"; font.pixelSize: 12
        renderType: Text.NativeRendering
    }
    component ActionButton: Button {
        id: button
        implicitHeight: 40; implicitWidth: 100
        contentItem: Label { text: button.text; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter }
        background: Rectangle { color: button.down ? "#25344e" : "#172134"; radius: 11; border.color: "#3a4a63" }
    }
    component Choice: ComboBox {
        id: choice
        implicitHeight: 38; leftPadding: 12; rightPadding: 28
        font.family: "Microsoft YaHei UI"; font.pixelSize: 11
        background: Rectangle { color: "#172134"; radius: 10; border.color: "#34465f" }
        contentItem: Label { text: choice.displayText; verticalAlignment: Text.AlignVCenter; elide: Text.ElideRight; font.pixelSize: 11 }
        indicator: Label { text: "⌄"; x: choice.width - 22; anchors.verticalCenter: parent.verticalCenter; color: "#8e9aaf" }
        delegate: ItemDelegate {
            required property int index
            width: choice.width - 12; height: 40
            contentItem: Label { text: choice.textAt(index); verticalAlignment: Text.AlignVCenter; elide: Text.ElideRight; font.pixelSize: 11 }
            background: Rectangle { radius: 8; color: highlighted ? "#29364e" : "#101725" }
        }
        popup: Popup {
            y: choice.height + 4; width: choice.width; padding: 6
            implicitHeight: Math.min(contentItem.implicitHeight + 12, 320)
            background: Rectangle { color: "#101725"; radius: 12; border.color: "#34465f" }
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
            color: "#f7f9fd"; font.family: "Microsoft YaHei UI"; font.pixelSize: 12
            horizontalAlignment: Qt.AlignHCenter; verticalAlignment: Qt.AlignVCenter
            readOnly: !hpInput.editable; validator: hpInput.validator; inputMethodHints: Qt.ImhFormattedNumbersOnly
        }
        background: Rectangle { color: "#172134"; radius: 10; border.color: "#34465f" }
        up.indicator: Rectangle { x: hpInput.width - width; width: 26; height: hpInput.height / 2; color: "#22314a"; Label { anchors.centerIn: parent; text: "+"; font.pixelSize: 12 } MouseArea { anchors.fill: parent; onClicked: hpInput.increase() } }
        down.indicator: Rectangle { x: hpInput.width - width; y: hpInput.height / 2; width: 26; height: hpInput.height / 2; color: "#22314a"; Label { anchors.centerIn: parent; text: "−"; font.pixelSize: 12 } MouseArea { anchors.fill: parent; onClicked: hpInput.decrease() } }
    }
    component ValueSlider: Slider {
        id: valueSlider
        implicitHeight: 30
        background: Rectangle { x: valueSlider.leftPadding; y: valueSlider.topPadding + valueSlider.availableHeight/2 - height/2; width: valueSlider.availableWidth; height: 5; radius: 3; color: "#30405a"
            Rectangle { width: parent.width * valueSlider.visualPosition; height: parent.height; radius: 3; color: dialog.accent }
        }
        handle: Rectangle { x: valueSlider.leftPadding + valueSlider.visualPosition * (valueSlider.availableWidth-width); y: valueSlider.topPadding + valueSlider.availableHeight/2-height/2; width: 16; height: 20; radius: 5; color: dialog.accent; border.color: "#edfaff"; border.width: valueSlider.pressed ? 2 : 0 }
    }
    component WavePlot: Canvas {
        property var points: []
        property color stroke: "#5de0ea"
        onPointsChanged: requestPaint()
        onWidthChanged: requestPaint()
        onHeightChanged: requestPaint()
        onStrokeChanged: requestPaint()
        onPaint: {
            var ctx = getContext("2d"); ctx.reset()
            ctx.strokeStyle = "#27344a"; ctx.lineWidth = 1
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

    contentItem: ColumnLayout {
        anchors.fill: parent; anchors.margins: 22; spacing: 12
        Item {
            Layout.fillWidth: true; Layout.preferredHeight: 54
            ColumnLayout { anchors.left: parent.left; anchors.right: cancelButton.left; anchors.rightMargin: 14; anchors.verticalCenter: parent.verticalCenter; spacing: 3
                Label { text: dialog.channel + " 通道策略"; font.pixelSize: 23; font.bold: true; color: dialog.accent }
                Label { text: "独立配置 · 重叠时较强者接管，同强度刷新时长，较弱者忽略"; color: "#8e9aaf"; font.pixelSize: 11 }
            }
            ActionButton { id: cancelButton; anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter; text: "取消"; onClicked: dialog.close() }
        }
        RowLayout {
            Layout.fillWidth: true; spacing: 14
            Label { text: "信号来源"; font.bold: true }
            Choice {
                id: modeChoice
                objectName: "channelModeChoice"
                Layout.preferredWidth: 220; model: dialog.modes; textRole: "name"; valueRole: "key"
                onActivated: { dialog.selectedMode = currentValue; dialog.refreshRows() }
            }
            Label { Layout.fillWidth: true; wrapMode: Text.WordWrap; text: dialog.selectedMode === "both" ? "HP 与动作在本通道竞争；只播放较强的一种，不叠加强度。" : "两通道互不抢占，可选择相同或不同的来源。"; color: "#8e9aaf"; font.pixelSize: 10 }
        }
        Rectangle {
            visible: dialog.selectedMode === "hp" || dialog.selectedMode === "both"
            Layout.fillWidth: true; Layout.preferredHeight: 88; color: "#0b1220"; radius: 12; border.color: "#2a3850"
            ColumnLayout { anchors.fill: parent; anchors.margins: 12; spacing: 7
                RowLayout { spacing: 12; Label { text: "小伤害 ≤" } HpInput { id: lightMax } Label { text: "HP"; color: "#8e9aaf" } Label { text: "中伤害 ≤" } HpInput { id: mediumMax } Label { text: "HP · 超出为重伤害"; color: "#8e9aaf" } }
                Label { text: "按实际扣血量分级，含上限；300 ms 内连续掉血合并计算。支持小数。"; color: "#8e9aaf"; font.pixelSize: 10 }
            }
        }
        Rectangle {
            visible: dialog.selectedMode === "audio" || dialog.selectedMode === "off"
            Layout.fillWidth: true; Layout.fillHeight: dialog.selectedMode === "off"; Layout.preferredHeight: 150; color: "#0b1220"; radius: 14; border.color: "#2a3850"
            ColumnLayout { anchors.fill: parent; anchors.margins: 22; spacing: 14
                Label { text: dialog.selectedMode === "audio" ? "剧情实时音频包络" : "此通道关闭"; font.pixelSize: 19; font.bold: true }
                Label { Layout.fillWidth: true; wrapMode: Text.WordWrap; text: dialog.selectedMode === "audio" ? "仅在 ADV / ATD 剧情场景响应。去“音频共感”页选择音频源、启用监听并调整灵敏度与门限。波形随声音实时生成，不使用受击预设。" : "不会接收 HP、动作或剧情音频信号。"; color: "#8e9aaf"; font.pixelSize: 13 }
                Label { visible: dialog.selectedMode === "audio"; text: dialog.controller.audioEmpathyEnabled ? "音频总开关已启用" : "音频总开关当前关闭"; color: dialog.accent }
                Item { Layout.fillHeight: true }
            }
        }
        ScrollView {
            id: ruleScroll
            visible: dialog.selectedMode !== "off"
            Layout.fillWidth: true; Layout.fillHeight: true; clip: true
            rightPadding: 14; contentWidth: availableWidth
            ScrollBar.vertical: ScrollBar {
                parent: ruleScroll
                anchors.top: parent.top; anchors.bottom: parent.bottom; anchors.right: parent.right
                policy: ScrollBar.AsNeeded; width: 8
                contentItem: Rectangle { implicitWidth: 6; radius: 3; color: "#53627b" }
                background: Rectangle { color: "#0b1220"; radius: 4 }
            }
            ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
            ColumnLayout {
                width: ruleScroll.availableWidth; spacing: 10
                Repeater {
                    model: dialog.ruleRows
                    delegate: Rectangle {
                        id: row
                        required property var modelData
                        property var rule: modelData.rule
                        property string strengthMode: rule.custom_strength != null ? "custom" : rule.tier
                        property real customValue: rule.custom_strength == null ? dialog.controller[rule.tier + "Strength"] : rule.custom_strength
                        property real durationValue: rule.duration == null ? 0.1 : rule.duration
                        readonly property bool sustained: key === "struggle" || key === "defeat_interaction"
                        property string key: modelData.key
                        property var wave: dialog.catalog[waveChoice.currentIndex] || ({points:[],color:dialog.accent,frequency:0})
                        Layout.fillWidth: true; Layout.preferredHeight: customStrength.visible ? 176 : 140
                        radius: 13; color: "#172134"; border.color: "#2a3850"
                        ColumnLayout {
                            anchors.fill: parent; anchors.margins: 12; spacing: 6
                            RowLayout { Layout.fillWidth: true; spacing: 10
                                Switch { checked: row.rule.enabled; onToggled: dialog.setRule(row.key, "enabled", checked) }
                                Label { text: row.modelData.cg ? (row.key === "defeat_scene_enter" ? "CG · 场景入场惩罚" : "CG · 互动循环") : (row.modelData.hp ? "HP · " : "动作 · ") + row.rule.label; font.bold: true; Layout.preferredWidth: 176 }
                                Choice {
                                    Layout.preferredWidth: 145; model: dialog.tiers; textRole: "name"; valueRole: "key"
                                    currentIndex: dialog.indexOf(dialog.tiers, row.strengthMode)
                                    onActivated: {
                                        row.strengthMode = currentValue
                                        if (currentValue === "custom") dialog.setRule(row.key,"custom_strength",Math.round(strengthSlider.value))
                                        else { dialog.setRule(row.key,"tier",currentValue); dialog.setRule(row.key,"custom_strength",null) }
                                    }
                                    id: strengthChoice
                                    objectName: row.key + "StrengthChoice"
                                }
                                Choice {
                                    id: waveChoice
                                    objectName: row.key + "WaveChoice"
                                    Layout.fillWidth: true; model: dialog.catalog; textRole: "name"; valueRole: "key"
                                    currentIndex: dialog.indexOf(dialog.catalog, row.rule.wave)
                                    onActivated: dialog.setRule(row.key,"wave",currentValue)
                                    delegate: ItemDelegate {
                                        id: waveOption
                                        required property int index
                                        width: waveChoice.width - 12; height: 52
                                        contentItem: RowLayout {
                                            Label { Layout.preferredWidth: 125; text: waveChoice.textAt(index); elide: Text.ElideRight; font.pixelSize: 11 }
                                            WavePlot { Layout.fillWidth: true; Layout.preferredHeight: 36; points: dialog.catalog[waveOption.index].points; stroke: dialog.catalog[waveOption.index].color }
                                        }
                                        background: Rectangle { radius: 8; color: highlighted ? "#29364e" : "#101725" }
                                    }
                                }
                            }
                            RowLayout {
                                id: customStrength
                                visible: row.strengthMode === "custom"
                                Layout.fillWidth: true
                                Label { text: "自定义强度"; color: "#8e9aaf"; Layout.preferredWidth: 95; font.pixelSize: 11 }
                                ValueSlider { id: strengthSlider; objectName: row.key + "CustomStrength"; Layout.fillWidth: true; from: 0; to: 100; stepSize: 1; value: row.customValue; onMoved: { row.customValue = Math.round(value); dialog.setRule(row.key,"custom_strength",row.customValue) } }
                                Label { text: Math.round(strengthSlider.value); color: dialog.accent; Layout.preferredWidth: 48 }
                            }
                            RowLayout { Layout.fillWidth: true; spacing: 14
                                Label { text: row.sustained ? "持续方式" : "持续时间"; color: "#8e9aaf"; Layout.preferredWidth: 70; font.pixelSize: 11 }
                                ValueSlider { id: durationSlider; objectName: row.key + "Duration"; visible: !row.sustained; Layout.fillWidth: true; from: 0.1; to: 3.0; stepSize: 0.1; value: row.durationValue; onMoved: { row.durationValue = Math.round(value*100)/100; dialog.setRule(row.key,"duration",row.durationValue) } }
                                Label { text: row.key === "defeat_interaction" ? "互动期间循环 · 返回剧情即解除" : row.sustained ? "持续至挣脱 · 不按秒计时" : durationSlider.value.toFixed(2) + " 秒"; color: dialog.accent; Layout.fillWidth: row.sustained; Layout.preferredWidth: row.sustained ? 220 : 68 }
                                Rectangle { Layout.preferredWidth: 200; Layout.preferredHeight: 44; radius: 8; color: "#0b1220"
                                    WavePlot { anchors.fill: parent; anchors.margins: 5; points: row.wave.points; stroke: row.wave.color }
                                }
                            }
                            Label { text: row.key === "defeat_scene_enter" ? "记录 HP 归零并确认进入匹配场景后，仅触发一次；与其他反馈取较强者，不叠加。" : row.key === "defeat_interaction" ? "各非关闭通道独立配置。只在已确认败北流程的互动段循环；剧情、退出、插件暂停或读数失效时停止循环。" : row.key === "player_down" ? "倒下诊断仅预览；真实大惩罚使用上方 CG 入场规则。" : row.sustained ? "受困期间保持所选强度与波形，不随进度衰减；挣脱、暂停或读取失效时停止。" : row.key === "capture_start" ? "捕获开始短事件；逃脱或捕获读取失效立即清除。" : "按所选档位或自定义数值触发，逐渐回落；碎甲升敏后仍受安全上限约束。"; color: row.modelData.cg || row.key === "player_down" ? "#f7c55b" : "#8e9aaf"; font.pixelSize: 9; Layout.fillWidth: true; wrapMode: Text.WordWrap }
                        }
                    }
                }
            }
        }
        Label { visible: dialog.errorText !== ""; text: dialog.errorText; color: "#ff5d7a" }
        RowLayout { Layout.fillWidth: true
            Label { Layout.fillWidth: true; text: "档位跟随个性化范围 · 当前硬上限 " + dialog.controller.hardCap + " · 保存后自动应用，保留手动暂停状态"; color: "#8e9aaf"; font.pixelSize: 10 }
            ActionButton { text: "保存 " + dialog.channel + " 通道策略"; implicitWidth: 190; onClicked: dialog.save() }
        }
    }
}
