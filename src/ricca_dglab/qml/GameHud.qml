pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Window

Window {
    id: hudWindow
    objectName: "riccaGameHud"
    property var controller: null
    readonly property real uiScale: height / 68
    readonly property bool live: backend.outputArmed && !backend.outputPaused
    width: 730; height: 68
    visible: false
    title: "Ricca DG-LAB HUD"
    color: "transparent"
    flags: Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint |
           Qt.WindowTransparentForInput | Qt.WindowDoesNotAcceptFocus

    Rectangle {
        anchors.fill: parent
        color: "#5c06090e"
        Rectangle { anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top; height: 1; color: "#3380a6e6" }
    }

    component Channel: Rectangle {
        id: channel
        required property string letter
        required property color accent
        required property real strength
        required property var history
        color: "#7a0d131f"
        Rectangle { anchors.left: parent.left; anchors.top: parent.top; anchors.bottom: parent.bottom; width: Math.max(1, 2 * hudWindow.uiScale); color: channel.accent }
        LocalizedText {
            x: parent.width * 0.025 + 4 * hudWindow.uiScale
            y: 0; height: parent.height * 0.32
            sourceText: channel.letter
            color: channel.accent; font.family: "Segoe UI"; font.bold: true; font.pixelSize: 15 * hudWindow.uiScale
            verticalAlignment: Text.AlignVCenter
        }
        LocalizedText {
            x: parent.width * 0.12; width: parent.width * 0.66
            y: 0; height: parent.height * 0.32
            sourceText: (backend.channelPolicies ? backend.channelModeName(channel.letter) : "") + " · " + (hudWindow.live ? "LIVE" : "预览")
            color: hudWindow.live ? "#b9e5d4" : "#b5bdcb"
            font.family: backend.uiFontFamily; font.pixelSize: 10 * hudWindow.uiScale
            verticalAlignment: Text.AlignVCenter; elide: Text.ElideRight
        }
        LocalizedText {
            x: parent.width * 0.82; width: parent.width * 0.145
            y: 0; height: parent.height * 0.32
            sourceText: Math.round(channel.strength)
            color: "white"; font.family: "Segoe UI"; font.bold: true; font.pixelSize: 13 * hudWindow.uiScale
            horizontalAlignment: Text.AlignRight; verticalAlignment: Text.AlignVCenter
        }
        Canvas {
            id: graph
            x: parent.width * 0.035; y: parent.height * 0.30
            width: parent.width * 0.93; height: parent.height * 0.60
            property var history: channel.history
            property bool active: hudWindow.live
            onHistoryChanged: requestPaint()
            onActiveChanged: requestPaint()
            onWidthChanged: requestPaint()
            onHeightChanged: requestPaint()
            onPaint: {
                var ctx = getContext("2d"); ctx.reset()
                ctx.strokeStyle = Qt.rgba(channel.accent.r,channel.accent.g,channel.accent.b,.10)
                ctx.lineWidth = 1
                for (var row=1; row<4; ++row) {
                    var y = height*row/4
                    ctx.beginPath(); ctx.moveTo(0,y); ctx.lineTo(width,y); ctx.stroke()
                }
                ctx.strokeStyle = Qt.rgba(channel.accent.r,channel.accent.g,channel.accent.b,.28)
                ctx.beginPath(); ctx.moveTo(width*.72,0); ctx.lineTo(width*.72,height); ctx.stroke()
                if (!history || history.length < 2) return
                ctx.strokeStyle = active ? channel.accent : "#d17a879e"
                ctx.lineWidth = 2.6 * hudWindow.uiScale
                ctx.lineJoin = "round"; ctx.lineCap = "round"; ctx.beginPath()
                for (var i=0; i<history.length; ++i) {
                    var x = width*i/(history.length-1)
                    y = height*(.92-.84*Math.max(0,Math.min(1,Number(history[i]))))
                    if (i===0) ctx.moveTo(x,y); else ctx.lineTo(x,y)
                }
                ctx.stroke()
            }
        }
    }

    Channel {
        x: hudWindow.width * 0.012; width: hudWindow.width * 0.48; height: hudWindow.height
        letter: "A"; accent: "#ff61b0"; strength: backend.previewA
        history: hudWindow.controller ? hudWindow.controller.historyA : []
    }
    Channel {
        x: hudWindow.width * 0.508; width: hudWindow.width * 0.48; height: hudWindow.height
        letter: "B"; accent: "#54d6e8"; strength: backend.previewB
        history: hudWindow.controller ? hudWindow.controller.historyB : []
    }
}
