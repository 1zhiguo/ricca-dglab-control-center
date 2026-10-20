pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Dialogs
import QtQuick.Layouts
import QtQuick.Window

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
    color: "#090b11"

    readonly property color bg: "#070a11"
    readonly property color panel: "#101725"
    readonly property color panel2: "#172134"
    readonly property color border: "#2a3850"
    readonly property color ink: "#f7f9fd"
    readonly property color muted: "#8e9aaf"
    readonly property color cyan: "#5de0ea"
    readonly property color violet: "#a78bfa"
    readonly property color red: "#ff5d7a"
    readonly property color yellow: "#f7c55b"
    readonly property color pink: "#ff6fae"
    readonly property color green: "#4adda5"
    property int pageIndex: 0
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
        return "#6e82a9"
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

    component AppText: Text {
        color: root.ink
        font.family: "Microsoft YaHei UI"
        renderType: Text.NativeRendering
    }

    component Card: Rectangle {
        color: root.panel
        radius: 20
        border.color: root.border
        border.width: 1
        clip: true
        Rectangle { anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top; anchors.leftMargin: 24; anchors.rightMargin: 24; height: 1; color: "#50617a"; opacity: .65 }
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
        AppText { anchors.centerIn: parent; text: appButton.label; color: appButton.labelColor; font.pixelSize: 13; font.weight: Font.DemiBold }
        MouseArea { id: buttonHit; anchors.fill: parent; enabled: appButton.enabled; hoverEnabled: true; cursorShape: enabled ? Qt.PointingHandCursor : Qt.ArrowCursor; onClicked: appButton.clicked() }
    }

    component AppComboBox: ComboBox {
        id: appCombo
        implicitHeight: 40; leftPadding: 14; rightPadding: 36
        font.family: "Microsoft YaHei UI"; font.pixelSize: 11
        background: Rectangle { radius: 11; color: root.panel2; border.color: appCombo.activeFocus ? root.pink : root.border }
        contentItem: AppText { leftPadding: 2; text: appCombo.displayText; verticalAlignment: Text.AlignVCenter; elide: Text.ElideRight }
        indicator: AppText { x: appCombo.width - width - 14; anchors.verticalCenter: parent.verticalCenter; text: appCombo.popup.visible ? "⌃" : "⌄"; color: appCombo.popup.visible ? root.pink : root.muted; font.pixelSize: 16 }
        delegate: ItemDelegate {
            required property int index
            width: appCombo.width - 12; height: 38; leftPadding: 12
            contentItem: AppText { text: appCombo.textAt(index); verticalAlignment: Text.AlignVCenter; elide: Text.ElideRight }
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
        color: active ? root.cyan : "#50596b"
    }

    component NavButton: Button {
        property string glyph: "•"
        property bool selected: false
        flat: true
        implicitHeight: 48
        background: Rectangle {
            radius: 14
            color: parent.selected ? Qt.rgba(root.pink.r, root.pink.g, root.pink.b, .14) : (parent.hovered ? root.panel2 : "transparent")
            border.color: parent.selected ? Qt.rgba(root.pink.r, root.pink.g, root.pink.b, .30) : "transparent"
        }
        contentItem: RowLayout {
            spacing: 12
            AppText { text: parent.parent.glyph; font.pixelSize: 18; color: parent.parent.selected ? root.pink : root.muted; Layout.preferredWidth: 22; horizontalAlignment: Text.AlignHCenter }
            AppText { text: parent.parent.text; font.pixelSize: 14; font.weight: parent.parent.selected ? Font.DemiBold : Font.Normal; color: parent.parent.selected ? root.ink : root.muted; Layout.fillWidth: true }
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
            AppText { text: parent.parent.label; color: root.muted; font.pixelSize: 12; Layout.fillWidth: true }
            AppText { text: root.compact(parent.parent.value) + " / " + root.compact(parent.parent.maximum) + parent.parent.suffix; font.pixelSize: 12; font.weight: Font.DemiBold }
        }
        Rectangle {
            Layout.fillWidth: true; Layout.preferredHeight: 8; radius: 4; color: "#242a37"; clip: true
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
            ctx.strokeStyle = "#293142"
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
                ctx.fillStyle = "#f7f9fd"
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
            AppText { text: intensitySetting.title; font.pixelSize: 14; font.weight: Font.DemiBold }
            AppText { text: intensitySetting.detail; color: root.muted; font.pixelSize: 10; Layout.fillWidth: true }
            Rectangle {
                width: 58; height: 28; radius: 9; color: Qt.rgba(intensitySetting.accent.r,intensitySetting.accent.g,intensitySetting.accent.b,.13); border.color: Qt.rgba(intensitySetting.accent.r,intensitySetting.accent.g,intensitySetting.accent.b,.28)
                AppText { anchors.centerIn: parent; text: intensitySetting.value; color: intensitySetting.accent; font.pixelSize: 12; font.weight: Font.Bold }
            }
        }
        Slider {
            Layout.fillWidth: true; from: intensitySetting.minimum; to: 100; stepSize: 1; value: intensitySetting.value
            onMoved: intensitySetting.edited(Math.round(value))
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
                    AppText { text: "自定义波形编辑器"; font.pixelSize: 22; font.weight: Font.Bold }
                    AppText { text: "从模板开始，或直接在大画布上绘制 16 点包络"; color: root.muted; font.pixelSize: 11 }
                }
                AppButton { id: closeWaveEditor; anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter; width: 96; label: "关闭"; onClicked: editor.close() }
            }
            RowLayout { Layout.fillWidth: true; spacing: 10
                TextField {
                    id: waveName; text: editor.seedName; placeholderText: "波形名称"; Layout.fillWidth: true; Layout.preferredHeight: 46; leftPadding: 14
                    color: root.ink; font.family: "Microsoft YaHei UI"; font.pixelSize: 12
                    background: Rectangle { color: root.panel2; radius: 11; border.color: waveName.activeFocus ? root.cyan : root.border }
                }
                AppButton { Layout.preferredWidth: 110; label: "呼吸"; onClicked: editor.replace([0,8,18,32,50,70,88,100,88,70,50,32,18,8,0,0], true) }
                AppButton { Layout.preferredWidth: 110; label: "心跳"; onClicked: editor.replace([0,25,100,30,0,0,0,65,15,0,0,0,25,100,25,0], true) }
                AppButton { Layout.preferredWidth: 110; label: "渐强"; onClicked: editor.replace([0,8,14,22,30,40,52,65,78,90,100,90,78,60,38,0], true) }
                AppButton { Layout.preferredWidth: 110; label: "阶梯"; onClicked: editor.replace([0,20,20,40,40,60,60,80,80,100,100,75,75,40,40,0], true) }
            }
            Rectangle {
                id: drawArea
                Layout.fillWidth: true; Layout.fillHeight: true; radius: 16; color: "#09101b"; border.color: root.cyan; clip: true
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
                    width: 116; height: 30; radius: 9; color: "#17243a"; border.color: root.cyan
                    AppText { anchors.centerIn: parent; text: "节点 " + (editor.activeIndex + 1) + " · " + editor.draftPoints[editor.activeIndex] + "%"; color: root.cyan; font.pixelSize: 10; font.weight: Font.DemiBold }
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
                AppText { text: editor.draftPoints.join(" · "); color: root.muted; font.family: "Consolas"; font.pixelSize: 8; Layout.preferredWidth: 390; elide: Text.ElideRight; horizontalAlignment: Text.AlignRight }
            }
            RowLayout { Layout.fillWidth: true; spacing: 10
                AppText { text: "频率"; color: root.muted; font.pixelSize: 11 }
                Slider { id: waveFrequency; Layout.fillWidth: true; from: 10; to: 240; stepSize: 1; value: editor.seedFrequency }
                AppText { text: Math.round(waveFrequency.value) + " Hz"; color: root.cyan; font.pixelSize: 12; font.weight: Font.DemiBold; Layout.preferredWidth: 58 }
                AppText { text: "输出仍受事件档位与硬上限限制"; color: root.yellow; font.pixelSize: 9; Layout.preferredWidth: 190; horizontalAlignment: Text.AlignRight }
                AppButton { Layout.preferredWidth: 210; fillColor: root.cyan; labelColor: "#10151a"; label: "保存到我的波形库"; onClicked: { if (backend.saveCustomWaveform(waveName.text, editor.draftPoints, Math.round(waveFrequency.value))) editor.close() } }
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
                AppText { text: guideDialog.stepTitle; font.pixelSize: 17; font.weight: Font.DemiBold; Layout.fillWidth: true }
                AppButton { Layout.preferredWidth: 72; Layout.preferredHeight: 36; label: "关闭"; onClicked: guideDialog.close() }
            }
            Rectangle {
                Layout.fillWidth: true; Layout.fillHeight: true; radius: 14; color: "#080b12"; border.color: root.border; clip: true
                Image { anchors.fill: parent; anchors.margins: 10; source: guideDialog.imageSource; fillMode: Image.PreserveAspectFit; asynchronous: true }
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
                Rectangle { width: 30; height: 30; radius: 8; color: Qt.rgba(accent.r, accent.g, accent.b, .14); AppText { anchors.centerIn: parent; text: channel; color: accent; font.bold: true } }
                AppText { text: backend.channelPolicies ? backend.channelModeName(channelCard.channel) : "通道策略"; font.pixelSize: 14; font.weight: Font.DemiBold; Layout.fillWidth: true }
                AppText { text: Math.round(strength).toString(); color: accent; font.pixelSize: 25; font.weight: Font.Bold }
            }
            Rectangle { Layout.fillWidth: true; height: 7; radius: 4; color: "#242a37"; Rectangle { height: parent.height; width: parent.width * Math.min(1, strength / Math.max(1, backend.hardCap)); radius: parent.radius; color: accent } }
            RowLayout { Layout.fillWidth: true
                AppText { text: "预览波形  " + wave; color: root.muted; font.pixelSize: 12; Layout.fillWidth: true }
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
            color: "#0c0f16"
            border.color: "#1c2230"
            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 18
                spacing: 8
                RowLayout {
                    Layout.fillWidth: true; Layout.bottomMargin: 24
                    Rectangle {
                        width: 44; height: 44; radius: 22; color: "transparent"
                        border.width: 0; clip: false
                        Image {
                            anchors.fill: parent
                            source: "../assets/branding/ricca-app-icon-round.png"
                            fillMode: Image.PreserveAspectFit; smooth: true; mipmap: true
                        }
                    }
                    ColumnLayout { spacing: 1; AppText { text: "RICCA × DG-LAB"; font.pixelSize: 14; font.weight: Font.Bold } AppText { text: "CONTROL CENTER"; color: root.muted; font.pixelSize: 9; font.letterSpacing: 1.5 } }
                }
                NavButton { Layout.fillWidth: true; text: "实时总览"; glyph: "◈"; selected: root.pageIndex === 0; onClicked: root.pageIndex = 0 }
                NavButton { Layout.fillWidth: true; text: "设备与游戏"; glyph: "⌁"; selected: root.pageIndex === 1; onClicked: root.pageIndex = 1 }
                NavButton { Layout.fillWidth: true; text: "个性化范围"; glyph: "◫"; selected: root.pageIndex === 2; onClicked: root.pageIndex = 2 }
                NavButton { Layout.fillWidth: true; text: "波形工作台"; glyph: "〰"; selected: root.pageIndex === 3; onClicked: root.pageIndex = 3 }
                NavButton { Layout.fillWidth: true; text: "A/B 波形监视"; glyph: "◉"; selected: root.pageIndex === 4; onClicked: root.pageIndex = 4 }
                Rectangle { Layout.fillWidth: true; Layout.preferredHeight: 1; Layout.topMargin: 8; Layout.bottomMargin: 8; color: root.border }
                NavButton { Layout.fillWidth: true; text: "剧情信号"; glyph: "◇"; selected: root.pageIndex === 5; onClicked: root.pageIndex = 5 }
                NavButton { Layout.fillWidth: true; text: "音频共感"; glyph: "◌"; selected: root.pageIndex === 6; onClicked: root.pageIndex = 6 }
                NavButton { Layout.fillWidth: true; text: "诊断与事件"; glyph: "≡"; selected: root.pageIndex === 7; onClicked: root.pageIndex = 7 }
                AppButton { objectName:"onboardingHelpButton"; Layout.fillWidth:true; Layout.preferredHeight:32; label:"新手教程"; labelColor:root.cyan; onClicked:onboarding.openGuide() }
                Item { Layout.fillHeight: true }
                Card {
                    Layout.preferredWidth: 196; Layout.minimumWidth: 196; Layout.maximumWidth: 196
                    Layout.preferredHeight: 112
                    color: "#121722"
                    ColumnLayout { anchors.fill: parent; anchors.margins: 13; spacing: 7
                        RowLayout { StatusDot { active: backend.telemetryOnline } AppText { text: backend.telemetryStatus; font.pixelSize: 11; Layout.fillWidth: true; Layout.minimumWidth: 0; elide: Text.ElideRight } }
                        RowLayout { StatusDot { active: backend.deviceConnected } AppText { text: backend.deviceConnected ? "DG-LAB 已连接" : "等待手机连接"; font.pixelSize: 11; Layout.fillWidth: true; Layout.minimumWidth: 0; elide: Text.ElideRight } }
                        Rectangle { Layout.fillWidth: true; height: 1; color: root.border }
                        AppText { text: "v" + backend.version + "  ·  " + (backend.outputArmed ? backend.outputPaused ? "PAUSED" : "LIVE" : "SAFE"); color: backend.outputArmed && !backend.outputPaused ? root.red : root.yellow; font.pixelSize: 10; font.letterSpacing: 1 }
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
                    AppText { Layout.fillWidth: true; Layout.minimumWidth: 0; text: ["实时总览", "设备与游戏", "个性化范围", "波形工作台", "A/B 波形监视", "剧情信号", "音频共感", "诊断与事件"][root.pageIndex]; font.pixelSize: 22; font.weight: Font.Bold; elide: Text.ElideRight }
                    AppText { Layout.fillWidth: true; Layout.minimumWidth: 0; text: ["游戏状态、角色与事件输出总览", "连接 Ricca 只读遥测并使用 DG-LAB 3.0 扫码", "设置共感档位与安全硬上限", "选择官方预设或创建自定义波形", "查看两个通道的当前波形和预览强度", "识别剧情行号、说话人与正文", "检测系统音频并转换为实时 Pulse 包络", "逐项核对指针、动作与触发边沿"][root.pageIndex]; color: root.muted; font.pixelSize: 11; elide: Text.ElideRight }
                }
                RowLayout {
                    id: headerActions
                    anchors.right: parent.right; anchors.rightMargin: 30
                    anchors.verticalCenter: parent.verticalCenter; spacing: 14
                    width: 484; height: 38
                    Rectangle {
                        id: hudToggle
                        Layout.preferredWidth: 88; Layout.preferredHeight: 38; radius: 19
                        color: backend.gameHudEnabled ? Qt.rgba(root.cyan.r,root.cyan.g,root.cyan.b,.14) : root.panel2
                        border.color: backend.gameHudEnabled ? Qt.rgba(root.cyan.r,root.cyan.g,root.cyan.b,.5) : root.border
                        Row {
                            anchors.centerIn: parent; spacing: 7
                            AppText { text: "HUD"; color: backend.gameHudEnabled ? root.cyan : root.muted; font.pixelSize: 10; font.bold: true; anchors.verticalCenter: parent.verticalCenter }
                            Rectangle {
                                width: 30; height: 18; radius: 9; color: backend.gameHudEnabled ? root.cyan : "#303b50"
                                Rectangle { width: 12; height: 12; radius: 6; y: 3; x: backend.gameHudEnabled ? 15 : 3; color: backend.gameHudEnabled ? "#10232b" : "#cbd5e3"; Behavior on x { NumberAnimation { duration: 150 } } }
                            }
                        }
                        MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: backend.setGameHudEnabled(!backend.gameHudEnabled) }
                    }
                    Rectangle { Layout.preferredWidth: 164; Layout.preferredHeight: 38; radius: 19; color: Qt.rgba((backend.outputArmed ? root.red : root.yellow).r, (backend.outputArmed ? root.red : root.yellow).g, (backend.outputArmed ? root.red : root.yellow).b, .10); border.color: Qt.rgba((backend.outputArmed ? root.red : root.yellow).r, (backend.outputArmed ? root.red : root.yellow).g, (backend.outputArmed ? root.red : root.yellow).b, .30); Row { anchors.centerIn: parent; spacing: 8; Rectangle { width: 8; height: 8; radius: 4; color: backend.outputArmed ? root.red : backend.deviceConnected ? root.green : root.yellow; anchors.verticalCenter: parent.verticalCenter } AppText { objectName: "outputStateBadge"; text: backend.priorityOutputStatus !== "" ? backend.priorityOutputStatus + " · 输出中" : backend.userOutputPaused || (backend.outputArmed && backend.outputPaused) ? "输出已暂停" : backend.outputArmed ? "实时输出中" : backend.deviceConnected ? "设备已连接" : "等待设备连接"; color: backend.outputArmed ? root.red : backend.deviceConnected ? root.green : root.yellow; font.pixelSize: 10; font.bold: true } } }
                    AppButton { objectName: "outputPauseButton"; Layout.preferredWidth: 92; Layout.preferredHeight: 38; label: backend.priorityOutputStatus === "死亡惩罚" ? (backend.userOutputPaused ? "恢复普通输出" : "暂停普通输出") : backend.userOutputPaused ? "恢复输出" : backend.outputArmed && backend.outputPaused ? "已暂停" : "暂停输出"; labelColor: backend.outputArmed && !backend.outputPaused ? root.red : root.yellow; onClicked: backend.toggleOutputPause() }
                    AppButton { Layout.preferredWidth: 98; Layout.preferredHeight: 38; label: "紧急归零"; fillColor: Qt.rgba(root.red.r, root.red.g, root.red.b, .12); labelColor: root.red; onClicked: backend.emergencyStop() }
                }
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
                            color: "#211d16"; border.color: "#564521"
                            RowLayout { anchors.fill: parent; anchors.margins: 13
                                AppText { text: backend.outputArmed ? backend.outputPaused ? "输出暂停" : "实时输出" : "安全待机"; color: backend.outputArmed && !backend.outputPaused ? root.red : root.yellow; font.bold: true }
                                AppText { text: backend.outputStatus; color: "#c9bd9d"; Layout.fillWidth: true; font.pixelSize: 12 }
                                Button { text: "连接设置"; flat: true; onClicked: root.pageIndex = 1; contentItem: AppText { text: parent.text; color: root.yellow; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter } }
                            }
                        }
                        GridLayout {
                            Layout.fillWidth: true; columns: 3; columnSpacing: 16; rowSpacing: 16
                            Card {
                                Layout.fillWidth: true; Layout.columnSpan: 2; Layout.preferredHeight: 220
                                ColumnLayout { anchors.fill: parent; anchors.margins: 19; spacing: 13
                                    RowLayout { Layout.fillWidth: true
                                        AppText { text: "PLAYER"; color: root.muted; font.pixelSize: 10; font.letterSpacing: 1.4; Layout.fillWidth: true }
                                        AppText { objectName: "armorMultiplierStatus"; text: (backend.sensitivityStage > 0 ? "已破甲" : "未破甲") + " · Pulse ×" + backend.sensitivityMultiplier.toFixed(1); color: root.yellow; font.pixelSize: 12; font.weight: Font.DemiBold }
                                        AppText { text: backend.playerState; color: root.cyan; font.pixelSize: 12 }
                                    }
                                    MetricBar { Layout.fillWidth: true; label: "HP"; value: backend.currentHp; maximum: backend.maxHp; accent: root.red }
                                    MetricBar { Layout.fillWidth: true; label: "MP"; value: backend.currentMp; maximum: backend.maxMp; accent: root.violet }
                                    MetricBar { Layout.fillWidth: true; label: "ARMOR · LEVEL " + backend.armorLevel + " / " + Math.max(0, backend.armorLevelCount - 1); value: backend.armorHp; maximum: backend.armorMaxHp; accent: root.yellow }
                                    RowLayout { Layout.fillWidth: true
                                        ColumnLayout { Layout.fillWidth: true; spacing: 2; AppText { text: "当前动作"; color: root.muted; font.pixelSize: 10 } AppText { text: backend.actionName; font.pixelSize: 16; font.weight: Font.DemiBold } }
                                        ColumnLayout { spacing: 2; AppText { text: "ACTION HASH"; color: root.muted; font.pixelSize: 10 } AppText { text: backend.actionHash; font.family: "Consolas"; font.pixelSize: 13 } }
                                    }
                                }
                            }
                            Card {
                                Layout.fillWidth: true; Layout.preferredHeight: 220
                                ColumnLayout { anchors.fill: parent; anchors.margins: 19; spacing: 11
                                    AppText { text: "SESSION"; color: root.muted; font.pixelSize: 10; font.letterSpacing: 1.4 }
                                    AppText { text: backend.stageName; font.pixelSize: 21; font.weight: Font.DemiBold }
                                    AppText { text: "场景  " + backend.gameScene.toUpperCase(); color: root.cyan; font.pixelSize: 12 }
                                    Item { Layout.fillHeight: true }
                                    RowLayout { Layout.fillWidth: true; AppText { text: "PID " + backend.processId; color: root.muted; font.pixelSize: 11; Layout.fillWidth: true } AppText { text: backend.pollHz.toFixed(1) + " Hz"; color: root.ink; font.family: "Consolas" } }
                                    AppText { text: "读取延迟 " + backend.latencyMs.toFixed(1) + " ms"; color: root.muted; font.pixelSize: 11 }
                                    RowLayout { Layout.fillWidth: true
                                        AppText { text: "破甲增幅 ×" + backend.sensitivityMultiplier.toFixed(1); color: root.yellow; font.pixelSize: 11; Layout.fillWidth: true }
                                        AppText { text: "复活 / 重新进入后重置"; color: root.muted; font.pixelSize: 10 }
                                    }
                                }
                            }
                            ChannelCard { Layout.fillWidth: true; channel: "A"; strength: backend.previewA; wave: backend.waveA; points: backend.waveAPoints; accent: root.red }
                            ChannelCard { Layout.fillWidth: true; channel: "B"; strength: backend.previewB; wave: backend.waveB; points: backend.waveBPoints; accent: root.violet }
                            Card {
                                Layout.fillWidth: true; Layout.preferredHeight: 128
                                ColumnLayout { anchors.fill: parent; anchors.margins: 16; spacing: 7
                                    RowLayout { Layout.fillWidth: true; AppText { text: "BOSS"; color: root.muted; font.pixelSize: 10; font.letterSpacing: 1.4; Layout.fillWidth: true } AppText { text: backend.bossActive ? "ENGAGED" : "IDLE"; color: backend.bossActive ? root.red : root.muted; font.pixelSize: 10; font.bold: true } }
                                    MetricBar { Layout.fillWidth: true; label: backend.bossState; value: backend.bossHp; maximum: backend.bossMaxHp; accent: root.red }
                                    AppText { text: backend.bossAction; color: root.muted; font.pixelSize: 11 }
                                }
                            }
                        }
                        Card {
                            objectName: "captureOverviewCard"
                            Layout.fillWidth: true; Layout.preferredHeight: 124
                            ColumnLayout { anchors.fill: parent; anchors.margins: 18; spacing: 8
                                RowLayout { Layout.fillWidth: true
                                    AppText { text: "捕获与挣扎"; font.pixelSize: 15; font.weight: Font.DemiBold; Layout.fillWidth: true }
                                    AppText { objectName: "captureStatusText"; text: backend.captureStatus.label; color: backend.captureStatus.active ? root.yellow : root.muted; font.pixelSize: 13; font.bold: true }
                                }
                                MetricBar { Layout.fillWidth: true; label: "挣扎进度 · " + Math.round(backend.captureStatus.progress * 100) + "%"; value: backend.captureStatus.count; maximum: backend.captureStatus.maximum; accent: root.cyan }
                                AppText { Layout.fillWidth: true; text: backend.captureStatus.active ? "挣扎反馈持续至挣脱，保持所选强度与波形；暂停或读取异常时停止。" : backend.captureStatus.known ? "当前未受困 · 逃脱后残留计数不计入进度。" : "等待可用的捕获遥测；读取异常不会触发捕获 Pulse。"; color: root.muted; font.pixelSize: 10; wrapMode: Text.WordWrap }
                            }
                        }
                        Card {
                            objectName: "defeatSceneOverview"
                            Layout.fillWidth: true; Layout.preferredHeight: backend.canConfirmCurrentDefeatScene ? 94 : 76
                            ColumnLayout { anchors.fill: parent; anchors.margins: 16; spacing: 5
                                RowLayout { Layout.fillWidth: true; spacing: 12
                                    AppText { objectName: "defeatSceneStatusLabel"; text: backend.defeatSceneStatus; color: root.yellow; font.pixelSize: 13; Layout.fillWidth: true; elide: Text.ElideRight }
                                    AppButton { objectName: "confirmCurrentDefeatButton"; visible: backend.canConfirmCurrentDefeatScene; Layout.preferredWidth: 168; Layout.preferredHeight: 32; label: "接管当前败北互动"; labelColor: root.yellow; onClicked: resetConfirmation.ask("确认接管当前败北互动？", "请确认当前是败北后的互动，而不是回想。确认后将按通道设置开始循环 Pulse，不补发之前未记录的死亡惩罚。请先核对强度；紧急归零可停止全部输出。", function() { backend.confirmCurrentDefeatScene() }, "确认接管") }
                                }
                                AppText { text: "HP 归零惩罚优先于普通暂停 · 互动期间循环 · 紧急归零停止全部输出"; color: root.muted; font.pixelSize: 10; Layout.fillWidth: true; wrapMode: Text.WordWrap }
                            }
                        }
                        AppText { text: "最近事件"; font.pixelSize: 15; font.weight: Font.DemiBold; Layout.topMargin: 4 }
                        Card {
                            Layout.fillWidth: true; Layout.preferredHeight: 230
                            ListView {
                                anchors.fill: parent; anchors.margins: 8; clip: true; spacing: 2
                                model: backend.events
                                delegate: Rectangle {
                                    required property var modelData
                                    width: ListView.view.width; height: 48; radius: 8; color: hover.hovered ? "#181e29" : "transparent"
                                    HoverHandler { id: hover }
                                    RowLayout { anchors.fill: parent; anchors.leftMargin: 10; anchors.rightMargin: 10; spacing: 10
                                        Rectangle { width: 4; height: 25; radius: 2; color: root.severityColor(modelData.severity) }
                                        AppText { text: String(modelData.time).slice(11, 23); color: root.muted; font.family: "Consolas"; font.pixelSize: 10; Layout.preferredWidth: 76 }
                                        AppText { text: modelData.title; font.pixelSize: 12; font.weight: Font.DemiBold; Layout.preferredWidth: 205; elide: Text.ElideRight }
                                        AppText { text: modelData.detail; color: root.muted; font.pixelSize: 11; Layout.fillWidth: true; elide: Text.ElideRight }
                                    }
                                }
                                AppText { anchors.centerIn: parent; text: "等待游戏事件…"; color: root.muted; visible: parent.count === 0 }
                            }
                        }
                        Item { Layout.preferredHeight: 12 }
                    }
                }

                ScrollView {
                    id: connectionPage
                    clip: true; leftPadding: 16; rightPadding: 16; topPadding: 16; bottomPadding: 16
                    contentWidth: availableWidth
                    ColumnLayout { width: connectionPage.availableWidth; spacing: 16
                        RowLayout { Layout.fillWidth: true; Layout.preferredHeight: root.width < 1240 ? 520 : 440; Layout.minimumHeight: Layout.preferredHeight; Layout.maximumHeight: Layout.preferredHeight; spacing: 16
                            Card { Layout.fillWidth: true; Layout.fillHeight: true
                                ColumnLayout { anchors.fill: parent; anchors.margins: 24; spacing: 14
                                    RowLayout { Layout.fillWidth: true
                                        AppText { text: "Ricca 外部遥测"; font.pixelSize: 17; font.weight: Font.DemiBold; Layout.fillWidth: true }
                                        AppText { text: "自动连接"; color: root.muted; font.pixelSize: 10 }
                                    }
                                    AppText { text: "无需安装 BepInEx，不向游戏注入 DLL；控制中心只通过 ReadProcessMemory 读取已验证字段。"; color: root.muted; font.pixelSize: 11; wrapMode: Text.WordWrap; Layout.fillWidth: true }
                                    Rectangle { Layout.fillWidth: true; Layout.preferredHeight: 44; radius: 12; color: "#0b1220"; border.color: root.border
                                        RowLayout { anchors.fill: parent; anchors.leftMargin: 14; anchors.rightMargin: 14
                                            StatusDot { active: backend.telemetryOnline }
                                            AppText { text: backend.telemetryStatus; Layout.fillWidth: true; font.weight: Font.DemiBold }
                                            AppText { text: backend.processId ? "PID " + backend.processId : "等待进程"; color: root.cyan; font.family: "Consolas" }
                                        }
                                    }
                                    AppText { text: backend.telemetryOnline ? "游戏、场景、HP、动作与护甲遥测均已就绪" : "启动游戏并进入可操作场景后会自动绑定"; color: backend.telemetryOnline ? root.green : root.yellow; font.pixelSize: 10 }
                                    RowLayout { Layout.fillWidth: true
                                        Rectangle { Layout.fillWidth: true; height: 72; radius: 13; color: root.panel2
                                            ColumnLayout { anchors.fill: parent; anchors.margins: 12; spacing: 4; AppText { text: "当前章节"; color: root.muted; font.pixelSize: 9 } AppText { text: backend.stageName; font.pixelSize: 15; font.weight: Font.DemiBold } }
                                        }
                                        Rectangle { Layout.fillWidth: true; height: 72; radius: 13; color: root.panel2
                                            ColumnLayout { anchors.fill: parent; anchors.margins: 12; spacing: 4; AppText { text: "场景模式"; color: root.muted; font.pixelSize: 9 } AppText { text: backend.gameScene.toUpperCase(); color: root.cyan; font.pixelSize: 15; font.weight: Font.DemiBold } }
                                        }
                                    }
                                    Item { Layout.fillHeight: true }
                                    Rectangle {
                                        Layout.fillWidth: true; Layout.preferredHeight: 96; radius: 13
                                        color: backend.readerError !== "" ? "#241821" : "#0b1220"
                                        border.color: backend.readerError !== "" ? root.red : root.border
                                        ColumnLayout {
                                            anchors.fill: parent; anchors.margins: 12; spacing: 7
                                            RowLayout {
                                                Layout.fillWidth: true; spacing: 8
                                                ColumnLayout {
                                                    Layout.fillWidth: true; spacing: 2
                                                    AppText { text: "自动检测失败回退"; font.weight: Font.DemiBold; font.pixelSize: 11 }
                                                    AppText {
                                                        Layout.fillWidth: true
                                                        text: backend.manualGamePathConfigured ? backend.gameExecutablePath : "未指定路径 · 默认按进程名自动查找"
                                                        color: root.muted; font.pixelSize: 9; elide: Text.ElideMiddle
                                                    }
                                                }
                                                AppButton { Layout.preferredWidth: 112; Layout.preferredHeight: 36; label: "选择游戏 EXE"; onClicked: gameExecutableDialog.open() }
                                                AppButton { visible: backend.manualGamePathConfigured; Layout.preferredWidth: 86; Layout.preferredHeight: 36; label: "恢复自动"; onClicked: resetConfirmation.ask("恢复自动检测？", "将清除已保存的手动游戏路径，重新按进程名寻找游戏。", function() { backend.resetGameExecutablePath() }) }
                                            }
                                            RowLayout {
                                                Layout.fillWidth: true; spacing: 8
                                                StatusDot { active: backend.manualGamePathConfigured ? backend.gamePathSupported : backend.telemetryOnline }
                                                AppText {
                                                    Layout.fillWidth: true
                                                    text: backend.readerError !== "" ? backend.readerError : backend.gamePathStatus
                                                    color: backend.readerError !== "" ? root.red : backend.manualGamePathConfigured ? (backend.gamePathSupported ? root.green : root.red) : root.muted
                                                    font.pixelSize: 9; elide: Text.ElideRight
                                                }
                                                AppText {
                                                    visible: backend.gameAssemblyHash !== ""
                                                    text: "SHA-256 " + backend.gameAssemblyHash.slice(0, 12) + "…"
                                                    color: root.muted; font.family: "Consolas"; font.pixelSize: 8
                                                }
                                                AppText { text: "外部只读 · 无注入"; color: root.yellow; font.pixelSize: 9 }
                                            }
                                        }
                                    }
                                }
                            }
                            Card { Layout.preferredWidth: 510; Layout.minimumWidth: 470; Layout.fillHeight: true
                                RowLayout { anchors.fill: parent; anchors.margins: 20; spacing: 16
                                    ColumnLayout { Layout.fillWidth: true; Layout.minimumWidth: 210; spacing: 6
                                        AppText { text: "DG-LAB Socket"; font.pixelSize: 17; font.weight: Font.DemiBold }
                                        AppText { text: backend.bridgeStatus; color: backend.serverError !== "" ? root.red : backend.deviceConnected ? root.green : root.yellow; font.pixelSize: 10; wrapMode: Text.WordWrap; Layout.fillWidth: true; maximumLineCount: 3; elide: Text.ElideRight }
                                        AppComboBox { objectName: "connectionAddressChoice"; Layout.fillWidth: true; model: backend.lanInterfaces; textRole: "label"; valueRole: "address"; currentIndex: Math.max(0, backend.lanAddresses.indexOf(backend.lanAddress)); onActivated: backend.selectLanAddress(currentValue) }
                                        AppText { text: backend.lanAddress; color: root.muted; font.family: "Consolas"; font.pixelSize: 9 }
                                        RowLayout { Layout.fillWidth: true; spacing: 7
                                            AppButton { Layout.fillWidth: true; Layout.preferredHeight: 32; label: "刷新地址"; onClicked: backend.refreshLanAddresses() }
                                            AppButton { objectName: "connectionHelpButton"; Layout.fillWidth: true; Layout.preferredHeight: 32; label: "连接不上？"; labelColor: root.yellow; onClicked: { backend.diagnoseConnection(); connectionHelp.open() } }
                                        }
                                        Rectangle { Layout.fillWidth: true; height: 1; color: root.border }
                                        AppText { objectName: "automaticOutputNotice"; text: "连接后自动同步 · 硬上限 " + backend.hardCap; color: root.green; font.pixelSize: 11; wrapMode: Text.WordWrap; Layout.fillWidth: true }
                                        AppText { text: "请先设置适合自己的低强度与硬上限。暂停 / 恢复和紧急归零始终位于右上角。"; color: root.muted; font.pixelSize: 9; wrapMode: Text.WordWrap; Layout.fillWidth: true }
                                        AppText { text: backend.outputStatus; color: root.muted; font.pixelSize: 8; wrapMode: Text.WordWrap; Layout.fillWidth: true }
                                        Item { Layout.fillHeight: true }
                                    }
                                    Rectangle { Layout.preferredWidth: 200; Layout.minimumWidth: 200; Layout.preferredHeight: 200; radius: 14; color: "white"
                                        Image { objectName: "connectionQrImage"; anchors.fill: parent; anchors.margins: 10; source: backend.qrSource; fillMode: Image.PreserveAspectFit }
                                        AppText { objectName: "connectionQrPlaceholder"; anchors.centerIn: parent; width: parent.width - 28; horizontalAlignment: Text.AlignHCenter; wrapMode: Text.WordWrap; visible: backend.qrSource === ""; text: backend.serverError !== "" ? "二维码不可用\nSocket 服务启动失败\n请点“连接不上？”" : backend.serverReady ? "二维码暂不可用\n请点“连接不上？”" : "正在启动 Socket 服务…"; color: backend.serverError !== "" ? "#b83550" : "#4b5565"; font.pixelSize: 12 }
                                    }
                                }
                            }
                        }
                        Card { Layout.fillWidth: true; Layout.preferredHeight: 300
                            ColumnLayout { anchors.fill: parent; anchors.margins: 20; spacing: 12
                                RowLayout { Layout.fillWidth: true; AppText { text: "DG-LAB 3.0 连接向导"; font.pixelSize: 17; font.weight: Font.DemiBold; Layout.fillWidth: true } AppText { text: "依次完成四步"; color: root.muted; font.pixelSize: 10 } }
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
                                            Image { anchors.fill: parent; anchors.margins: 8; source: modelData.source; fillMode: Image.PreserveAspectFit; asynchronous: true }
                                            Rectangle { anchors.left: parent.left; anchors.top: parent.top; anchors.margins: 10; width: 30; height: 30; radius: 15; color: root.pink; AppText { anchors.centerIn: parent; text: modelData.n; color: "#11151c"; font.bold: true } }
                                            Rectangle { anchors.right: parent.right; anchors.bottom: parent.bottom; anchors.margins: 10; width: 30; height: 30; radius: 15; color: "#0e1625"; border.color: root.border; AppText { anchors.centerIn: parent; text: "↗"; color: root.ink; font.pixelSize: 14 } }
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
                                AppText { text: "强度方案"; font.pixelSize: 17; font.weight: Font.DemiBold; Layout.fillWidth: true }
                                AppButton { label: "低档预设"; onClicked: personalPage.applyPreset(5,15,25,25,30) }
                                AppButton { label: "中档预设"; fillColor: Qt.rgba(root.violet.r,root.violet.g,root.violet.b,.22); onClicked: personalPage.applyPreset(15,30,40,55,60) }
                                AppButton { label: "高档预设"; fillColor: Qt.rgba(root.red.r,root.red.g,root.red.b,.22); onClicked: personalPage.applyPreset(30,45,60,80,90) }
                            }
                            AppText { text: "选择一套起点后，下面五项仍可分别调节；点击底部“应用并保存”后生效。"; color: root.muted; font.pixelSize: 10 }
                            Rectangle { Layout.fillWidth: true; height: 1; color: root.border }
                            IntensitySetting { Layout.fillWidth: true; title: "低强度"; detail: "轻微伤害与轻微硬直"; value: personalPage.draftLow; accent: root.cyan; onEdited: function(v) { personalPage.draftLow=v } }
                            IntensitySetting { Layout.fillWidth: true; title: "中强度"; detail: "普通受击与常规动作"; value: personalPage.draftMedium; accent: root.violet; onEdited: function(v) { personalPage.draftMedium=v } }
                            IntensitySetting { Layout.fillWidth: true; title: "高强度"; detail: "重击、撞墙与护甲破碎"; value: personalPage.draftHigh; accent: root.pink; onEdited: function(v) { personalPage.draftHigh=v } }
                            IntensitySetting { Layout.fillWidth: true; title: "死亡惩罚"; detail: "玩家死亡时的独立强度"; value: personalPage.draftDeath; accent: root.red; onEdited: function(v) { personalPage.draftDeath=v } }
                            IntensitySetting { Layout.fillWidth: true; title: "安全上限"; detail: "0 禁用设备输出，所有命令不能突破此值"; value: personalPage.draftCap; minimum: 0; accent: root.yellow; onEdited: function(v) { personalPage.draftCap=v } }
                            Item { Layout.fillHeight: true }
                            RowLayout { Layout.fillWidth: true
                                AppText { text: personalPage.settingsValid ? "保存后同时应用于预览和已解锁的实时输出；所有命令受安全上限约束。" : "请保持：低强度 ≤ 中强度 ≤ 高强度 ≤ 死亡惩罚 ≤ 安全上限"; color: personalPage.settingsValid ? root.yellow : root.red; font.pixelSize: 10; Layout.fillWidth: true }
                                AppButton { label: "恢复当前设置"; onClicked: resetConfirmation.ask("放弃未保存的强度调整？", "将重新载入已保存的数值，不会恢复出厂值或改写配置文件。", function() { personalPage.draftLow=backend.lowStrength; personalPage.draftMedium=backend.mediumStrength; personalPage.draftHigh=backend.highStrength; personalPage.draftDeath=backend.deathStrength; personalPage.draftCap=backend.hardCap }) }
                                AppButton { label: "应用并保存"; fillColor: root.green; labelColor: "#10151a"; enabled: personalPage.settingsValid; onClicked: backend.saveIntensitySettings(personalPage.draftLow,personalPage.draftMedium,personalPage.draftHigh,personalPage.draftDeath,personalPage.draftCap) }
                            }
                        }
                    }
                }

                Item {
                    id: empathyPage
                    property string catalogFilter: "all"
                    property string selectedWaveKey: "impact"
                    property bool fixedMode: false
                    property var selectedWave: root.waveItem(selectedWaveKey)
                    property var filteredCatalog: {
                        var values = []
                        for (var i=0; i<backend.waveformCatalog.length; ++i) {
                            var item = backend.waveformCatalog[i]
                            if (catalogFilter === "all" || item.group === catalogFilter) values.push(item)
                        }
                        return values
                    }
                    ColumnLayout { anchors.fill: parent; anchors.margins: 16; spacing: 14
                        RowLayout { Layout.fillWidth: true; Layout.preferredHeight: 42
                            AppButton { label: "智能分段"; fillColor: !empathyPage.fixedMode ? root.pink : root.panel2; labelColor: !empathyPage.fixedMode ? "#10151a" : root.ink; onClicked: empathyPage.fixedMode=false }
                            AppButton { label: "固定预设"; fillColor: empathyPage.fixedMode ? root.pink : root.panel2; labelColor: empathyPage.fixedMode ? "#10151a" : root.ink; onClicked: empathyPage.fixedMode=true }
                            Item { Layout.fillWidth: true }
                            AppButton { objectName: "restoreMappingsButton"; label: "恢复默认"; onClicked: resetConfirmation.ask("恢复默认通道策略？", "将恢复 A / B 通道策略及事件映射并保存。不会修改强度、安全硬上限或音频设置，也不会删除自定义波形。恢复后自动应用，保留手动暂停状态。", function() { if (backend.resetEventMappings()) { empathyPage.fixedMode=false; empathyPage.selectedWaveKey="impact" } }) }
                            AppButton { label: empathyPage.fixedMode ? "应用固定波形" : "分别保存通道策略"; fillColor: root.green; labelColor: "#10151a"; enabled: empathyPage.fixedMode; onClicked: backend.applyWaveformToAllEvents(empathyPage.selectedWaveKey) }
                        }
                        Card { Layout.fillWidth: true; Layout.preferredHeight: 282
                            ColumnLayout { anchors.fill: parent; anchors.margins: 16; spacing: 9
                                RowLayout { Layout.fillWidth: true
                                    AppText { text: "波形预设与我的波形库"; font.pixelSize: 17; font.weight: Font.DemiBold }
                                    AppText { text: empathyPage.filteredCatalog.length + " 个波形"; color: root.muted; font.pixelSize: 10; Layout.fillWidth: true }
                                    Repeater { model: [{key:"all",label:"全部"},{key:"official",label:"官方波形"},{key:"custom",label:"自定义波形"},{key:"builtin",label:"内置波形"}]
                                        delegate: AppButton { required property var modelData; Layout.preferredWidth: 92; Layout.preferredHeight: 34; label: modelData.label; fillColor: empathyPage.catalogFilter===modelData.key ? root.pink : root.panel2; labelColor: empathyPage.catalogFilter===modelData.key ? "#10151a" : root.ink; onClicked: empathyPage.catalogFilter=modelData.key }
                                    }
                                }
                                ListView { id: waveGallery; Layout.fillWidth: true; Layout.fillHeight: true; orientation: ListView.Horizontal; spacing: 10; clip: true; boundsBehavior: Flickable.StopAtBounds; model: empathyPage.filteredCatalog
                                    delegate: Rectangle {
                                        required property var modelData
                                        width: 250; height: waveGallery.height; radius: 14; color: waveHover.hovered ? Qt.lighter(root.panel2,1.08) : root.panel2
                                        border.color: empathyPage.selectedWaveKey===modelData.key ? modelData.color : root.border
                                        HoverHandler { id: waveHover }
                                        MouseArea { anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: empathyPage.selectedWaveKey=modelData.key }
                                        ColumnLayout { anchors.fill: parent; anchors.margins: 11; spacing: 5
                                            RowLayout { Layout.fillWidth: true; AppText { text: modelData.name; font.weight: Font.DemiBold; font.pixelSize: 11; Layout.fillWidth: true; elide: Text.ElideRight } AppText { text: modelData.group==="custom" ? "自定义" : modelData.source; color: modelData.group==="custom" ? root.cyan : root.muted; font.pixelSize: 8 } }
                                            WaveCanvas { Layout.fillWidth: true; Layout.fillHeight: true; points: modelData.points; accent: modelData.color; tiled: true; animated: waveHover.hovered }
                                            RowLayout { Layout.fillWidth: true; AppText { text: modelData.frequency + " Hz"; color: root.muted; font.pixelSize: 9; Layout.fillWidth: true } AppText { text: empathyPage.selectedWaveKey===modelData.key ? "已选择" : "悬停预览"; color: empathyPage.selectedWaveKey===modelData.key ? modelData.color : root.muted; font.pixelSize: 9 } }
                                        }
                                    }
                                }
                                RowLayout { Layout.fillWidth: true; AppText { text: "拖动卡片区域或使用滚轮浏览"; color: root.muted; font.pixelSize: 9; Layout.fillWidth: true } AppButton { Layout.preferredWidth: 54; Layout.preferredHeight: 32; label: "‹"; onClicked: waveGallery.contentX=Math.max(0,waveGallery.contentX-260) } AppButton { Layout.preferredWidth: 54; Layout.preferredHeight: 32; label: "›"; onClicked: waveGallery.contentX=Math.min(Math.max(0,waveGallery.contentWidth-waveGallery.width),waveGallery.contentX+260) } }
                            }
                        }
                        RowLayout { Layout.fillWidth: true; Layout.fillHeight: true; spacing: 14
                            Card { Layout.preferredWidth: 420; Layout.fillHeight: true
                                ColumnLayout { anchors.fill: parent; anchors.margins: 20; spacing: 10
                                    RowLayout { Layout.fillWidth: true; AppText { text: empathyPage.fixedMode ? "固定波形" : "通道策略"; font.pixelSize: 17; font.weight: Font.DemiBold; Layout.fillWidth: true } AppText { text: empathyPage.fixedMode ? "始终使用" : "A / B"; color: root.muted; font.pixelSize: 10 } }
                                    Rectangle { Layout.fillWidth: true; Layout.fillHeight: true; radius: 15; color: root.panel2; border.color: root.cyan
                                        RowLayout { anchors.fill: parent; anchors.margins: 14; spacing: 12
                                            Rectangle { width: 46; height: 46; radius: 14; color: Qt.rgba(root.cyan.r,root.cyan.g,root.cyan.b,.15); AppText { anchors.centerIn: parent; text: "A"; color: root.cyan; font.pixelSize: 19; font.bold: true } }
                                            ColumnLayout { Layout.fillWidth: true; spacing: 2; AppText { text: "A 通道 · " + (backend.channelPolicies ? backend.channelModeName("A") : ""); font.pixelSize: 14; font.weight: Font.DemiBold } AppText { text: "独立来源、强度、波形与时长"; color: root.muted; font.pixelSize: 9 } }
                                            WaveCanvas { Layout.preferredWidth: 112; Layout.fillHeight: true; points: empathyPage.fixedMode ? empathyPage.selectedWave.points : root.waveItem("impact").points; accent: root.cyan; tiled: true }
                                            AppText { text: "›"; color: root.cyan; font.pixelSize: 24 }
                                        }
                                        MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: channelStrategy.openChannel("A") }
                                    }
                                    Rectangle { Layout.fillWidth: true; Layout.fillHeight: true; radius: 15; color: root.panel2; border.color: root.violet
                                        RowLayout { anchors.fill: parent; anchors.margins: 14; spacing: 12
                                            Rectangle { width: 46; height: 46; radius: 14; color: Qt.rgba(root.violet.r,root.violet.g,root.violet.b,.15); AppText { anchors.centerIn: parent; text: "B"; color: root.violet; font.pixelSize: 19; font.bold: true } }
                                            ColumnLayout { Layout.fillWidth: true; spacing: 2; AppText { text: "B 通道 · " + (backend.channelPolicies ? backend.channelModeName("B") : ""); font.pixelSize: 14; font.weight: Font.DemiBold } AppText { text: "独立配置 · 重叠时较强者接管"; color: root.muted; font.pixelSize: 9 } }
                                            WaveCanvas { Layout.preferredWidth: 112; Layout.fillHeight: true; points: empathyPage.fixedMode ? empathyPage.selectedWave.points : root.waveItem("heavy_land").points; accent: root.violet; tiled: true }
                                            AppText { text: "›"; color: root.violet; font.pixelSize: 24 }
                                        }
                                        MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: channelStrategy.openChannel("B") }
                                    }
                                }
                            }
                            Card { Layout.fillWidth: true; Layout.fillHeight: true
                                ColumnLayout { anchors.fill: parent; anchors.margins: 20; spacing: 10
                                    RowLayout { Layout.fillWidth: true; AppText { text: "自定义波形设计器"; font.pixelSize: 17; font.weight: Font.DemiBold; Layout.fillWidth: true } AppText { text: "独立窗口编辑"; color: root.muted; font.pixelSize: 10 } }
                                    Rectangle { Layout.fillWidth: true; Layout.fillHeight: true; radius: 15; color: "#0b1220"; border.color: empathyPage.selectedWave.color
                                        ColumnLayout { anchors.fill: parent; anchors.margins: 14; spacing: 7
                                            RowLayout { Layout.fillWidth: true; AppText { text: empathyPage.selectedWave.name; font.pixelSize: 14; font.weight: Font.DemiBold; Layout.fillWidth: true } AppText { text: empathyPage.selectedWave.frequency + " Hz"; color: root.cyan; font.pixelSize: 10 } }
                                            WaveCanvas { Layout.fillWidth: true; Layout.fillHeight: true; points: empathyPage.selectedWave.points; accent: empathyPage.selectedWave.color; tiled: true; animated: true }
                                            AppText { text: "打开编辑器可使用模板、平滑、镜像、归一化和撤销。"; color: root.muted; font.pixelSize: 9 }
                                        }
                                    }
                                    RowLayout { Layout.fillWidth: true
                                        AppButton { Layout.fillWidth: true; label: "新建波形"; onClicked: waveformEditor.openFrom("Ricca 自定义",[0,18,48,82,100,58,20,0,0,25,68,45,15,0,0,0],92) }
                                        AppButton { Layout.fillWidth: true; label: "编辑当前波形"; fillColor: root.cyan; labelColor: "#10151a"; onClicked: waveformEditor.openFrom(empathyPage.selectedWave.name,empathyPage.selectedWave.points,empathyPage.selectedWave.frequency) }
                                        AppButton { Layout.preferredWidth: 92; label: "打开目录"; onClicked: backend.openWaveformLibraryFolder() }
                                    }
                                }
                            }
                        }
                    }

                }

                Item {
                    RowLayout { anchors.fill: parent; anchors.margins: 20; spacing: 16
                        Repeater {
                            model: [
                                {channel:"A", name:root.waveName(backend.waveA), points:backend.waveAPoints, strength:backend.previewA, color:root.pink, detail:backend.channelPolicies ? backend.channelModeName("A") : ""},
                                {channel:"B", name:root.waveName(backend.waveB), points:backend.waveBPoints, strength:backend.previewB, color:root.violet, detail:backend.channelPolicies ? backend.channelModeName("B") : ""}
                            ]
                            delegate: Card {
                                required property var modelData
                                Layout.fillWidth: true; Layout.fillHeight: true
                                ColumnLayout { anchors.fill: parent; anchors.margins: 24; spacing: 12
                                    RowLayout { Layout.fillWidth: true
                                        Rectangle { width: 46; height: 46; radius: 14; color: Qt.rgba(modelData.color.r,modelData.color.g,modelData.color.b,.14); AppText { anchors.centerIn: parent; text: modelData.channel; color: modelData.color; font.pixelSize: 18; font.bold: true } }
                                        ColumnLayout { spacing: 2; AppText { text: modelData.channel + " 通道"; font.pixelSize: 17; font.weight: Font.DemiBold } AppText { text: modelData.detail; color: root.muted; font.pixelSize: 10 } }
                                        Item { Layout.fillWidth: true }
                                        AppText { text: modelData.strength.toFixed(1) + " / " + backend.hardCap; color: modelData.color; font.pixelSize: 13; font.bold: true }
                                    }
                                    WaveCanvas { Layout.fillWidth: true; Layout.fillHeight: true; points: modelData.points; accent: modelData.color; tiled: true; animated: modelData.strength > 0 }
                                    Rectangle { Layout.fillWidth: true; Layout.preferredHeight: 78; radius: 15; color: root.panel2
                                        RowLayout { anchors.fill: parent; anchors.margins: 15
                                            ColumnLayout { Layout.fillWidth: true; spacing: 3; AppText { text: "当前选择"; color: root.muted; font.pixelSize: 9 } AppText { text: modelData.name; color: modelData.color; font.pixelSize: 13; font.weight: Font.DemiBold } }
                                            AppText { text: modelData.strength > 0 ? (backend.outputArmed ? "实时输出请求" : "模拟预览") : "安全待机"; color: modelData.strength > 0 ? root.green : root.yellow; font.pixelSize: 10; font.weight: Font.DemiBold }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }

                Item {
                    ColumnLayout { anchors.fill: parent; anchors.margins: 30; spacing: 18
                        Card { Layout.fillWidth: true; Layout.preferredHeight: 250; ColumnLayout { anchors.fill: parent; anchors.margins: 24; spacing: 15
                            RowLayout { Layout.fillWidth: true; ColumnLayout { Layout.fillWidth: true; AppText { text: backend.storySpeaker; color: root.violet; font.pixelSize: 13; font.bold: true } AppText { text: "LINE " + (backend.storyLine < 0 ? "—" : backend.storyLine); color: root.muted; font.family: "Consolas"; font.pixelSize: 10 } } Rectangle { width: 120; height: 30; radius: 15; color: "#241e37"; AppText { anchors.centerIn: parent; text: backend.storySceneActive ? backend.gameScene.toUpperCase() + " ACTIVE" : "STANDBY"; color: root.violet; font.pixelSize: 10; font.bold: true } } }
                            AppText { text: backend.storyText; font.pixelSize: 20; lineHeight: 1.45; wrapMode: Text.WordWrap; Layout.fillWidth: true; Layout.fillHeight: true; verticalAlignment: Text.AlignVCenter }
                        } }
                        RowLayout { Layout.fillWidth: true; spacing: 16
                            Card { Layout.fillWidth: true; Layout.preferredHeight: 150; ColumnLayout { anchors.fill: parent; anchors.margins: 18; spacing: 9; AppText { text: "检测状态"; color: root.muted; font.pixelSize: 11 } AppText { text: backend.storySceneActive ? "剧情控制器在线" : "等待 ADV / ATD 剧情"; font.pixelSize: 17; font.weight: Font.DemiBold } AppText { text: "行号、说话人与正文变化会记录为事件。"; color: root.muted; wrapMode: Text.WordWrap; Layout.fillWidth: true } } }
                            Card { Layout.fillWidth: true; Layout.preferredHeight: 150; ColumnLayout { anchors.fill: parent; anchors.margins: 18; spacing: 9; AppText { text: "音频共感"; color: root.muted; font.pixelSize: 11 } AppText { text: backend.audioEmpathyEnabled ? "独立检测已启用" : "默认关闭"; color: backend.audioEmpathyEnabled ? root.cyan : root.muted; font.pixelSize: 17; font.weight: Font.DemiBold } AppText { text: "音频采集、门限与 Pulse 模拟已移至左侧“音频共感”，不再属于事件波形映射。"; color: root.muted; wrapMode: Text.WordWrap; Layout.fillWidth: true } } }
                        }
                        Item { Layout.fillHeight: true }
                    }
                }

                ScrollView {
                    id: audioPage
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
                            Card { Layout.fillWidth: true; Layout.preferredHeight: 224
                                ColumnLayout { anchors.fill: parent; anchors.margins: 20; spacing: 12
                                    RowLayout { Layout.fillWidth: true
                                        ColumnLayout { Layout.fillWidth: true; spacing: 3
                                            AppText { text: "音频来源"; font.pixelSize: 18; font.weight: Font.DemiBold }
                                            AppText { text: "优先选择“系统回环”以捕获游戏声音；录音输入适合麦克风测试。"; color: root.muted; font.pixelSize: 10 }
                                        }
                                        StatusDot { active: backend.audioEmpathyEnabled && backend.audioBackendAvailable }
                                        AppText { text: backend.audioEmpathyEnabled ? "监听开启" : "监听关闭"; color: backend.audioEmpathyEnabled ? root.cyan : root.muted; font.pixelSize: 11 }
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
                                        AppText { text: backend.audioCaptureStatus; color: backend.audioBackendAvailable ? root.muted : root.red; font.pixelSize: 10; Layout.fillWidth: true; elide: Text.ElideRight }
                                    }
                                    AppText { visible: backend.audioDevices.length === 0; text: "未找到设备。Windows 需要可用的扬声器回环或录音输入。"; color: root.yellow; font.pixelSize: 10 }
                                }
                            }
                            Card { Layout.preferredWidth: 390; Layout.preferredHeight: 224
                                ColumnLayout { anchors.fill: parent; anchors.margins: 20; spacing: 12
                                    AppText { text: "工作范围"; font.pixelSize: 18; font.weight: Font.DemiBold }
                                    RowLayout { Layout.fillWidth: true
                                        Switch { id: audioEnabledSwitch; objectName: "audioEnabledSwitch"; checked: audioPage.draftEnabled; onToggled: { audioPage.draftEnabled=checked; audioPage.draftDirty=true } }
                                        Item { Layout.fillWidth: true; implicitHeight: 38
                                            Column { anchors.verticalCenter: parent.verticalCenter; spacing: 3; AppText { text: "启用音频共感"; font.pixelSize: 12; font.weight: Font.DemiBold } AppText { text: audioPage.draftDirty ? "待应用 · 点击下方应用音频设置" : "修改后需应用；关闭后不采集声音"; color: audioPage.draftDirty ? root.yellow : root.muted; font.pixelSize: 9 } }
                                            MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: { audioPage.draftEnabled=!audioPage.draftEnabled; audioPage.draftDirty=true } }
                                        }
                                    }
                                    RowLayout { Layout.fillWidth: true
                                        Switch { checked: true; enabled: false }
                                        ColumnLayout { Layout.fillWidth: true; spacing: 2; AppText { text: "仅在 ADV / ATD 剧情场景响应"; font.pixelSize: 12; font.weight: Font.DemiBold } AppText { text: "暂停、加载与其他场景仍由安全门归零"; color: root.muted; font.pixelSize: 9 } }
                                    }
                                    RowLayout { Layout.fillWidth: true
                                        AppText { text: "输出通道"; color: root.muted; font.pixelSize: 10 }
                                        AppText { Layout.fillWidth: true; text: "在 A / B 通道策略中选择剧情音频"; color: root.cyan; font.pixelSize: 10; wrapMode: Text.WordWrap }
                                    }
                                }
                            }
                        }

                        Card { Layout.fillWidth: true; Layout.preferredHeight: 300
                            ColumnLayout { anchors.fill: parent; anchors.margins: 20; spacing: 12
                                RowLayout { Layout.fillWidth: true
                                    ColumnLayout { Layout.fillWidth: true; spacing: 2
                                        AppText { text: "实时音频信号"; font.pixelSize: 18; font.weight: Font.DemiBold }
                                        AppText { text: backend.audioSceneStatus; color: backend.audioPulseActive ? root.green : root.muted; font.pixelSize: 10 }
                                    }
                                    ColumnLayout { spacing: 2; AppText { text: backend.audioDbfs.toFixed(1) + " dBFS"; color: root.cyan; font.pixelSize: 18; font.weight: Font.Bold; horizontalAlignment: Text.AlignRight; Layout.alignment: Qt.AlignRight } AppText { text: "输入电平 " + Math.round(backend.audioLevel); color: root.muted; font.pixelSize: 9; horizontalAlignment: Text.AlignRight; Layout.alignment: Qt.AlignRight } }
                                    Rectangle { width: 124; height: 52; radius: 14; color: Qt.rgba(root.pink.r,root.pink.g,root.pink.b,.12); border.color: Qt.rgba(root.pink.r,root.pink.g,root.pink.b,.3)
                                        Column { anchors.centerIn: parent; spacing: 1; AppText { text: "PULSE 强度"; color: root.muted; font.pixelSize: 8; anchors.horizontalCenter: parent.horizontalCenter } AppText { text: backend.audioPulseStrength.toFixed(1); color: root.pink; font.pixelSize: 19; font.bold: true; anchors.horizontalCenter: parent.horizontalCenter } }
                                    }
                                }
                                Rectangle { Layout.fillWidth: true; Layout.preferredHeight: 34; radius: 10; color: "#0b1019"; border.color: root.border
                                    Rectangle { height: parent.height; width: parent.width * Math.max(0,Math.min(100,backend.audioLevel)) / 100; radius: parent.radius; color: backend.audioLevel >= audioGateSlider.value ? root.cyan : "#344159"; Behavior on width { NumberAnimation { duration: 80 } } }
                                    Rectangle { x: parent.width * audioGateSlider.value / 100 - 1; width: 2; height: parent.height; color: root.yellow }
                                }
                                Rectangle { Layout.fillWidth: true; Layout.fillHeight: true; radius: 14; color: "#09101b"; border.color: backend.audioPulseActive ? root.cyan : root.border; clip: true
                                    WaveCanvas { anchors.fill: parent; anchors.margins: 14; points: backend.audioPulsePoints; accent: backend.audioPulseActive ? root.cyan : "#53647e"; showVerticalGrid: true; animated: backend.audioPulseActive }
                                    AppText { anchors.left: parent.left; anchors.bottom: parent.bottom; anchors.margins: 10; text: "系统音频包络 → Pulse（不使用预设波形）"; color: root.muted; font.pixelSize: 9 }
                                }
                            }
                        }

                        Card { Layout.fillWidth: true; Layout.preferredHeight: 198
                            ColumnLayout { anchors.fill: parent; anchors.margins: 20; spacing: 12
                                RowLayout { Layout.fillWidth: true; AppText { text: "转换参数"; font.pixelSize: 18; font.weight: Font.DemiBold; Layout.fillWidth: true } AppText { text: "安全上限 " + backend.hardCap; color: root.yellow; font.pixelSize: 11 } }
                                RowLayout { Layout.fillWidth: true; spacing: 14
                                    AppText { text: "灵敏度"; Layout.preferredWidth: 68; color: root.muted; font.pixelSize: 11 }
                                    Slider { id: audioSensitivitySlider; Layout.fillWidth: true; from: 1; to: 100; stepSize: 1; value: audioPage.draftSensitivity; onMoved: { audioPage.draftSensitivity=Math.round(value); audioPage.draftDirty=true } }
                                    Rectangle { width: 58; height: 32; radius: 9; color: root.panel2; AppText { anchors.centerIn: parent; text: Math.round(audioSensitivitySlider.value); color: root.cyan; font.bold: true } }
                                }
                                RowLayout { Layout.fillWidth: true; spacing: 14
                                    AppText { text: "噪声门限"; Layout.preferredWidth: 68; color: root.muted; font.pixelSize: 11 }
                                    Slider { id: audioGateSlider; Layout.fillWidth: true; from: 0; to: 95; stepSize: 1; value: audioPage.draftGate; onMoved: { audioPage.draftGate=Math.round(value); audioPage.draftDirty=true } }
                                    Rectangle { width: 58; height: 32; radius: 9; color: root.panel2; AppText { anchors.centerIn: parent; text: Math.round(audioGateSlider.value); color: root.yellow; font.bold: true } }
                                }
                                RowLayout { Layout.fillWidth: true
                                    AppText { text: "输出按音频包络连续变化，并始终受“个性化范围”的安全上限约束。"; color: root.muted; font.pixelSize: 9; Layout.fillWidth: true }
                                    AppButton { objectName: "applyAudioSettingsButton"; Layout.preferredWidth: 154; fillColor: root.green; labelColor: "#10151a"; label: "应用音频设置"; onClicked: { if (backend.saveAudioEmpathySettings(audioPage.draftEnabled,audioPage.draftDeviceId,audioPage.draftSensitivity,audioPage.draftGate,backend.audioChannel,true)) audioPage.loadSaved() } }
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
                                RowLayout { Layout.fillWidth: true; AppText { text: "事件流"; font.pixelSize: 16; font.weight: Font.DemiBold; Layout.fillWidth: true } Button { text: "清空"; flat: true; onClicked: backend.clearEvents(); contentItem: AppText { text: parent.text; color: root.muted; horizontalAlignment: Text.AlignHCenter } } }
                                ListView { Layout.fillWidth: true; Layout.fillHeight: true; clip: true; model: backend.events; spacing: 5
                                    delegate: Rectangle { required property var modelData; width: ListView.view.width; height: 66; radius: 9; color: "#151a24"; border.color: "#202735"; RowLayout { anchors.fill: parent; anchors.margins: 10; spacing: 10; Rectangle { width: 4; Layout.fillHeight: true; radius: 2; color: root.severityColor(modelData.severity) } ColumnLayout { Layout.fillWidth: true; spacing: 3; RowLayout { Layout.fillWidth: true; AppText { text: modelData.title; font.weight: Font.DemiBold; Layout.fillWidth: true } AppText { text: String(modelData.time).slice(11, 23); color: root.muted; font.family: "Consolas"; font.pixelSize: 10 } } AppText { text: modelData.detail; color: root.muted; font.pixelSize: 11; elide: Text.ElideRight; Layout.fillWidth: true } } } }
                                }
                            }
                        }
                        Card { Layout.preferredWidth: 470; Layout.fillHeight: true
                            ColumnLayout { anchors.fill: parent; anchors.margins: 14; spacing: 8
                                RowLayout { Layout.fillWidth: true; AppText { text: "原始快照"; font.pixelSize: 16; font.weight: Font.DemiBold; Layout.fillWidth: true } AppText { text: backend.pollHz.toFixed(1) + " Hz · " + backend.latencyMs.toFixed(1) + " ms"; color: root.cyan; font.family: "Consolas"; font.pixelSize: 11 } }
                                ScrollView { Layout.fillWidth: true; Layout.fillHeight: true; TextArea { text: backend.rawJson; readOnly: true; selectByMouse: true; color: "#b7c2d9"; font.family: "Consolas"; font.pixelSize: 10; wrapMode: TextEdit.NoWrap; background: Rectangle { color: "#0c1017"; radius: 8 } } }
                                AppText { visible: backend.readerError !== ""; text: backend.readerError; color: root.red; font.pixelSize: 10; wrapMode: Text.WrapAnywhere; Layout.fillWidth: true }
                            }
                        }
                    }
                }
            }
        }
    }

    WaveEditorDialog { id: waveformEditor }
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
        background: Rectangle { radius: 16; color: "#172134"; border.color: saveToast.heading === "保存成功" ? root.green : root.red }
        contentItem: ColumnLayout {
            spacing: 8
            RowLayout { Layout.fillWidth: true
                AppText { text: saveToast.heading; font.pixelSize: 16; font.bold: true; color: saveToast.heading === "保存成功" ? root.green : root.red; Layout.fillWidth: true }
                AppButton { label: "×"; Layout.preferredWidth: 28; Layout.preferredHeight: 28; onClicked: saveToast.close() }
            }
            AppText { text: saveToast.message; Layout.fillWidth: true; wrapMode: Text.WordWrap; font.pixelSize: 12 }
        }
    }
    Timer { id: toastTimer; interval: 3600; onTriggered: saveToast.close() }
    Connections { target: backend; function onToastRequested(title, message) { saveToast.heading=title; saveToast.message=message; saveToast.open(); toastTimer.restart() } }
    GuidePreviewDialog { id: guidePreview }
    ChannelStrategyDialog { id: channelStrategy; controller: backend }
    ConnectionHelpDialog { id: connectionHelp; controller: backend }
    OnboardingDialog { id:onboarding; controller:backend; onNavigateRequested:function(page) { root.pageIndex=page } }
    FileDialog {
        id: gameExecutableDialog
        title: "选择 Holy Knight Ricca 游戏程序"
        fileMode: FileDialog.OpenFile
        nameFilters: ["Windows 程序 (*.exe)"]
        onAccepted: backend.setGameExecutablePath(selectedFile.toString())
    }
}
