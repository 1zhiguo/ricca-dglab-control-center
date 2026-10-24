pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Controls.Basic as Basic
import QtQuick.Dialogs
import QtQuick.Layouts
import QtQuick.Window
import QtQuick.Effects

ApplicationWindow {
    id: root
    width: 1360
    height: 860
    minimumWidth: 1120
    minimumHeight: 720
    visible: true
    property bool showOnboardingOnStart: false
    onShowOnboardingOnStartChanged: if (showOnboardingOnStart) Qt.callLater(function() { onboarding.openGuide() })
    title: "Ricca × DG-LAB Control Center"
    color: "#0f1711"

    // Forest-green and warm timber palette. Legacy accent property names are
    // retained for existing component bindings; red remains a danger signal.
    readonly property color bg: "#111a14"
    readonly property color panel: "#25251c"
    readonly property color panel2: "#353025"
    readonly property color border: "#574a36"
    readonly property color ink: "#f3ecd9"
    readonly property color muted: "#aaa68d"
    readonly property color cyan: "#8fbd83"
    readonly property color violet: "#ccab77"
    readonly property color red: "#ff5d7a"
    readonly property color yellow: "#e6be73"
    readonly property color pink: "#d59a78"
    readonly property color green: "#88c898"
    palette {
        window: root.bg
        windowText: root.ink
        base: root.panel
        alternateBase: root.panel2
        button: root.panel2
        buttonText: root.ink
        text: root.ink
        placeholderText: root.muted
        highlight: root.cyan
        highlightedText: root.bg
        accent: root.cyan
        mid: root.border
        light: "#75674d"
        dark: root.bg
    }
    property int pageIndex: 0
    readonly property bool sharedOutputPaused: backend.outputPaused && (!backend.ovcPlan.allowed || backend.ovcPlan.paused)
    readonly property string outputStateLabel: {
        if (backend.emergencyStopped) return "紧急停止"
        if (backend.priorityOutputStatus !== "") return backend.priorityOutputStatus + " · 输出中"
        if (backend.userOutputPaused) return "手动暂停"
        if (backend.manualOutputs.coyote.running || backend.manualOutputs.ovc.running) return "手动播放中"
        if ((backend.manualOutputs.coyote.enabled || backend.manualOutputs.ovc.enabled) && !backend.anyOutputArmed) return "手动模式待机"
        if (!backend.anyDeviceConnected) return "等待设备连接"
        if (!backend.telemetryReady) return "等待游戏就绪"
        if (root.sharedOutputPaused) return "输出待机"
        return "正在同步"
    }
    function openDeviceWorkbench(device, section) {
        if(section === "manual") { root.pageIndex=9;return }
        if (device === "ovc") { root.pageIndex=8; ovcWorkbench.showSection(section || "strength") }
        else { root.pageIndex=3; pulseWorkbench.showSection(section || "strength") }
    }
    property bool editorOnStart: false
    property string strategyOnStart: ""
    onStrategyOnStartChanged: {
        if (strategyOnStart !== "") channelStrategy.openChannel(strategyOnStart)
    }
    onEditorOnStartChanged: {
        if (editorOnStart)
            waveformEditor.openFrom("冲击", backend.waveformPoints("impact"), 24)
    }
    readonly property var tierOptions: [
        { "key": "low", "name": "低" },
        { "key": "medium", "name": "中" },
        { "key": "high", "name": "高" },
        { "key": "death", "name": "死亡" }
    ]

    function compact(value) {
        if (value === undefined || value === null || isNaN(value)) return "—"
        return Math.abs(value) >= 100 ? Math.round(value).toString() : Number(value).toFixed(1)
    }
    function stateColor() {
        if (backend.safetyMode === "gameplay-ready") return cyan
        if (backend.safetyMode === "story") return violet
        if (backend.safetyMode === "paused" || backend.safetyMode === "rebinding") return yellow
        return red
    }
    function severityColor(value) {
        if (value === "danger") return red
        if (value === "warning") return yellow
        if (value === "success") return cyan
        if (value === "story") return violet
        return "#938669"
    }
    function waveIndex(key) {
        var catalog = backend.waveformCatalog
        for (var i = 0; i < catalog.length; ++i)
            if (catalog[i].key === key) return i
        return 0
    }
    function waveItem(key) {
        if (key === "audio-reactive")
            return ({ "key": key, "name": "音频实时包络", "points": backend.audioPulsePoints, "frequency": 0, "color": cyan })
        var catalog = backend.waveformCatalog
        for (var i = 0; i < catalog.length; ++i)
            if (catalog[i].key === key) return catalog[i]
        return ({ "key": "idle", "name": "待机", "points": [0,0,0,0], "frequency": 0, "color": muted })
    }
    function waveName(key) { return waveItem(key).name }
    function tierIndex(key) {
        for (var i = 0; i < tierOptions.length; ++i)
            if (tierOptions[i].key === key) return i
        return 0
    }
    function audioDeviceIndex(key) {
        var devices = backend.audioDevices
        for (var i = 0; i < devices.length; ++i)
            if (devices[i].id === key) return i
        return devices.length ? 0 : -1
    }

    component AppText: LocalizedText {
        color: root.ink
        font.family: backend.uiFontFamily
        renderType: Text.NativeRendering
    }
    component AppSwitch: Basic.Switch {
        id: control
        implicitWidth:48; implicitHeight:28
        indicator:Rectangle { implicitWidth:44; implicitHeight:24; y:(control.height-height)/2; radius:12; color:control.checked ? root.green : root.border; opacity:control.enabled ? 1 : .65
            Rectangle { width:18; height:18; radius:9; anchors.verticalCenter:parent.verticalCenter; x:control.checked ? parent.width-width-3 : 3; color:root.ink; Behavior on x { NumberAnimation { duration:120 } } }
        }
    }

    component Card: Rectangle {
        color: root.panel
        radius: 20
        border.color: root.border
        border.width: 1
        clip: true
        Rectangle { anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top; anchors.leftMargin: 24; anchors.rightMargin: 24; height: 1; color: "#75674d"; opacity: .65 }
    }

    component ConnectionCard: Card {
        id: connectionCard
        property int readiness: 0
        property bool fault: false
        property color accent: root.green
        readonly property bool connectionReady: readiness === 2 && !fault
        readonly property bool glowActive: connectionReady
        readonly property color glowColor: fault ? root.red : connectionReady ? accent : readiness === 1 ? root.yellow : root.border
        clip: false
        border.width: connectionReady || fault ? 2 : 1
        border.color: glowColor
        color: connectionReady ? Qt.tint(root.panel, Qt.rgba(accent.r, accent.g, accent.b, .065)) : root.panel
        Behavior on border.color { ColorAnimation { duration: 180 } }
        Repeater {
            // Layered outlines give a static glow without blur textures,
            // continuous animation or work on the detection/output threads.
            model: [{spread:7,alpha:.055},{spread:4,alpha:.10},{spread:2,alpha:.18}]
            delegate: Rectangle {
                required property var modelData
                anchors.fill: parent
                anchors.margins: -modelData.spread
                radius: connectionCard.radius + modelData.spread
                color: "transparent"
                border.width: 2
                border.color: connectionCard.glowColor
                opacity: connectionCard.glowActive ? modelData.alpha : 0
                z: -1
                Behavior on opacity { NumberAnimation { duration: 180 } }
            }
        }
    }

    component AppButton: Rectangle {
        id: appButton
        property string label: "按钮"
        property color fillColor: root.panel2
        property color labelColor: root.ink
        property bool enabled: true
        signal clicked()
        implicitWidth: 118; implicitHeight: 42; radius: 13
        opacity: enabled ? 1 : .45
        color: buttonHit.pressed ? Qt.darker(fillColor, 1.1) : buttonHit.containsMouse ? Qt.lighter(fillColor, 1.06) : fillColor
        border.color: Qt.rgba(labelColor.r, labelColor.g, labelColor.b, .18)
        AppText { anchors.centerIn: parent; sourceText: appButton.label; color: appButton.labelColor; font.pixelSize: 13; font.weight: Font.DemiBold }
        MouseArea { id: buttonHit; anchors.fill: parent; enabled: appButton.enabled; hoverEnabled: true; cursorShape: enabled ? Qt.PointingHandCursor : Qt.ArrowCursor; onClicked: appButton.clicked() }
    }

    component AppComboBox: ComboBox {
        id: appCombo
        implicitHeight: 40; leftPadding: 14; rightPadding: 36
        font.family: backend.uiFontFamily; font.pixelSize: 11
        background: Rectangle { radius: 11; color: root.panel2; border.color: appCombo.activeFocus ? root.pink : root.border }
        contentItem: AppText { leftPadding: 2; sourceText: appCombo.displayText; verticalAlignment: Text.AlignVCenter; elide: Text.ElideRight }
        indicator: AppText { x: appCombo.width - width - 14; anchors.verticalCenter: parent.verticalCenter; sourceText: appCombo.popup.visible ? "⌃" : "⌄"; color: appCombo.popup.visible ? root.pink : root.muted; font.pixelSize: 16 }
        delegate: ItemDelegate {
            required property int index
            width: appCombo.width - 12; height: 38; leftPadding: 12
            contentItem: AppText { sourceText: appCombo.textAt(index); verticalAlignment: Text.AlignVCenter; elide: Text.ElideRight }
            background: Rectangle { radius: 9; color: highlighted ? Qt.rgba(root.pink.r, root.pink.g, root.pink.b, .18) : "transparent" }
        }
        popup: Popup {
            y: appCombo.height + 5; width: appCombo.width; implicitHeight: Math.min(contentItem.implicitHeight + 12, 292); padding: 6
            background: Rectangle { radius: 13; color: root.panel; border.color: root.border }
            contentItem: ListView { clip: true; implicitHeight: contentHeight; model: appCombo.popup.visible ? appCombo.delegateModel : null; currentIndex: appCombo.highlightedIndex; ScrollIndicator.vertical: ScrollIndicator {} }
        }
    }

    component StatusDot: Rectangle {
        property bool active: false
        width: 8; height: 8; radius: 4
        color: active ? root.cyan : "#66634e"
    }

    component NavButton: Button {
        property string glyph: "•"
        property bool selected: false
        flat: true
        implicitHeight: root.height < 800 ? 40 : 48
        background: Rectangle {
            radius: 14
            color: parent.selected ? Qt.rgba(root.pink.r, root.pink.g, root.pink.b, .14) : (parent.hovered ? root.panel2 : "transparent")
            border.color: parent.selected ? Qt.rgba(root.pink.r, root.pink.g, root.pink.b, .30) : "transparent"
        }
        contentItem: RowLayout {
            spacing: 12
            AppText { sourceText: parent.parent.glyph; font.pixelSize: 18; color: parent.parent.selected ? root.pink : root.muted; Layout.preferredWidth: 22; horizontalAlignment: Text.AlignHCenter }
            AppText { sourceText: parent.parent.text; font.pixelSize: 14; font.weight: parent.parent.selected ? Font.DemiBold : Font.Normal; color: parent.parent.selected ? root.ink : root.muted; Layout.fillWidth: true }
        }
    }

    component MetricBar: ColumnLayout {
        property string label: ""
        property real value: 0
        property real maximum: 1
        property color accent: root.cyan
        property string suffix: ""
        spacing: 7
        RowLayout {
            Layout.fillWidth: true
            AppText { sourceText: parent.parent.label; color: root.muted; font.pixelSize: 12; Layout.fillWidth: true }
            AppText { sourceText: root.compact(parent.parent.value) + " / " + root.compact(parent.parent.maximum) + parent.parent.suffix; font.pixelSize: 12; font.weight: Font.DemiBold }
        }
        Rectangle {
            Layout.fillWidth: true; Layout.preferredHeight: 8; radius: 4; color: "#34372a"; clip: true
            Rectangle { width: parent.width * Math.max(0, Math.min(1, maximum > 0 ? value / maximum : 0)); height: parent.height; radius: parent.radius; color: accent; Behavior on width { NumberAnimation { duration: 140 } } }
        }
    }

    component WaveCanvas: Canvas {
        property var points: []
        property color accent: root.cyan
        property bool tiled: false
        property bool animated: false
        property bool showPoints: false
        property bool showVerticalGrid: false
        onPointsChanged: requestPaint()
        onAccentChanged: requestPaint()
        onWidthChanged: requestPaint()
        onHeightChanged: requestPaint()
        onPaint: {
            var ctx = getContext("2d")
            ctx.reset()
            ctx.strokeStyle = "#45402e"
            ctx.lineWidth = 1
            for (var row = 1; row < 4; ++row) {
                var gy = height * row / 4
                ctx.beginPath(); ctx.moveTo(0, gy); ctx.lineTo(width, gy); ctx.stroke()
            }
            if (showVerticalGrid && points && points.length > 1) {
                for (var column = 0; column < points.length; ++column) {
                    var gx = 6 + column * Math.max(0, width - 12) / (points.length - 1)
                    ctx.beginPath(); ctx.moveTo(gx, 0); ctx.lineTo(gx, height); ctx.stroke()
                }
            }
            if (!points || points.length < 2) return
            ctx.strokeStyle = accent
            ctx.lineWidth = showPoints ? 4 : 3
            ctx.lineCap = "round"; ctx.lineJoin = "round"
            ctx.beginPath()
            var cycles = tiled ? Math.max(2, Math.ceil(48 / points.length)) : 1
            var total = points.length * cycles
            var horizontalInset = showPoints ? 6 : 0
            var verticalInset = showPoints ? 6 : height * .18
            for (var i = 0; i < total; ++i) {
                var x = horizontalInset + i * Math.max(0, width - horizontalInset * 2) / Math.max(1, total - 1)
                var y = height - verticalInset - Math.max(0, Math.min(100, Number(points[i % points.length]))) * Math.max(0, height - verticalInset * 2) / 100
                if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y)
            }
            ctx.stroke()
            if (showPoints && !tiled) {
                ctx.fillStyle = "#f3ecd9"
                for (i = 0; i < points.length; ++i) {
                    x = horizontalInset + i * Math.max(0, width - horizontalInset * 2) / Math.max(1, points.length - 1)
                    y = height - verticalInset - Math.max(0, Math.min(100, Number(points[i]))) * Math.max(0, height - verticalInset * 2) / 100
                    ctx.beginPath(); ctx.arc(x, y, 5, 0, Math.PI * 2); ctx.fill()
                }
            }
        }
        Rectangle {
            id: wavePlayhead
            property real phase: 0
            visible: parent.animated && parent.visible && parent.points && parent.points.length > 1
            width: 2; height: parent.height; color: Qt.rgba(parent.accent.r, parent.accent.g, parent.accent.b, .55)
            x: phase * Math.max(0, parent.width - width)
            Timer { interval: 33; repeat: true; running: wavePlayhead.visible; onTriggered: wavePlayhead.phase = (wavePlayhead.phase + .006) % 1 }
        }
    }

    component IntensitySetting: ColumnLayout {
        id: intensitySetting
        property string title: "低强度"
        property string detail: ""
        property int value: 0
        property int minimum: 0
        property color accent: root.cyan
        signal edited(int newValue)
        spacing: 5
        implicitHeight: 62
        RowLayout {
            Layout.fillWidth: true
            AppText { sourceText: intensitySetting.title; font.pixelSize: 14; font.weight: Font.DemiBold }
            AppText { sourceText: intensitySetting.detail; color: root.muted; font.pixelSize: 10; Layout.fillWidth: true }
            Rectangle {
                width: 58; height: 28; radius: 9; color: Qt.rgba(intensitySetting.accent.r,intensitySetting.accent.g,intensitySetting.accent.b,.13); border.color: Qt.rgba(intensitySetting.accent.r,intensitySetting.accent.g,intensitySetting.accent.b,.28)
                AppText { anchors.centerIn: parent; sourceText: intensitySetting.value; color: intensitySetting.accent; font.pixelSize: 12; font.weight: Font.Bold }
            }
        }
        AppSlider {
            Layout.fillWidth: true; from: intensitySetting.minimum; to: 100; stepSize: 1; value: intensitySetting.value
            onMoved: intensitySetting.edited(Math.round(value))
        }
    }

    component AppSlider: Basic.Slider {
        id: themedSlider
        implicitHeight: 28
        padding: 0
        opacity: enabled ? 1 : 0.45
        background: Rectangle {
            x: themedSlider.leftPadding
            y: themedSlider.topPadding + (themedSlider.availableHeight - height) / 2
            width: themedSlider.availableWidth
            height: 6
            radius: 3
            color: root.border
            Rectangle { width: themedSlider.visualPosition * parent.width; height: parent.height; radius: parent.radius; color: root.cyan }
        }
        handle: Rectangle {
            x: themedSlider.leftPadding + themedSlider.visualPosition * (themedSlider.availableWidth - width)
            y: themedSlider.topPadding + (themedSlider.availableHeight - height) / 2
            width: 14
            height: 22
            radius: 5
            color: themedSlider.pressed ? Qt.lighter(root.cyan, 1.15) : root.cyan
            border.color: themedSlider.activeFocus ? root.ink : root.border
        }
    }

    component WaveEditorDialog: Dialog {
        id: editor
        parent: Overlay.overlay
        anchors.centerIn: parent
        width: Math.min(1220, parent.width - 48)
        height: Math.min(820, parent.height - 36)
        modal: true
        padding: 0
        property var draftPoints: [0, 12, 24, 40, 58, 78, 100, 72, 44, 22, 8, 0, 0, 0, 0, 0]
        property var undoStack: []
        property var redoStack: []
        property string seedName: "Ricca 自定义"
        property int seedFrequency: 80
        property int activeIndex: -1

        function clean(values) {
            var out = []
            for (var i = 0; i < 16; ++i)
                out.push(Math.max(0, Math.min(100, Math.round(Number(values[i] || 0)))))
            return out
        }
        function replace(values, remember) {
            if (remember) {
                var past = undoStack.slice(); past.push(draftPoints.slice())
                if (past.length > 30) past.shift()
                undoStack = past; redoStack = []
            }
            draftPoints = clean(values)
        }
        function setPointAt(x, y, remember) {
            var index = Math.max(0, Math.min(15, Math.round((x - 6) / Math.max(1, drawMouse.width - 12) * 15)))
            var value = Math.max(0, Math.min(100, Math.round((drawMouse.height - 6 - y) / Math.max(1, drawMouse.height - 12) * 100)))
            activeIndex = index
            var next = draftPoints.slice(); next[index] = value; replace(next, remember)
        }
        function undo() {
            if (!undoStack.length) return
            var future = redoStack.slice(); future.push(draftPoints.slice()); redoStack = future
            var past = undoStack.slice(); draftPoints = past.pop(); undoStack = past
        }
        function redo() {
            if (!redoStack.length) return
            var past = undoStack.slice(); past.push(draftPoints.slice()); undoStack = past
            var future = redoStack.slice(); draftPoints = future.pop(); redoStack = future
        }
        function smooth() {
            var next = draftPoints.slice()
            for (var i = 1; i < 15; ++i)
                next[i] = Math.round((draftPoints[i - 1] + draftPoints[i] * 2 + draftPoints[i + 1]) / 4)
            replace(next, true)
        }
        function normalize() {
            var maximum = 0
            for (var i = 0; i < 16; ++i) maximum = Math.max(maximum, draftPoints[i])
            if (maximum <= 0) return
            var next = []; for (i = 0; i < 16; ++i) next.push(Math.round(draftPoints[i] * 100 / maximum))
            replace(next, true)
        }
        function mirror() { replace(draftPoints.slice().reverse(), true) }
        function clearPoints() { replace([0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0], true) }
        function openFrom(name, points, frequency) {
            seedName = name + "·自定义"
            seedFrequency = frequency
            draftPoints = clean(points); undoStack = []; redoStack = []; activeIndex = -1
            waveName.text = seedName
            waveFrequency.value = seedFrequency
            open()
        }

        background: Rectangle { color: root.panel; radius: 16; border.color: root.border }
        contentItem: ColumnLayout {
            anchors.fill: parent; anchors.margins: 26; spacing: 14
            Item { Layout.fillWidth: true; Layout.preferredHeight: 56
                ColumnLayout { anchors.left: parent.left; anchors.right: closeWaveEditor.left; anchors.rightMargin: 16; anchors.verticalCenter: parent.verticalCenter; spacing: 2
                    AppText { sourceText: "自定义波形编辑器"; font.pixelSize: 22; font.weight: Font.Bold }
                    AppText { sourceText: "从模板开始，或直接在大画布上绘制 16 点包络"; color: root.muted; font.pixelSize: 11 }
                }
                AppButton { id: closeWaveEditor; anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter; width: 96; label: "关闭"; onClicked: editor.close() }
            }
            RowLayout { Layout.fillWidth: true; spacing: 10
                TextField {
                    id: waveName; text: editor.seedName; placeholderText: backend.localize("波形名称", backend.language); Layout.fillWidth: true; Layout.preferredHeight: 46; leftPadding: 14
                    color: root.ink; font.family: backend.uiFontFamily; font.pixelSize: 12
                    background: Rectangle { color: root.panel2; radius: 11; border.color: waveName.activeFocus ? root.cyan : root.border }
                }
                AppButton { Layout.preferredWidth: 110; label: "呼吸"; onClicked: editor.replace([0,8,18,32,50,70,88,100,88,70,50,32,18,8,0,0], true) }
                AppButton { Layout.preferredWidth: 110; label: "心跳"; onClicked: editor.replace([0,25,100,30,0,0,0,65,15,0,0,0,25,100,25,0], true) }
                AppButton { Layout.preferredWidth: 110; label: "渐强"; onClicked: editor.replace([0,8,14,22,30,40,52,65,78,90,100,90,78,60,38,0], true) }
                AppButton { Layout.preferredWidth: 110; label: "阶梯"; onClicked: editor.replace([0,20,20,40,40,60,60,80,80,100,100,75,75,40,40,0], true) }
            }
            Rectangle {
                id: drawArea
                Layout.fillWidth: true; Layout.fillHeight: true; radius: 16; color: "#101b13"; border.color: root.cyan; clip: true
                WaveCanvas { anchors.fill: parent; anchors.margins: 20; points: editor.draftPoints; accent: root.cyan; showPoints: true; showVerticalGrid: true }
                MouseArea {
                    id: drawMouse
                    anchors.fill: parent; anchors.margins: 20
                    cursorShape: Qt.CrossCursor
                    onPressed: function(mouse) { editor.setPointAt(mouse.x, mouse.y, true) }
                    onPositionChanged: function(mouse) { if (pressed) editor.setPointAt(mouse.x, mouse.y, false) }
                }
                Rectangle {
                    visible: editor.activeIndex >= 0
                    anchors.left: parent.left; anchors.top: parent.top; anchors.margins: 12
                    width: 116; height: 30; radius: 9; color: "#373e28"; border.color: root.cyan
                    AppText { anchors.centerIn: parent; sourceText: "节点 " + (editor.activeIndex + 1) + " · " + editor.draftPoints[editor.activeIndex] + "%"; color: root.cyan; font.pixelSize: 10; font.weight: Font.DemiBold }
                }
            }
            RowLayout { Layout.fillWidth: true; spacing: 10
                AppButton { Layout.preferredWidth: 96; label: "撤销"; enabled: editor.undoStack.length > 0; onClicked: editor.undo() }
                AppButton { Layout.preferredWidth: 96; label: "重做"; enabled: editor.redoStack.length > 0; onClicked: editor.redo() }
                AppButton { Layout.preferredWidth: 96; label: "平滑"; onClicked: editor.smooth() }
                AppButton { Layout.preferredWidth: 96; label: "镜像"; onClicked: editor.mirror() }
                AppButton { Layout.preferredWidth: 96; label: "归一化"; onClicked: editor.normalize() }
                AppButton { Layout.preferredWidth: 96; label: "清空"; onClicked: editor.clearPoints() }
                Item { Layout.fillWidth: true }
                AppText { sourceText: editor.draftPoints.join(" · "); color: root.muted; font.family: "Consolas"; font.pixelSize: 8; Layout.preferredWidth: 390; elide: Text.ElideRight; horizontalAlignment: Text.AlignRight }
            }
            RowLayout { Layout.fillWidth: true; spacing: 10
                AppText { sourceText: "频率"; color: root.muted; font.pixelSize: 11 }
                AppSlider { id: waveFrequency; Layout.fillWidth: true; from: 10; to: 240; stepSize: 1; value: editor.seedFrequency }
                AppText { sourceText: Math.round(waveFrequency.value) + " Hz"; color: root.cyan; font.pixelSize: 12; font.weight: Font.DemiBold; Layout.preferredWidth: 58 }
                AppText { sourceText: "输出仍受事件档位与硬上限限制"; color: root.yellow; font.pixelSize: 9; Layout.preferredWidth: 190; horizontalAlignment: Text.AlignRight }
                AppButton { Layout.preferredWidth: 210; fillColor: root.cyan; labelColor: "#18251c"; label: "保存到我的波形库"; onClicked: { if (backend.saveCustomWaveform(waveName.text, editor.draftPoints, Math.round(waveFrequency.value))) editor.close() } }
            }
        }
    }

    component GuidePreviewDialog: Dialog {
        id: guideDialog
        parent: Overlay.overlay
        anchors.centerIn: parent
        width: Math.min(500, parent.width - 64)
        height: Math.min(790, parent.height - 48)
        modal: true
        padding: 0
        property url imageSource: ""
        property string stepTitle: "DG-LAB 连接步骤"

        function openSource(source, title) {
            imageSource = source
            stepTitle = title
            open()
        }

        background: Rectangle { color: root.panel; radius: 18; border.color: root.border }
        contentItem: ColumnLayout {
            anchors.fill: parent; anchors.margins: 18; spacing: 12
            RowLayout {
                Layout.fillWidth: true
                AppText { sourceText: guideDialog.stepTitle; font.pixelSize: 17; font.weight: Font.DemiBold; Layout.fillWidth: true }
                AppButton { Layout.preferredWidth: 72; Layout.preferredHeight: 36; label: "关闭"; onClicked: guideDialog.close() }
            }
            Rectangle {
                Layout.fillWidth: true; Layout.fillHeight: true; radius: 14; color: "#0e1710"; border.color: root.border; clip: true
                Image { anchors.fill: parent; anchors.margins: 10; source: guideDialog.imageSource; sourceSize: Qt.size(720, 1600); fillMode: Image.PreserveAspectFit; asynchronous: true }
            }
        }
    }


    component ChannelCard: Card {
        id: channelCard
        property string channel: "A"
        property real strength: 0
        property string wave: "idle"
        property color accent: root.cyan
        property var points: []
        implicitHeight: 128
        ColumnLayout {
            anchors.fill: parent; anchors.margins: 16; spacing: 9
            RowLayout {
                Layout.fillWidth: true
                Rectangle { width: 30; height: 30; radius: 8; color: Qt.rgba(accent.r, accent.g, accent.b, .14); AppText { anchors.centerIn: parent; sourceText: channel; color: accent; font.bold: true } }
                AppText { sourceText: backend.channelPolicies ? backend.channelModeName(channelCard.channel) : "通道策略"; font.pixelSize: 14; font.weight: Font.DemiBold; Layout.fillWidth: true }
                AppText { sourceText: Math.round(strength).toString(); color: accent; font.pixelSize: 25; font.weight: Font.Bold }
            }
            Rectangle { Layout.fillWidth: true; height: 7; radius: 4; color: "#34372a"; Rectangle { height: parent.height; width: parent.width * Math.min(1, strength / Math.max(1, backend.hardCap)); radius: parent.radius; color: accent } }
            RowLayout { Layout.fillWidth: true
                AppText { sourceText: "预览波形  " + wave; color: root.muted; font.pixelSize: 12; Layout.fillWidth: true }
                WaveCanvas { Layout.preferredWidth: 108; Layout.preferredHeight: 24; points: channelCard.points; accent: channelCard.accent }
            }
        }
    }

    RowLayout {
        anchors.fill: parent
        spacing: 0

        Rectangle {
            Layout.preferredWidth: 224
            Layout.fillHeight: true
            color: "#121b13"
            border.color: "#393629"
            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 18
                spacing: root.height < 800 ? 6 : 8
                RowLayout {
                    Layout.fillWidth: true; Layout.bottomMargin: root.height < 800 ? 12 : 24
                    Rectangle {
                        objectName: "riccaBrandAvatar"
                        width: 44; height: 44; radius: 10; color: "transparent"
                        border.width: 0; clip: false
                        Image {
                            id: avatarImage
                            anchors.fill: parent
                            source: "../assets/branding/ricca-app-icon.png"
                            sourceSize: Qt.size(128, 128)
                            fillMode: Image.PreserveAspectFit; smooth: true; mipmap: true
                            visible: false
                        }
                        Rectangle {
                            id: avatarMask
                            anchors.fill: parent; radius: 10; color: "white"
                            visible: false
                            layer.enabled: true
                        }
                        MultiEffect {
                            anchors.fill: parent; source: avatarImage
                            maskEnabled: true; maskSource: avatarMask
                        }
                    }
                    ColumnLayout { spacing: 1; AppText { sourceText: "RICCA × DG-LAB"; font.pixelSize: 14; font.weight: Font.Bold } AppText { sourceText: "CONTROL CENTER"; color: root.muted; font.pixelSize: 9; font.letterSpacing: 1.5 } }
                }
                NavButton { Layout.fillWidth: true; text: "实时总览"; glyph: "◈"; selected: root.pageIndex === 0; onClicked: root.pageIndex = 0 }
                NavButton { Layout.fillWidth: true; text: "设备与游戏"; glyph: "⌁"; selected: root.pageIndex === 1; onClicked: root.pageIndex = 1 }
                NavButton { Layout.fillWidth: true; text: "郊狼工作台"; glyph: "〰"; selected: root.pageIndex === 3 || root.pageIndex === 2; onClicked: root.pageIndex = 3 }
                NavButton { objectName: "ovcWorkbenchNavButton"; Layout.fillWidth: true; text: "负鼠工作台"; glyph: "≋"; selected: root.pageIndex === 8; onClicked: root.pageIndex = 8 }
                NavButton {objectName:"manualControlNavButton";Layout.fillWidth:true;text:"手动控制";glyph:"▷";selected:root.pageIndex===9;onClicked:root.pageIndex=9}
                NavButton { Layout.fillWidth: true; text: "A/B 波形监视"; glyph: "◉"; selected: root.pageIndex === 4; onClicked: root.pageIndex = 4 }
                Rectangle { Layout.fillWidth: true; Layout.preferredHeight: 1; Layout.topMargin: 8; Layout.bottomMargin: 8; color: root.border }
                NavButton { Layout.fillWidth: true; text: "场景与字幕"; glyph: "◇"; selected: root.pageIndex === 5; onClicked: root.pageIndex = 5 }
                NavButton { Layout.fillWidth: true; text: "音频共感"; glyph: "◌"; selected: root.pageIndex === 6; onClicked: root.pageIndex = 6 }
                NavButton { Layout.fillWidth: true; text: "诊断与事件"; glyph: "≡"; selected: root.pageIndex === 7; onClicked: root.pageIndex = 7 }
                AppButton { objectName:"onboardingHelpButton"; Layout.fillWidth:true; Layout.preferredHeight:32; label:"新手教程"; labelColor:root.cyan; onClicked:onboarding.openGuide() }
                Item { Layout.fillHeight: true }
                Card {
                    objectName: "sidebarStatusCard"
                    Layout.preferredWidth: 196; Layout.minimumWidth: 196; Layout.maximumWidth: 196
                    Layout.preferredHeight: 112
                    color: "#24291d"
                    ColumnLayout { anchors.fill: parent; anchors.margins: 13; spacing: 7
                        RowLayout { StatusDot { active: backend.telemetryOnline } AppText { sourceText: backend.telemetryStatus; font.pixelSize: 11; Layout.fillWidth: true; Layout.minimumWidth: 0; elide: Text.ElideRight } }
                        RowLayout { StatusDot { active: backend.anyDeviceConnected } AppText { sourceText: backend.anyDeviceConnected ? "DG-LAB 已连接" : "等待手机连接"; font.pixelSize: 11; Layout.fillWidth: true; Layout.minimumWidth: 0; elide: Text.ElideRight } }
                        Rectangle { Layout.fillWidth: true; height: 1; color: root.border }
                        AppText { sourceText: "v" + backend.version + "  ·  " + (backend.anyOutputArmed ? root.sharedOutputPaused ? "PAUSED" : "LIVE" : "SAFE"); color: backend.anyOutputArmed && !root.sharedOutputPaused ? root.red : root.yellow; font.pixelSize: 10; font.letterSpacing: 1 }
                    }
                }
            }
        }

        ColumnLayout {
            Layout.fillWidth: true; Layout.fillHeight: true; spacing: 0
            Rectangle {
                Layout.fillWidth: true; Layout.preferredHeight: 74; color: root.bg; z: 20
                ColumnLayout {
                    anchors.left: parent.left; anchors.right: headerActions.left
                    anchors.leftMargin: 30; anchors.rightMargin: 24
                    anchors.verticalCenter: parent.verticalCenter; spacing: 2
                    AppText { Layout.fillWidth: true; Layout.minimumWidth: 0; sourceText: ["实时总览", "设备与游戏", "个性化范围", "郊狼工作台", "A/B 波形监视", "场景与字幕", "音频共感", "诊断与事件", "负鼠工作台", "手动控制"][root.pageIndex]; font.pixelSize: 22; font.weight: Font.Bold; elide: Text.ElideRight }
                    AppText { Layout.fillWidth: true; Layout.minimumWidth: 0; sourceText: ["游戏状态、角色与事件输出总览", "启动游戏、扫码连接、选择设备", "设置共感档位与安全硬上限", "强度、战斗与剧情，按需调整", "查看两个通道的当前波形和预览强度", "查看剧情文字与已登记场景", "共用音频来源；各设备映射在工作台调整", "逐项核对指针、动作与触发边沿", "强度、战斗与剧情，按需调整", "独立调节 A/B 强度与波形，不依赖游戏检测"][root.pageIndex]; color: root.muted; font.pixelSize: 11; elide: Text.ElideRight }
                }
                RowLayout {
                    id: headerActions
                    anchors.right: parent.right; anchors.rightMargin: 30
                    anchors.verticalCenter: parent.verticalCenter; spacing: 14
                    width: 590; height: 38
                    AppComboBox {
                        objectName: "uiLanguageChoice"
                        Layout.preferredWidth: 104; Layout.preferredHeight: 38
                        textRole: "name"; valueRole: "code"
                        model: [{code:"zh",name:"中文"},{code:"en",name:"English"},{code:"ja",name:"日本語"}]
                        currentIndex: backend.language === "en" ? 1 : backend.language === "ja" ? 2 : 0
                        onActivated: backend.setLanguage(currentValue)
                    }
                    Rectangle {
                        id: hudToggle
                        Layout.preferredWidth: 88; Layout.preferredHeight: 38; radius: 19
                        color: backend.gameHudEnabled ? Qt.rgba(root.cyan.r,root.cyan.g,root.cyan.b,.14) : root.panel2
                        border.color: backend.gameHudEnabled ? Qt.rgba(root.cyan.r,root.cyan.g,root.cyan.b,.5) : root.border
                        Row {
                            anchors.centerIn: parent; spacing: 7
                            AppText { sourceText: "HUD ⚙"; translateEnabled:false; color: backend.gameHudEnabled ? root.cyan : root.muted; font.pixelSize: 10; font.bold: true; anchors.verticalCenter: parent.verticalCenter }
                            Rectangle {
                                width: 30; height: 18; radius: 9; color: backend.gameHudEnabled ? root.cyan : "#514831"
                                Rectangle { width: 12; height: 12; radius: 6; y: 3; x: backend.gameHudEnabled ? 15 : 3; color: backend.gameHudEnabled ? "#213b29" : "#ded3b7"; Behavior on x { NumberAnimation { duration: 150 } } }
                                MouseArea {anchors.fill:parent;cursorShape:Qt.PointingHandCursor;onClicked:backend.setGameHudEnabled(!backend.gameHudEnabled)}
                            }
                        }
                        MouseArea { objectName:"openHudSettingsButton";anchors.left:parent.left;anchors.top:parent.top;anchors.bottom:parent.bottom;width:parent.width-36;cursorShape:Qt.PointingHandCursor;onClicked:hudSettings.openSettings() }
                        HoverHandler { id:hudHelpHover }
                        ToolTip.visible:hudHelpHover.hovered
                        ToolTip.text:backend.localize("HUD 支持窗口和无边框全屏；独占全屏可能遮挡桌面悬浮窗。HUD 隐藏不代表设备停止输出。",backend.language)
                    }
                    Rectangle {
                        Layout.preferredWidth:164; Layout.preferredHeight:38; radius:19
                        readonly property color statusAccent: backend.emergencyStopped || backend.priorityOutputStatus !== "" ? root.red : root.sharedOutputPaused || !backend.anyDeviceConnected ? root.yellow : root.green
                        color:Qt.rgba(statusAccent.r,statusAccent.g,statusAccent.b,.10)
                        border.color:Qt.rgba(statusAccent.r,statusAccent.g,statusAccent.b,.30)
                        Row { anchors.centerIn:parent; spacing:8
                            Rectangle { width:8; height:8; radius:4; color:parent.parent.statusAccent; anchors.verticalCenter:parent.verticalCenter }
                            AppText { objectName:"outputStateBadge"; sourceText:root.outputStateLabel; color:parent.parent.statusAccent; font.pixelSize:10; font.bold:true }
                        }
                        ToolTip.visible:statusHover.hovered
                        ToolTip.text:backend.localize(backend.outputStatus,backend.language)
                        HoverHandler { id:statusHover }
                    }
                    AppButton { objectName: "outputPauseButton"; Layout.preferredWidth: 92; Layout.preferredHeight: 38; label: backend.priorityOutputStatus === "死亡惩罚" ? (backend.userOutputPaused ? "恢复普通输出" : "暂停普通输出") : backend.userOutputPaused ? "恢复输出" : "暂停输出"; labelColor: backend.anyOutputArmed && !backend.userOutputPaused ? root.red : root.yellow; onClicked: backend.toggleOutputPause() }
                    AppButton { Layout.preferredWidth: 98; Layout.preferredHeight: 38; label: "紧急归零"; fillColor: Qt.rgba(root.red.r, root.red.g, root.red.b, .12); labelColor: root.red; onClicked: backend.emergencyStop() }
                }
            }

            RowLayout {
                Layout.fillWidth: true; Layout.preferredHeight: 30; Layout.leftMargin: 30; Layout.rightMargin: 30; spacing: 12
                AppText { objectName: "activeOutputProfile"; sourceText: "郊狼 Pulse＋负鼠振动，两台控制器可同时运行，强度与节奏独立保存"; color: root.cyan; font.pixelSize: 10; font.weight: Font.DemiBold; Layout.fillWidth: true; elide: Text.ElideRight }
                AppButton { label: "连接设置"; Layout.preferredHeight: 26; Layout.preferredWidth: 104; onClicked: root.pageIndex = 1 }
            }
            StackLayout {
                currentIndex: root.pageIndex
                Layout.fillWidth: true; Layout.fillHeight: true

                ScrollView {
                    id: overviewPage
                    clip: true
                    leftPadding: 24
                    rightPadding: 34
                    topPadding: 20
                    bottomPadding: 24
                    contentWidth: availableWidth
                    ColumnLayout {
                        width: overviewPage.availableWidth; spacing: 16
                        Rectangle {
                            Layout.fillWidth: true; Layout.preferredHeight: 48; radius: 10
                            color: "#30271b"; border.color: "#66502a"
                            RowLayout { anchors.fill: parent; anchors.margins: 13
                                AppText { sourceText: backend.outputArmed ? backend.outputPaused ? "输出暂停" : "实时输出" : "安全待机"; color: backend.outputArmed && !backend.outputPaused ? root.red : root.yellow; font.bold: true }
                                AppText { sourceText: backend.outputStatus; color: "#d4bf91"; Layout.fillWidth: true; font.pixelSize: 12 }
                                Button { text: "连接设置"; flat: true; onClicked: root.pageIndex = 1; contentItem: AppText { sourceText: parent.text; color: root.yellow; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter } }
                            }
                        }
                        GridLayout {
                            Layout.fillWidth: true; columns: 3; columnSpacing: 16; rowSpacing: 16
                            Card {
                                Layout.fillWidth: true; Layout.columnSpan: 2; Layout.preferredHeight: 220
                                ColumnLayout { anchors.fill: parent; anchors.margins: 19; spacing: 13
                                    RowLayout { Layout.fillWidth: true
                                        AppText { sourceText: "PLAYER"; color: root.muted; font.pixelSize: 10; font.letterSpacing: 1.4; Layout.fillWidth: true }
                                        AppText { objectName: "armorMultiplierStatus"; sourceText: (backend.sensitivityStage > 0 ? "已破甲" : "未破甲") + " · Pulse ×" + backend.sensitivityMultiplier.toFixed(1); color: root.yellow; font.pixelSize: 12; font.weight: Font.DemiBold }
                                        AppText { sourceText: backend.playerState; color: root.cyan; font.pixelSize: 12 }
                                    }
                                    MetricBar { Layout.fillWidth: true; label: "HP"; value: backend.currentHp; maximum: backend.maxHp; accent: root.red }
                                    MetricBar { Layout.fillWidth: true; label: "MP"; value: backend.currentMp; maximum: backend.maxMp; accent: root.violet }
                                    MetricBar { Layout.fillWidth: true; label: "ARMOR · LEVEL " + backend.armorLevel + " / " + Math.max(0, backend.armorLevelCount - 1); value: backend.armorHp; maximum: backend.armorMaxHp; accent: root.yellow }
                                    RowLayout { Layout.fillWidth: true
                                        ColumnLayout { Layout.fillWidth: true; spacing: 2; AppText { sourceText: "当前动作"; color: root.muted; font.pixelSize: 10 } AppText { translateEnabled: false; sourceText: backend.actionName; font.pixelSize: 16; font.weight: Font.DemiBold } }
                                        ColumnLayout { spacing: 2; AppText { sourceText: "ACTION HASH"; color: root.muted; font.pixelSize: 10 } AppText { sourceText: backend.actionHash; font.family: "Consolas"; font.pixelSize: 13 } }
                                    }
                                }
                            }
                            Card {
                                objectName: "overviewPauseCard"
                                Layout.fillWidth: true; Layout.preferredHeight: 220
                                ColumnLayout { anchors.fill: parent; anchors.margins: 18; spacing: 10
                                    Button {
                                        id: overviewPause
                                        objectName: "overviewPauseButton"
                                        Layout.fillWidth: true; Layout.fillHeight: true
                                        hoverEnabled: true
                                        onClicked: backend.toggleOutputPause()
                                        background: Rectangle {
                                            radius: 16
                                            color: backend.userOutputPaused ? "#314533" : "#483b28"
                                            border.color: overviewPause.hovered ? root.cyan : root.border
                                            border.width: overviewPause.hovered ? 2 : 1
                                            opacity: overviewPause.down ? 0.75 : 1
                                            Behavior on color { ColorAnimation { duration: 140 } }
                                        }
                                        contentItem: ColumnLayout {
                                            spacing: 7
                                            AppText { sourceText: backend.userOutputPaused ? "▶" : "Ⅱ"; color: backend.userOutputPaused ? root.green : root.yellow; font.pixelSize: 32; Layout.alignment: Qt.AlignHCenter }
                                            AppText { objectName: "overviewPauseLabel"; sourceText: backend.userOutputPaused ? "恢复输出" : "暂停输出"; font.pixelSize: 24; font.bold: true; Layout.alignment: Qt.AlignHCenter }
                                            AppText { sourceText: backend.userOutputPaused ? "场景循环已暂停" : backend.outputPaused ? "当前安全待机 · 可预先暂停" : "点击暂停场景及普通输出"; color: root.muted; font.pixelSize: 11; Layout.alignment: Qt.AlignHCenter }
                                        }
                                    }
                                    AppText { sourceText: "死亡惩罚仅由「紧急归零」停止"; color: root.yellow; font.pixelSize: 10; Layout.alignment: Qt.AlignHCenter }
                                    AppText { translateEnabled: false; sourceText: backend.stageName + " · " + backend.gameScene.toUpperCase() + " · " + backend.pollHz.toFixed(1) + " Hz"; color: root.muted; font.pixelSize: 10; Layout.fillWidth: true; elide: Text.ElideRight }
                                }
                            }
                            ChannelCard { Layout.fillWidth: true; channel: "A"; strength: backend.previewA; wave: backend.waveA; points: backend.waveAPoints; accent: root.red }
                            ChannelCard { Layout.fillWidth: true; channel: "B"; strength: backend.previewB; wave: backend.waveB; points: backend.waveBPoints; accent: root.violet }
                            Card {
                                Layout.fillWidth: true; Layout.preferredHeight: 128
                                ColumnLayout { anchors.fill: parent; anchors.margins: 16; spacing: 7
                                    RowLayout { Layout.fillWidth: true; AppText { sourceText: "BOSS"; color: root.muted; font.pixelSize: 10; font.letterSpacing: 1.4; Layout.fillWidth: true } AppText { sourceText: backend.bossActive ? "ENGAGED" : "IDLE"; color: backend.bossActive ? root.red : root.muted; font.pixelSize: 10; font.bold: true } }
                                    MetricBar { Layout.fillWidth: true; label: backend.bossState; value: backend.bossHp; maximum: backend.bossMaxHp; accent: root.red }
                                    AppText { sourceText: backend.bossAction; color: root.muted; font.pixelSize: 11 }
                                }
                            }
                        }
                        Card {
                            objectName: "captureOverviewCard"
                            Layout.fillWidth: true; Layout.preferredHeight: 124
                            ColumnLayout { anchors.fill: parent; anchors.margins: 18; spacing: 8
                                RowLayout { Layout.fillWidth: true
                                    AppText { sourceText: "捕获与挣扎"; font.pixelSize: 15; font.weight: Font.DemiBold; Layout.fillWidth: true }
                                    AppText { objectName: "captureStatusText"; sourceText: backend.captureStatus.label; color: backend.captureStatus.active ? root.yellow : root.muted; font.pixelSize: 13; font.bold: true }
                                }
                                MetricBar { Layout.fillWidth: true; label: "挣扎进度 · " + Math.round(backend.captureStatus.progress * 100) + "%"; value: backend.captureStatus.count; maximum: backend.captureStatus.maximum; accent: root.cyan }
                                AppText { Layout.fillWidth: true; sourceText: backend.captureStatus.active ? "挣扎反馈持续至挣脱，保持所选强度与波形；暂停或读取异常时停止。" : backend.captureStatus.known ? "当前未受困 · 逃脱后残留计数不计入进度。" : "等待可用的捕获遥测；读取异常不会触发捕获 Pulse。"; color: root.muted; font.pixelSize: 10; wrapMode: Text.WordWrap }
                            }
                        }
                        Card {
                            objectName: "defeatSceneOverview"
                            Layout.fillWidth: true; Layout.preferredHeight: backend.canConfirmCurrentDefeatScene ? 94 : 76
                            ColumnLayout { anchors.fill: parent; anchors.margins: 16; spacing: 5
                                RowLayout { Layout.fillWidth: true; spacing: 12
                                    AppText { objectName: "defeatSceneStatusLabel"; sourceText: backend.defeatSceneStatus; color: root.yellow; font.pixelSize: 13; Layout.fillWidth: true; elide: Text.ElideRight }
                                    AppButton { objectName: "confirmCurrentDefeatButton"; visible: backend.canConfirmCurrentDefeatScene; Layout.preferredWidth: 168; Layout.preferredHeight: 32; label: "接管当前败北互动"; labelColor: root.yellow; onClicked: resetConfirmation.ask("确认接管当前败北互动？", "请确认当前是败北后的互动，而不是回想。确认后将按通道设置开始循环 Pulse，不补发之前未记录的死亡惩罚。请先核对强度；紧急归零可停止全部输出。", function() { backend.confirmCurrentDefeatScene() }, "确认接管") }
                                }
                                AppText { sourceText: "已登记剧情 / 回想全程循环 · 大按钮暂停循环 · 死亡惩罚优先于普通暂停 · 紧急归零停止全部输出"; color: root.muted; font.pixelSize: 10; Layout.fillWidth: true; wrapMode: Text.WordWrap }
                            }
                        }
                        AppText { sourceText: "最近事件"; font.pixelSize: 15; font.weight: Font.DemiBold; Layout.topMargin: 4 }
                        Card {
                            Layout.fillWidth: true; Layout.preferredHeight: 230
                            ListView {
                                anchors.fill: parent; anchors.margins: 8; clip: true; spacing: 2
                                model: backend.events
                                delegate: Rectangle {
                                    required property var modelData
                                    width: ListView.view.width; height: 48; radius: 8; color: hover.hovered ? "#313324" : "transparent"
                                    HoverHandler { id: hover }
                                    RowLayout { anchors.fill: parent; anchors.leftMargin: 10; anchors.rightMargin: 10; spacing: 10
                                        Rectangle { width: 4; height: 25; radius: 2; color: root.severityColor(modelData.severity) }
                                        AppText { sourceText: String(modelData.time).slice(11, 23); color: root.muted; font.family: "Consolas"; font.pixelSize: 10; Layout.preferredWidth: 76 }
                                        AppText { sourceText: modelData.title; font.pixelSize: 12; font.weight: Font.DemiBold; Layout.preferredWidth: 205; elide: Text.ElideRight }
                                        AppText { sourceText: modelData.detail; color: root.muted; font.pixelSize: 11; Layout.fillWidth: true; elide: Text.ElideRight }
                                    }
                                }
                                AppText { anchors.centerIn: parent; sourceText: "等待游戏事件…"; color: root.muted; visible: parent.count === 0 }
                            }
                        }
                        Item { Layout.preferredHeight: 12 }
                    }
                }

                ScrollView {
                    id: connectionPage
                    property bool detailsExpanded: false
                    property bool qrExpanded: false
                    readonly property bool appConnected: backend.socketProtocol === "v4" ? backend.v4AppConnected : backend.deviceConnected
                    readonly property bool showQr: !appConnected || qrExpanded
                    readonly property int setupCardHeight: (showQr ? 292 : 260) + (backend.socketProtocol === "v3" ? 34 : 0)
                    clip: true; leftPadding: 24; rightPadding: 24; topPadding: 18; bottomPadding: 24
                    contentWidth: availableWidth
                    ColumnLayout { objectName: "deviceSetupRows"; width: connectionPage.availableWidth; spacing: 16
                        RowLayout { objectName: "connectionSetupRow"; Layout.fillWidth: true; Layout.preferredHeight: connectionPage.setupCardHeight; Layout.minimumHeight: Layout.preferredHeight; Layout.maximumHeight: Layout.preferredHeight; spacing: 16
                            ConnectionCard {
                                objectName: "gameTelemetryCard"
                                Layout.fillWidth: true; Layout.preferredWidth: 1; Layout.fillHeight: true
                                readiness: backend.telemetryReady ? 2 : backend.processId > 0 ? 1 : 0
                                fault: backend.processId > 0 && backend.readerError !== ""
                                accent: root.green
                                ColumnLayout { anchors.fill: parent; anchors.margins: 18; spacing: 8
                                    RowLayout { Layout.fillWidth: true
                                        AppText { sourceText: "1 · 打开游戏"; font.pixelSize: 17; font.weight: Font.DemiBold; Layout.fillWidth: true }
                                        StatusDot { active: backend.telemetryReady }
                                    }
                                    Rectangle { Layout.fillWidth: true; Layout.preferredHeight: 44; radius: 12; color: "#142017"; border.color: root.border
                                        RowLayout { anchors.fill: parent; anchors.leftMargin: 14; anchors.rightMargin: 14
                                            StatusDot { active: backend.telemetryReady }
                                            AppText { sourceText: backend.telemetryReady ? "游戏已就绪" : "等待游戏就绪"; Layout.fillWidth: true; font.weight: Font.DemiBold }
                                        }
                                    }
                                    AppText { sourceText: backend.telemetryReady ? "已自动检测，无需选择游戏目录。" : "启动 Ricca 并进入游戏，插件会自动检测。"; color: root.muted; font.pixelSize: 11; wrapMode: Text.WordWrap; Layout.fillWidth: true }
                                    RowLayout { Layout.fillWidth: true
                                        Rectangle { Layout.fillWidth: true; height: 58; radius: 11; color: root.panel2
                                            ColumnLayout { anchors.fill: parent; anchors.margins: 10; spacing: 3; AppText { sourceText: "当前章节"; color: root.muted; font.pixelSize: 9 } AppText { Layout.fillWidth: true; translateEnabled: false; sourceText: backend.stageName; font.pixelSize: 12; font.weight: Font.DemiBold; elide: Text.ElideRight } }
                                        }
                                        Rectangle { Layout.fillWidth: true; height: 58; radius: 11; color: root.panel2
                                            ColumnLayout { anchors.fill: parent; anchors.margins: 10; spacing: 3; AppText { sourceText: "场景模式"; color: root.muted; font.pixelSize: 9 } AppText { Layout.fillWidth: true; sourceText: backend.gameScene.toUpperCase(); color: root.cyan; font.pixelSize: 12; font.weight: Font.DemiBold; elide: Text.ElideRight } }
                                        }
                                    }
                                    Item { Layout.fillHeight: true }
                                    AppButton {
                                        objectName: "gameDetectionDetailsButton"; label: "检测不到游戏？"; Layout.fillWidth: true; Layout.preferredHeight: 28
                                        onClicked: connectionPage.detailsExpanded = !connectionPage.detailsExpanded
                                    }
                                }
                            }
                            ConnectionCard {
                                objectName: "socketConnectionCard"
                                Layout.fillWidth: true; Layout.preferredWidth: 1; Layout.fillHeight: true
                                // A running listener/QR code is not a phone connection.
                                // Only the currently selected protocol may light this card.
                                readiness: connectionPage.appConnected ? 2 : 0
                                fault: backend.serverError !== ""
                                accent: root.violet
                                ColumnLayout { anchors.fill: parent; anchors.margins: 18; spacing: 8
                                    RowLayout { Layout.fillWidth: true
                                        AppText { sourceText: "2 · 扫码连接"; font.pixelSize: 17; font.weight: Font.DemiBold; Layout.fillWidth: true }
                                        StatusDot { active: connectionPage.appConnected }
                                        AppText { sourceText: connectionPage.appConnected ? "App 在线" : "等待扫码"; color: connectionPage.appConnected ? root.violet : root.muted; font.pixelSize: 10 }
                                    }
                                    RowLayout { Layout.fillWidth: true; spacing: 10
                                        AppComboBox {
                                            objectName: "socketProtocolChoice"; Layout.fillWidth: true
                                            textRole: "name"; valueRole: "key"
                                            model: [{key:"v3",name:"V3 · 保留原有连接"},{key:"v4",name:"V4 · DG-LAB 4"}]
                                            currentIndex: backend.socketProtocol === "v4" ? 1 : 0
                                            onActivated: { backend.selectSocketProtocol(currentValue); currentIndex=Qt.binding(function() { return backend.socketProtocol === "v4" ? 1 : 0 }) }
                                        }
                                    }
                                    RowLayout { Layout.fillWidth: true; Layout.fillHeight: true; spacing: 14
                                        ColumnLayout { Layout.fillWidth: true; Layout.minimumWidth: 0; spacing: 8
                                            AppText { Layout.fillWidth: true; sourceText: connectionPage.appConnected ? "已连接，新设备会自动选择。核对设置后手动启用输出。" : "手机与电脑连接同一网络，使用 DG-LAB App 扫码。"; color: root.muted; font.pixelSize: 11; wrapMode: Text.WordWrap }
                                            AppText { objectName: "automaticOutputNotice"; Layout.fillWidth: true; sourceText: (backend.socketProtocol === "v4" ? "选择设备并恢复后同步 · 硬上限 " : "连接后自动同步 · 硬上限 ") + backend.hardCap; color: root.green; font.pixelSize: 10; wrapMode: Text.WordWrap }
                                            AppText { visible: backend.serverError !== ""; Layout.fillWidth: true; sourceText: "连接服务异常，请打开连接帮助。"; color: root.red; font.pixelSize: 10; wrapMode: Text.WordWrap }
                                        }
                                        Rectangle { visible: connectionPage.showQr; Layout.preferredWidth: 132; Layout.minimumWidth: 132; Layout.preferredHeight: 132; radius: 12; color: "white"
                                            Image { objectName: "connectionQrImage"; anchors.fill: parent; anchors.margins: 8; source: backend.qrSource; fillMode: Image.PreserveAspectFit }
                                            AppText { objectName: "connectionQrPlaceholder"; anchors.centerIn: parent; width: parent.width - 20; horizontalAlignment: Text.AlignHCenter; wrapMode: Text.WordWrap; visible: backend.qrSource === ""; sourceText: backend.serverError !== "" ? "二维码不可用\n请点“连接不上？”" : "正在生成二维码…"; color: "#6d684f"; font.pixelSize: 11 }
                                            MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; enabled: backend.qrSource !== ""; onClicked: guidePreview.openSource(backend.qrSource, "连接二维码") }
                                        }
                                    }
                                    RowLayout { Layout.fillWidth: true; spacing: 8
                                        AppButton { objectName: "toggleConnectionQrButton"; visible: connectionPage.appConnected; Layout.fillWidth: true; Layout.preferredWidth: 1; Layout.preferredHeight: 32; label: connectionPage.qrExpanded ? "收起二维码" : "显示二维码"; onClicked: connectionPage.qrExpanded = !connectionPage.qrExpanded }
                                        AppButton { objectName: "connectionHelpButton"; Layout.fillWidth: true; Layout.preferredWidth: 1; Layout.preferredHeight: 32; label: "连接不上？"; labelColor: root.yellow; onClicked: { backend.diagnoseConnection(); connectionHelp.open() } }
                                    }
                                    AppButton { objectName:"ovcQrButton"; visible:backend.socketProtocol === "v3"; Layout.fillWidth:true; Layout.preferredHeight:30; label:"负鼠 V4 二维码"; enabled:backend.v4QrSource !== ""; onClicked:guidePreview.openSource(backend.v4QrSource,"负鼠 V4 二维码") }
                                }
                            }
                        }
                        RowLayout { Layout.fillWidth: true; spacing: 12
                            AppText { sourceText: "3 · 选择设备，开始同步"; font.pixelSize: 16; font.weight: Font.DemiBold; Layout.fillWidth: true }
                            AppButton { objectName: "connectionDetailsButton"; Layout.preferredWidth: 144; Layout.preferredHeight: 30; label: connectionPage.detailsExpanded ? "收起连接详情" : "连接详情与地址"; onClicked: connectionPage.detailsExpanded = !connectionPage.detailsExpanded }
                        }
                        RowLayout {
                            objectName: "controllerControlsRow"
                            Layout.fillWidth: true; spacing: 16
                            ConnectionCard {
                                objectName: "pulseConnectionCard"
                                Layout.fillWidth: true; Layout.preferredWidth: 1; Layout.preferredHeight: 226
                                readiness: backend.deviceConnected ? backend.telemetryReady ? 2 : 1 : backend.pulseDeviceWaiting ? 1 : 0
                                accent: root.cyan
                                ColumnLayout {
                                    anchors.fill: parent; anchors.margins: 18; spacing: 9
                                    RowLayout {
                                        Layout.fillWidth: true
                                        AppText { sourceText: "郊狼 Pulse"; font.pixelSize: 17; font.bold: true; Layout.fillWidth: true }
                                        StatusDot { active: backend.deviceConnected }
                                        AppText { objectName: "pulseConnectionStatus"; sourceText: backend.pulseDeviceMuted ? "通道已静音" : backend.deviceConnected ? "设备已连接" : backend.pulseDeviceWaiting ? "等待设备就绪" : "未连接"; color: backend.pulseDeviceMuted ? root.yellow : backend.deviceConnected ? root.green : backend.pulseDeviceWaiting ? root.yellow : root.muted; font.pixelSize: 10 }
                                    }
                                    AppComboBox {
                                        objectName: "v4DeviceChoice"; visible: backend.socketProtocol === "v4"; Layout.fillWidth: true
                                        textRole: "label"; model: [{label:"请选择郊狼设备"}].concat(backend.v4Devices)
                                        currentIndex: backend.v4DeviceIndex
                                        onModelChanged: Qt.callLater(function() { currentIndex=Qt.binding(function() { return backend.v4DeviceIndex }) })
                                        onActivated: { backend.selectV4Device(currentIndex); currentIndex=Qt.binding(function() { return backend.v4DeviceIndex }) }
                                    }
                                    AppText { objectName: "pulseMuteHint"; Layout.fillWidth: true; sourceText: backend.pulseEnableReason !== "" ? backend.pulseEnableReason : "已连接，强度与波形独立保存。"; color: backend.pulseEnableReason !== "" ? root.yellow : root.muted; font.pixelSize: 10; wrapMode: Text.WordWrap; maximumLineCount: 2; elide: Text.ElideRight }
                                    AppText { sourceText: "安全上限 " + backend.hardCap; color: root.cyan; font.pixelSize: 12; font.bold: true }
                                    Item { Layout.fillHeight: true; Layout.minimumHeight: 0 }
                                    RowLayout {
                                        Layout.fillWidth: true; spacing: 8
                                        AppButton { objectName: "openPulseWorkbenchButton"; label: "进入工作台"; Layout.fillWidth: true; Layout.preferredWidth: 1; Layout.preferredHeight: 36; onClicked: root.openDeviceWorkbench("coyote", "strength") }
                                        AppButton { objectName: "pulseRoutePauseButton"; readonly property bool unavailable: (backend.pulseRoutePaused || !backend.deviceConnected || backend.emergencyStopped) && backend.pulseEnableReason !== ""; label: unavailable ? "无法启用 · 查看原因" : backend.pulseRoutePaused ? "启用 Pulse" : "暂停 Pulse"; labelColor: unavailable ? root.yellow : root.cyan; Layout.fillWidth: true; Layout.preferredWidth: 1; Layout.preferredHeight: 36; onClicked: unavailable ? backend.explainOutputUnavailable("coyote") : backend.togglePulseOutput() }
                                    }
                                }
                            }
                            ConnectionCard {
                                objectName: "ovcConnectionCard"
                                Layout.fillWidth: true; Layout.preferredWidth: 1; Layout.preferredHeight: 226
                                readiness: backend.ovcConnected ? backend.telemetryReady ? 2 : 1 : 0
                                accent: root.violet
                                ColumnLayout {
                                    anchors.fill: parent; anchors.margins: 18; spacing: 9
                                    RowLayout {
                                        Layout.fillWidth: true
                                        AppText { sourceText: "负鼠振动"; font.pixelSize: 17; font.bold: true; Layout.fillWidth: true }
                                        StatusDot { active: backend.ovcConnected }
                                        AppText { sourceText: backend.ovcConnected ? "设备已连接" : backend.ovcAccessoryHint !== "" ? "等待插入配件" : "未连接"; color: backend.ovcConnected ? root.green : backend.ovcAccessoryHint !== "" ? root.yellow : root.muted; font.pixelSize: 10 }
                                    }
                                    AppComboBox {
                                        objectName: "ovcDeviceChoice"; Layout.fillWidth: true
                                        textRole: "label"; model: [{label:"请选择负鼠设备"}].concat(backend.ovcDevices)
                                        currentIndex: backend.ovcDeviceIndex
                                        onModelChanged: Qt.callLater(function() { currentIndex=Qt.binding(function() { return backend.ovcDeviceIndex }) })
                                        onActivated: { backend.selectOvcDevice(currentIndex); currentIndex=Qt.binding(function() { return backend.ovcDeviceIndex }) }
                                    }
                                    AppText { objectName: "ovcRouteStatus"; Layout.fillWidth: true; sourceText: backend.ovcEnableReason !== "" ? backend.ovcEnableReason : backend.ovcAccessoryHint !== "" ? backend.ovcAccessoryHint : "已连接，强度与波形独立保存。"; color: backend.ovcEnableReason !== "" || backend.ovcAccessoryHint !== "" ? root.yellow : root.muted; font.pixelSize: 10; wrapMode: Text.WordWrap; maximumLineCount: 3; elide: Text.ElideRight }
                                    AppText { sourceText: "安全上限 " + backend.ovcController.hardCap; color: root.violet; font.pixelSize: 12; font.bold: true }
                                    Item { Layout.fillHeight: true; Layout.minimumHeight: 0 }
                                    RowLayout {
                                        Layout.fillWidth: true; spacing: 8
                                        AppButton { objectName: "openOvcConfigButton"; label: "进入工作台"; Layout.fillWidth: true; Layout.preferredWidth: 1; Layout.preferredHeight: 36; onClicked: root.openDeviceWorkbench("ovc", "strength") }
                                        AppButton { objectName: "ovcRoutePauseButton"; readonly property bool unavailable: (backend.ovcRoutePaused || !backend.ovcConnected || backend.emergencyStopped) && backend.ovcEnableReason !== ""; label: unavailable ? "无法启用 · 查看原因" : backend.ovcRoutePaused ? "启用振动" : "暂停振动"; labelColor: unavailable ? root.yellow : root.violet; Layout.fillWidth: true; Layout.preferredWidth: 1; Layout.preferredHeight: 36; onClicked: unavailable ? backend.explainOutputUnavailable("ovc") : backend.toggleOvcOutput() }
                                    }
                                }
                            }
                        }
                        AppText { Layout.fillWidth: true; sourceText: "两台设备可同时运行；同一个 DG-LAB 4 App 只需扫码一次。暂停与紧急归零始终在右上角。"; color: root.muted; font.pixelSize: 10; wrapMode: Text.WordWrap }
                        Card {
                            objectName: "connectionAdvancedDetails"; visible: connectionPage.detailsExpanded; Layout.fillWidth: true; Layout.preferredHeight: detailsContent.implicitHeight + 36
                            ColumnLayout { id: detailsContent; anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top; anchors.margins: 18; spacing: 12
                                AppText { sourceText: "连接详情与地址"; font.pixelSize: 16; font.weight: Font.DemiBold }
                                RowLayout { Layout.fillWidth: true; spacing: 16
                                    ColumnLayout { Layout.fillWidth: true; Layout.preferredWidth: 1; spacing: 8
                                        AppText { sourceText: "游戏检测"; font.weight: Font.DemiBold }
                                        AppText { Layout.fillWidth: true; sourceText: backend.telemetryStatus + (backend.processId ? " · PID " + backend.processId : ""); color: root.muted; font.pixelSize: 10; wrapMode: Text.WordWrap }
                                        AppText { Layout.fillWidth: true; translateEnabled: !backend.manualGamePathConfigured; sourceText: backend.manualGamePathConfigured ? backend.gameExecutablePath : "未指定路径 · 默认按进程名自动查找"; color: root.muted; font.pixelSize: 10; elide: Text.ElideMiddle }
                                        AppText { Layout.fillWidth: true; sourceText: backend.readerError !== "" ? backend.readerError : backend.gamePathStatus; color: backend.readerError !== "" ? root.red : root.muted; font.pixelSize: 10; wrapMode: Text.WordWrap }
                                        AppText { visible: backend.gameAssemblyHash !== ""; sourceText: "SHA-256 " + backend.gameAssemblyHash.slice(0, 12) + "…"; color: root.muted; font.family: "Consolas"; font.pixelSize: 9 }
                                        RowLayout { Layout.fillWidth: true; spacing: 8
                                            AppButton { Layout.fillWidth: true; Layout.preferredWidth: 1; Layout.preferredHeight: 34; label: "选择游戏 EXE"; onClicked: gameExecutableDialog.open() }
                                            AppButton { visible: backend.manualGamePathConfigured; Layout.fillWidth: true; Layout.preferredWidth: 1; Layout.preferredHeight: 34; label: "恢复自动"; onClicked: resetConfirmation.ask("恢复自动检测？", "将清除已保存的手动游戏路径，重新按进程名寻找游戏。", function() { backend.resetGameExecutablePath() }) }
                                        }
                                    }
                                    ColumnLayout { Layout.fillWidth: true; Layout.preferredWidth: 1; spacing: 8
                                        AppText { sourceText: "网络地址"; font.weight: Font.DemiBold }
                                        AppComboBox { objectName: "connectionAddressChoice"; Layout.fillWidth: true; model: backend.lanInterfaces; textRole: "label"; valueRole: "address"; currentIndex: Math.max(0, backend.lanAddresses.indexOf(backend.lanAddress)); onActivated: backend.selectLanAddress(currentValue) }
                                        AppText { Layout.fillWidth: true; sourceText: backend.bridgeStatus; color: backend.serverError !== "" ? root.red : root.muted; font.pixelSize: 10; wrapMode: Text.WordWrap }
                                        AppButton { Layout.fillWidth: true; Layout.preferredHeight: 34; label: "刷新地址"; onClicked: backend.refreshLanAddresses() }
                                    }
                                }
                                Rectangle { Layout.fillWidth: true; height: 1; color: root.border }
                                AppText { objectName: "v4DeviceStatus"; Layout.fillWidth: true; sourceText: "郊狼 Pulse · " + (backend.socketProtocol === "v4" ? backend.v4DeviceStatus : backend.bridgeStatus); color: root.yellow; font.pixelSize: 10; wrapMode: Text.WordWrap }
                                AppText { objectName: "ovcDeviceStatus"; Layout.fillWidth: true; sourceText: "负鼠振动 · " + backend.ovcDeviceStatus; color: root.yellow; font.pixelSize: 10; wrapMode: Text.WordWrap }
                                AppText { Layout.fillWidth: true; sourceText: backend.outputStatus; color: root.muted; font.pixelSize: 10; wrapMode: Text.WordWrap }
                                AppText { Layout.fillWidth: true; sourceText: backend.ovcStatus; color: root.muted; font.pixelSize: 10; wrapMode: Text.WordWrap }
                                AppText { Layout.fillWidth: true; sourceText: "外部只读 · 无注入"; color: root.muted; font.pixelSize: 10 }
                            }
                        }
                        Card { visible: connectionPage.detailsExpanded && backend.socketProtocol === "v3"; Layout.fillWidth: true; Layout.preferredHeight: 300
                            ColumnLayout { anchors.fill: parent; anchors.margins: 20; spacing: 12
                                RowLayout { Layout.fillWidth: true; AppText { sourceText: "DG-LAB 3.0 连接向导"; font.pixelSize: 17; font.weight: Font.DemiBold; Layout.fillWidth: true } AppText { sourceText: "依次完成四步"; color: root.muted; font.pixelSize: 10 } }
                                RowLayout { Layout.fillWidth: true; Layout.fillHeight: true; spacing: 12
                                    Repeater {
                                        model: [
                                            {n:"1", title:"进入设备页", source:"../assets/dglab_guide/step1_socket.png"},
                                            {n:"2", title:"初始化 Socket", source:"../assets/dglab_guide/step2_initialize.png"},
                                            {n:"3", title:"连接服务", source:"../assets/dglab_guide/step3_connect_server.png"},
                                            {n:"4", title:"扫描二维码", source:"../assets/dglab_guide/step4_camera_scan.png"}
                                        ]
                                        delegate: Rectangle {
                                            required property var modelData
                                            Layout.fillWidth: true; Layout.fillHeight: true; radius: 14; color: root.panel2; border.color: root.border
                                            clip: true
                                            Image { anchors.fill: parent; anchors.margins: 8; source: modelData.source; sourceSize: Qt.size(320, 720); fillMode: Image.PreserveAspectFit; asynchronous: true }
                                            Rectangle { anchors.left: parent.left; anchors.top: parent.top; anchors.margins: 10; width: 30; height: 30; radius: 15; color: root.pink; AppText { anchors.centerIn: parent; sourceText: modelData.n; color: "#1c2419"; font.bold: true } }
                                            Rectangle { anchors.right: parent.right; anchors.bottom: parent.bottom; anchors.margins: 10; width: 30; height: 30; radius: 15; color: "#1b281c"; border.color: root.border; AppText { anchors.centerIn: parent; sourceText: "↗"; color: root.ink; font.pixelSize: 14 } }
                                            MouseArea { anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: guidePreview.openSource(modelData.source, modelData.n + " · " + modelData.title) }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }

                Item {
                    id: personalPage
                    property int draftLow: backend.lowStrength
                    property int draftMedium: backend.mediumStrength
                    property int draftHigh: backend.highStrength
                    property int draftDeath: backend.deathStrength
                    property int draftCap: backend.hardCap
                    property bool settingsValid: 0 <= draftLow && draftLow <= draftMedium && draftMedium <= draftHigh && draftHigh <= draftDeath && draftDeath <= draftCap && draftCap <= 100
                    function applyPreset(low, medium, high, death, cap) { draftLow=low; draftMedium=medium; draftHigh=high; draftDeath=death; draftCap=cap }
                    Card { anchors.fill: parent; anchors.margins: 24
                        ColumnLayout { anchors.fill: parent; anchors.margins: 26; spacing: 11
                            RowLayout { Layout.fillWidth: true
                                AppText { sourceText: backend.outputProfile === "ovc" ? "负鼠独立强度" : "强度方案"; font.pixelSize: 17; font.weight: Font.DemiBold; Layout.fillWidth: true }
                                AppButton { objectName:"openHotkeySettingsButton"; label:"全局急停键"; onClicked:hotkeySettings.open() }
                                AppButton { visible: backend.outputProfile !== "ovc"; label: "低档预设"; onClicked: personalPage.applyPreset(5,15,25,25,30) }
                                AppButton { visible: backend.outputProfile !== "ovc"; label: "中档预设"; fillColor: Qt.rgba(root.violet.r,root.violet.g,root.violet.b,.22); onClicked: personalPage.applyPreset(15,30,40,55,60) }
                                AppButton { visible: backend.outputProfile !== "ovc"; label: "高档预设"; fillColor: Qt.rgba(root.red.r,root.red.g,root.red.b,.22); onClicked: personalPage.applyPreset(30,45,60,80,90) }
                            }
                            AppText { sourceText: "选择一套起点后，下面五项仍可分别调节；点击底部“应用并保存”后生效。"; color: root.muted; font.pixelSize: 10 }
                            Rectangle { Layout.fillWidth: true; height: 1; color: root.border }
                            IntensitySetting { Layout.fillWidth: true; title: "低强度"; detail: "轻微伤害与轻微硬直"; value: personalPage.draftLow; accent: root.cyan; onEdited: function(v) { personalPage.draftLow=v } }
                            IntensitySetting { Layout.fillWidth: true; title: "中强度"; detail: "普通受击与常规动作"; value: personalPage.draftMedium; accent: root.violet; onEdited: function(v) { personalPage.draftMedium=v } }
                            IntensitySetting { Layout.fillWidth: true; title: "高强度"; detail: "重击、撞墙与护甲破碎"; value: personalPage.draftHigh; accent: root.pink; onEdited: function(v) { personalPage.draftHigh=v } }
                            IntensitySetting { Layout.fillWidth: true; title: "死亡惩罚"; detail: "玩家死亡时的独立强度"; value: personalPage.draftDeath; accent: root.red; onEdited: function(v) { personalPage.draftDeath=v } }
                            IntensitySetting { Layout.fillWidth: true; title: "安全上限"; detail: "0 禁用设备输出，所有命令不能突破此值"; value: personalPage.draftCap; minimum: 0; accent: root.yellow; onEdited: function(v) { personalPage.draftCap=v } }
                            Item { Layout.fillHeight: true }
                            RowLayout { Layout.fillWidth: true
                                AppText { sourceText: personalPage.settingsValid ? "保存后同时应用于预览和已解锁的实时输出；所有命令受安全上限约束。" : "请保持：低强度 ≤ 中强度 ≤ 高强度 ≤ 死亡惩罚 ≤ 安全上限"; color: personalPage.settingsValid ? root.yellow : root.red; font.pixelSize: 10; Layout.fillWidth: true }
                                AppButton { label: "恢复当前设置"; onClicked: resetConfirmation.ask("放弃未保存的强度调整？", "将重新载入已保存的数值，不会恢复出厂值或改写配置文件。", function() { personalPage.draftLow=backend.lowStrength; personalPage.draftMedium=backend.mediumStrength; personalPage.draftHigh=backend.highStrength; personalPage.draftDeath=backend.deathStrength; personalPage.draftCap=backend.hardCap }) }
                                AppButton { label: "应用并保存"; fillColor: root.green; labelColor: "#18251c"; enabled: personalPage.settingsValid; onClicked: backend.saveIntensitySettings(personalPage.draftLow,personalPage.draftMedium,personalPage.draftHigh,personalPage.draftDeath,personalPage.draftCap) }
                            }
                        }
                    }
                }

                Item {
                    DeviceWorkbench {
                        id: pulseWorkbench
                        objectName: "pulseWorkbenchPage"
                        anchors.fill: parent; anchors.margins: 16
                        controller: backend
                        vibration: false
                        onWaveformLibraryRequested: waveLibrary.open()
                        onAudioSourceRequested: root.pageIndex=6
                        onHotkeySettingsRequested: hotkeySettings.open()
                        onManualControlRequested:root.pageIndex=9
                    }
                }

                Item {
                    RowLayout { anchors.fill: parent; anchors.margins: 20; spacing: 16
                        Repeater {
                            model: ["A", "B"]
                            delegate: Card {
                                required property string modelData
                                readonly property bool channelA: modelData === "A"
                                readonly property var monitorData: ({channel:modelData,
                                    name:root.waveName(channelA ? backend.waveA : backend.waveB),
                                    points:channelA ? backend.waveAPoints : backend.waveBPoints,
                                    strength:channelA ? backend.previewA : backend.previewB,
                                    color:channelA ? root.pink : root.violet,
                                    detail:backend.channelModeName(modelData)})
                                Layout.fillWidth: true; Layout.fillHeight: true
                                ColumnLayout { anchors.fill: parent; anchors.margins: 24; spacing: 12
                                    RowLayout { Layout.fillWidth: true
                                        Rectangle { width: 46; height: 46; radius: 14; color: Qt.rgba(monitorData.color.r,monitorData.color.g,monitorData.color.b,.14); AppText { anchors.centerIn: parent; sourceText: monitorData.channel; color: monitorData.color; font.pixelSize: 18; font.bold: true } }
                                        ColumnLayout { spacing: 2; AppText { sourceText: monitorData.channel + " 通道"; font.pixelSize: 17; font.weight: Font.DemiBold } AppText { sourceText: monitorData.detail; color: root.muted; font.pixelSize: 10 } }
                                        Item { Layout.fillWidth: true }
                                        AppText { sourceText: Number(monitorData.strength || 0).toFixed(1) + " / " + backend.hardCap; color: monitorData.color; font.pixelSize: 13; font.bold: true }
                                    }
                                    WaveCanvas { Layout.fillWidth: true; Layout.fillHeight: true; points: monitorData.points; accent: monitorData.color; tiled: true; animated: monitorData.strength > 0 }
                                    Rectangle { Layout.fillWidth: true; Layout.preferredHeight: 78; radius: 15; color: root.panel2
                                        RowLayout { anchors.fill: parent; anchors.margins: 15
                                            ColumnLayout { Layout.fillWidth: true; spacing: 3; AppText { sourceText: "当前选择"; color: root.muted; font.pixelSize: 9 } AppText { sourceText: monitorData.name; color: monitorData.color; font.pixelSize: 13; font.weight: Font.DemiBold } }
                                            AppText { sourceText: monitorData.strength > 0 ? (backend.outputArmed ? "实时输出请求" : "模拟预览") : "安全待机"; color: monitorData.strength > 0 ? root.green : root.yellow; font.pixelSize: 10; font.weight: Font.DemiBold }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }

                ScrollView {
                    id: storyPage
                    objectName: "storyPage"
                    clip: true; leftPadding: 24; rightPadding: 34; topPadding: 20; bottomPadding: 24
                    contentWidth: availableWidth
                    ColumnLayout { width: storyPage.availableWidth; spacing: 16
                        Card { Layout.fillWidth: true; Layout.preferredHeight: 180; ColumnLayout { anchors.fill: parent; anchors.margins: 24; spacing: 15
                            RowLayout {
                                Layout.fillWidth: true; spacing: 16
                                ColumnLayout {
                                    Layout.fillWidth: true; spacing: 3
                                    AppText { objectName: "storySpeakerLabel"; translateEnabled: !backend.hasStorySpeaker; sourceText: backend.storySpeaker; color: root.violet; font.pixelSize: 13; font.bold: true; Layout.fillWidth: true }
                                    AppText { sourceText: "LINE " + (backend.storyLine < 0 ? "—" : backend.storyLine); color: root.muted; font.family: "Consolas"; font.pixelSize: 10 }
                                }
                                Rectangle {
                                    Layout.preferredWidth: 140; Layout.preferredHeight: 30; Layout.alignment: Qt.AlignRight | Qt.AlignTop
                                    radius: 15; color: "#3c3126"
                                    AppText { objectName: "storyActivityLabel"; anchors.fill: parent; anchors.margins: 8; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter; sourceText: backend.storySceneActive ? backend.gameScene.toUpperCase() + " · " + "剧情段" : "待机"; color: root.violet; font.pixelSize: 10; font.bold: true }
                                }
                            }
                            AppText { objectName: "storyMessageLabel"; translateEnabled: !backend.hasStoryMessage; sourceText: backend.storyText; font.pixelSize: 20; lineHeight: 1.45; wrapMode: Text.WordWrap; Layout.fillWidth: true; Layout.fillHeight: true; verticalAlignment: Text.AlignVCenter }
                        } }
                        RowLayout { Layout.fillWidth:true; spacing:12
                            AppText { sourceText:backend.currentSceneId || "等待剧情场景"; color:root.muted; font.pixelSize:11; Layout.fillWidth:true; elide:Text.ElideMiddle }
                            AppButton { objectName:"openSceneLibraryButton"; label:"场景记录 · "+backend.sceneLibrary.length+" / "+backend.registeredSceneCount; Layout.preferredWidth:200; onClicked:sceneLibraryDialog.open() }
                        }
                        RowLayout { Layout.fillWidth:true
                            AppText { Layout.fillWidth:true; wrapMode:Text.WordWrap; sourceText:"剧情播放方式与循环队列已集中到各设备工作台。"; color:root.muted; font.pixelSize:12 }
                            AppButton { label:"郊狼工作台"; onClicked:root.openDeviceWorkbench("coyote","story") }
                            AppButton { label:"负鼠工作台"; onClicked:root.openDeviceWorkbench("ovc","story") }
                        }
                        RowLayout { Layout.fillWidth: true; spacing: 16
                            Card { Layout.fillWidth: true; Layout.preferredHeight: 150; ColumnLayout { anchors.fill: parent; anchors.margins: 18; spacing: 9; AppText { sourceText: "检测状态"; color: root.muted; font.pixelSize: 11 } AppText { sourceText: backend.storySceneActive ? "剧情控制器在线" : "等待 ADV / ATD / ANV 剧情"; font.pixelSize: 17; font.weight: Font.DemiBold } AppText { sourceText: "行号、说话人与正文变化会记录为事件。"; color: root.muted; wrapMode: Text.WordWrap; Layout.fillWidth: true } } }
                            Card { Layout.fillWidth: true; Layout.preferredHeight: 150; ColumnLayout { anchors.fill: parent; anchors.margins: 18; spacing: 9; AppText { sourceText: "音频共感"; color: root.muted; font.pixelSize: 11 } AppText { sourceText: backend.audioEmpathyEnabled ? "独立检测已启用" : "默认关闭"; color: backend.audioEmpathyEnabled ? root.cyan : root.muted; font.pixelSize: 17; font.weight: Font.DemiBold } AppText { sourceText: "音频采集、门限与 Pulse 模拟已移至左侧“音频共感”，不再属于事件波形映射。"; color: root.muted; wrapMode: Text.WordWrap; Layout.fillWidth: true } } }
                        }
                        Item { Layout.fillHeight: true }
                    }
                }

                ScrollView {
                    id: audioPage
                    objectName: "audioPage"
                    onVisibleChanged: if (visible && !draftDirty) Qt.callLater(loadSaved)
                    property bool draftEnabled: false
                    property string draftDeviceId: ""
                    property int draftSensitivity: 55
                    property int draftGate: 12
                    property bool draftDirty: false
                    function loadSaved() {
                        draftEnabled=backend.audioEmpathyEnabled
                        draftDeviceId=backend.audioDeviceId
                        draftSensitivity=backend.audioSensitivity
                        draftGate=backend.audioGate
                        draftDirty=false
                    }
                    Component.onCompleted: loadSaved()
                    Connections { target: backend; function onChanged() { if (!audioPage.draftDirty) audioPage.loadSaved() } }
                    clip: true
                    leftPadding: 24
                    rightPadding: 34
                    topPadding: 20
                    bottomPadding: 24
                    contentWidth: availableWidth
                    ColumnLayout {
                        width: audioPage.availableWidth; spacing: 16
                        RowLayout { Layout.fillWidth: true; spacing: 16
                            Card { Layout.fillWidth: true; Layout.preferredHeight: 260
                                ColumnLayout { anchors.fill: parent; anchors.margins: 20; spacing: 12
                                    RowLayout { Layout.fillWidth: true
                                        ColumnLayout { Layout.fillWidth: true; spacing: 3
                                            AppText { sourceText: "音频来源"; font.pixelSize: 18; font.weight: Font.DemiBold }
                                            AppText { sourceText: "优先选择“系统回环”以捕获游戏声音；录音输入适合麦克风测试。"; color: root.muted; font.pixelSize: 10 }
                                        }
                                        StatusDot { active: backend.audioEmpathyEnabled && backend.audioBackendAvailable }
                                        AppText { sourceText: backend.audioEmpathyEnabled ? "监听开启" : "监听关闭"; color: backend.audioEmpathyEnabled ? root.cyan : root.muted; font.pixelSize: 11 }
                                    }
                                    AppComboBox {
                                        id: audioDeviceChoice
                                        Layout.fillWidth: true
                                        model: backend.audioDevices
                                        textRole: "name"; valueRole: "id"
                                        currentIndex: root.audioDeviceIndex(audioPage.draftDeviceId)
                                        onActivated: { audioPage.draftDeviceId=currentValue || ""; audioPage.draftDirty=true }
                                    }
                                    RowLayout { Layout.fillWidth: true
                                        AppButton { Layout.preferredWidth: 118; label: "刷新设备"; onClicked: backend.refreshAudioDevices() }
                                        AppText { sourceText: backend.audioCaptureStatus; color: backend.audioBackendAvailable ? root.muted : root.red; font.pixelSize: 10; Layout.fillWidth: true; elide: Text.ElideRight }
                                    }
                                    AppText { visible: backend.audioDevices.length === 0; sourceText: "未找到设备。Windows 需要可用的扬声器回环或录音输入。"; color: root.yellow; font.pixelSize: 10 }
                                }
                            }
                            Card { Layout.preferredWidth: 390; Layout.preferredHeight: 260
                                ColumnLayout { anchors.fill: parent; anchors.margins: 20; spacing: 12
                                    AppText { sourceText: "工作范围"; font.pixelSize: 18; font.weight: Font.DemiBold }
                                    RowLayout { Layout.fillWidth: true
                                        AppSwitch { id: audioEnabledSwitch; objectName: "audioEnabledSwitch"; checked: audioPage.draftEnabled; onToggled: { audioPage.draftEnabled=checked; audioPage.draftDirty=true } }
                                        Item { Layout.fillWidth: true; implicitHeight: 38
                                            Column { anchors.verticalCenter: parent.verticalCenter; spacing: 3; AppText { sourceText: "启用音频共感"; font.pixelSize: 12; font.weight: Font.DemiBold } AppText { sourceText: audioPage.draftDirty ? "待应用 · 点击下方应用音频设置" : "修改后需应用；关闭后不采集声音"; color: audioPage.draftDirty ? root.yellow : root.muted; font.pixelSize: 9 } }
                                            MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: { audioPage.draftEnabled=!audioPage.draftEnabled; audioPage.draftDirty=true } }
                                        }
                                    }
                                    RowLayout { Layout.fillWidth: true
                                        AppSwitch { checked: true; enabled: false }
                                        ColumnLayout { Layout.fillWidth: true; spacing: 2; AppText { sourceText: "仅在 ADV / ATD / ANV 剧情响应"; font.pixelSize: 12; font.weight: Font.DemiBold } AppText { sourceText: "战斗不触发音频 Pulse；暂停、加载或音频失联归零"; color: root.muted; font.pixelSize: 9 } }
                                    }
                                    RowLayout { Layout.fillWidth: true
                                        AppText { sourceText: "输出通道"; color: root.muted; font.pixelSize: 10 }
                                        AppText { Layout.fillWidth: true; sourceText: "默认 B：战斗动作 / 剧情音频队列；音量只调强度"; color: root.cyan; font.pixelSize: 10; wrapMode: Text.WordWrap }
                                    }
                                    AppButton { objectName:"editAudioStoryQueueButton"; label:"剧情播放设置 →"; Layout.fillWidth:true; Layout.preferredHeight:34; onClicked:{ root.pageIndex=3; pulseWorkbench.showQueue("B") } }
                                }
                            }
                        }

                        Card { Layout.fillWidth: true; Layout.preferredHeight: 300
                            ColumnLayout { anchors.fill: parent; anchors.margins: 20; spacing: 12
                                RowLayout { Layout.fillWidth: true
                                    ColumnLayout { Layout.fillWidth: true; spacing: 2
                                        AppText { sourceText: "实时音频信号"; font.pixelSize: 18; font.weight: Font.DemiBold }
                                        AppText { sourceText: backend.audioSceneStatus; color: backend.audioPulseActive ? root.green : root.muted; font.pixelSize: 10 }
                                    }
                                    ColumnLayout { spacing: 2; AppText { sourceText: backend.audioDbfs.toFixed(1) + " dBFS"; color: root.cyan; font.pixelSize: 18; font.weight: Font.Bold; horizontalAlignment: Text.AlignRight; Layout.alignment: Qt.AlignRight } AppText { sourceText: "输入电平 " + Math.round(backend.audioLevel); color: root.muted; font.pixelSize: 9; horizontalAlignment: Text.AlignRight; Layout.alignment: Qt.AlignRight } }
                                    Rectangle { width: 124; height: 52; radius: 14; color: Qt.rgba(root.pink.r,root.pink.g,root.pink.b,.12); border.color: Qt.rgba(root.pink.r,root.pink.g,root.pink.b,.3)
                                        Column { anchors.centerIn: parent; spacing: 1; AppText { sourceText: "PULSE 强度"; color: root.muted; font.pixelSize: 8; anchors.horizontalCenter: parent.horizontalCenter } AppText { sourceText: backend.audioPulseStrength.toFixed(1); color: root.pink; font.pixelSize: 19; font.bold: true; anchors.horizontalCenter: parent.horizontalCenter } }
                                    }
                                }
                                Rectangle { Layout.fillWidth: true; Layout.preferredHeight: 34; radius: 10; color: "#111e15"; border.color: root.border
                                    Rectangle { height: parent.height; width: parent.width * Math.max(0,Math.min(100,backend.audioLevel)) / 100; radius: parent.radius; color: backend.audioLevel >= backend.audioGate ? root.cyan : "#5b5139"; Behavior on width { NumberAnimation { duration: 80 } } }
                                    Rectangle { x: parent.width * backend.audioGate / 100 - 1; width: 2; height: parent.height; color: root.yellow }
                                }
                                Rectangle { Layout.fillWidth: true; Layout.fillHeight: true; radius: 14; color: "#101b13"; border.color: backend.audioPulseActive ? root.cyan : root.border; clip: true
                                    WaveCanvas { anchors.fill: parent; anchors.margins: 14; points: backend.audioPulsePoints; accent: backend.audioPulseActive ? root.cyan : "#81775d"; showVerticalGrid: true; animated: backend.audioPulseActive }
                                    AppText { anchors.left: parent.left; anchors.bottom: parent.bottom; anchors.margins: 10; sourceText: "队列决定波形 · 音量缩放当前段强度（旧纯音频模式仍兼容）"; color: root.muted; font.pixelSize: 9 }
                                }
                            }
                        }

                        Card { Layout.fillWidth:true; Layout.preferredHeight:150
                            ColumnLayout { anchors.fill:parent; anchors.margins:20; spacing:12
                                AppText { Layout.fillWidth:true; wrapMode:Text.WordWrap; sourceText:"音频来源由两台设备共用；播放方式、增益与最低强度在各自工作台的“剧情与鉴赏”中设置。"; color:root.muted; font.pixelSize:12 }
                                RowLayout { Layout.fillWidth:true
                                    AppButton { label:"郊狼工作台"; onClicked:root.openDeviceWorkbench("coyote","story") }
                                    AppButton { label:"负鼠工作台"; onClicked:root.openDeviceWorkbench("ovc","story") }
                                    Item { Layout.fillWidth:true }
                                    AppButton { objectName:"applyAudioSettingsButton"; label:"应用音频设置"; fillColor:root.green; labelColor:"#18251c"; Layout.preferredWidth:160; onClicked:{ if(backend.saveAudioEmpathySettings(audioPage.draftEnabled,audioPage.draftDeviceId,audioPage.draftSensitivity,audioPage.draftGate,backend.audioChannel,true))audioPage.loadSaved() } }
                                }
                            }
                        }
                        Item { Layout.preferredHeight: 8 }
                    }
                }

                Item {
                    RowLayout { anchors.fill: parent; anchors.margins: 24; spacing: 16
                        Card { Layout.fillWidth: true; Layout.fillHeight: true
                            ColumnLayout { anchors.fill: parent; anchors.margins: 14; spacing: 8
                                RowLayout { Layout.fillWidth: true; AppText { sourceText: "事件流"; font.pixelSize: 16; font.weight: Font.DemiBold; Layout.fillWidth: true } Button { text: "清空"; flat: true; onClicked: backend.clearEvents(); contentItem: AppText { sourceText: parent.text; color: root.muted; horizontalAlignment: Text.AlignHCenter } } }
                                ListView { Layout.fillWidth: true; Layout.fillHeight: true; clip: true; model: backend.events; spacing: 5
                                    delegate: Rectangle { required property var modelData; width: ListView.view.width; height: 66; radius: 9; color: "#2b2c20"; border.color: "#403c2c"; RowLayout { anchors.fill: parent; anchors.margins: 10; spacing: 10; Rectangle { width: 4; Layout.fillHeight: true; radius: 2; color: root.severityColor(modelData.severity) } ColumnLayout { Layout.fillWidth: true; spacing: 3; RowLayout { Layout.fillWidth: true; AppText { sourceText: modelData.title; font.weight: Font.DemiBold; Layout.fillWidth: true } AppText { sourceText: String(modelData.time).slice(11, 23); color: root.muted; font.family: "Consolas"; font.pixelSize: 10 } } AppText { sourceText: modelData.detail; color: root.muted; font.pixelSize: 11; elide: Text.ElideRight; Layout.fillWidth: true } } } }
                                }
                            }
                        }
                        Card { Layout.preferredWidth: 470; Layout.fillHeight: true
                            ColumnLayout { anchors.fill: parent; anchors.margins: 14; spacing: 8
                                RowLayout { Layout.fillWidth: true; AppText { sourceText: "原始快照"; font.pixelSize: 16; font.weight: Font.DemiBold; Layout.fillWidth: true } AppText { sourceText: backend.pollHz.toFixed(1) + " Hz · " + backend.latencyMs.toFixed(1) + " ms"; color: root.cyan; font.family: "Consolas"; font.pixelSize: 11 } }
                                ScrollView { Layout.fillWidth: true; Layout.fillHeight: true; TextArea { text: backend.rawJson; readOnly: true; selectByMouse: true; color: "#cabf9e"; font.family: "Consolas"; font.pixelSize: 10; wrapMode: TextEdit.NoWrap; background: Rectangle { color: "#142018"; radius: 8 } } }
                                AppText { visible: backend.readerError !== ""; sourceText: backend.readerError; color: root.red; font.pixelSize: 10; wrapMode: Text.WrapAnywhere; Layout.fillWidth: true }
                            }
                        }
                    }
                }
                Item {
                    objectName: "ovcWorkbenchContainer"
                    OvcWorkbench {
                        id: ovcWorkbench
                        objectName: "ovcWorkbenchPage"
                        anchors.fill: parent
                        anchors.margins: 16
                        controller: backend.ovcController
                        onAudioSourceRequested: root.pageIndex=6
                        onManualControlRequested:root.pageIndex=9
                    }
                }
                ManualControlPage {}
            }
        }
    }

    WaveEditorDialog { id: waveformEditor }
    WaveLibraryDialog { id: waveLibrary; controller: backend; onEditRequested:function(name,points,frequency) { waveformEditor.openFrom(name,points,frequency) } }
    HotkeyDialog { id:hotkeySettings }
    HudSettingsDialog {id:hudSettings}
    ConfirmResetDialog { id: resetConfirmation }
    Popup {
        id: saveToast
        objectName: "saveToast"
        property string heading: ""
        property string message: ""
        parent: Overlay.overlay
        width: Math.min(420, parent.width - 48)
        x: parent.width - width - 24
        y: parent.height - height - 24
        z: 1000
        padding: 18
        modal: false
        closePolicy: Popup.NoAutoClose
        background: Rectangle { radius: 16; color: "#353025"; border.color: saveToast.heading === "保存成功" ? root.green : root.red }
        contentItem: ColumnLayout {
            spacing: 8
            RowLayout { Layout.fillWidth: true
                AppText { sourceText: saveToast.heading; font.pixelSize: 16; font.bold: true; color: saveToast.heading === "保存成功" ? root.green : root.red; Layout.fillWidth: true }
                AppButton { label: "×"; Layout.preferredWidth: 28; Layout.preferredHeight: 28; onClicked: saveToast.close() }
            }
            AppText { sourceText: saveToast.message; Layout.fillWidth: true; wrapMode: Text.WordWrap; font.pixelSize: 12 }
        }
    }
    Timer { id: toastTimer; interval: 3600; onTriggered: saveToast.close() }
    Connections {
        target: backend
        function onToastRequested(title, message) { saveToast.heading=title; saveToast.message=message; saveToast.open(); toastTimer.restart() }
    }
    GuidePreviewDialog { id: guidePreview }
    ChannelStrategyDialog { id: channelStrategy; controller: backend; onQueueEditorRequested:function(channel) { root.pageIndex=3; pulseWorkbench.showQueue(channel) } }
    ConnectionHelpDialog { id: connectionHelp; controller: backend }
    SceneLibraryDialog { id: sceneLibraryDialog; controller: backend }
    OnboardingDialog { id:onboarding; controller:backend; onNavigateRequested:function(page) { if (page === 2) root.openDeviceWorkbench("coyote","strength"); else if (page === 3) root.openDeviceWorkbench("coyote","battle"); else root.pageIndex=page } }
    FileDialog {
        id: gameExecutableDialog
        title: backend.localize("选择 Holy Knight Ricca 游戏程序", backend.language)
        fileMode: FileDialog.OpenFile
        nameFilters: ["Windows 程序 (*.exe)"]
        onAccepted: backend.setGameExecutablePath(selectedFile.toString())
    }
}
