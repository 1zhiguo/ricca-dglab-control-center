import QtQuick
import QtQuick.Window

Window {
    id: hudWindow
    objectName: "riccaGameHud"
    property var controller: null
    width: 730; height: 68
    visible: false
    title: "Ricca DG-LAB HUD"
    color: "transparent"
    flags: Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint |
           Qt.WindowTransparentForInput | Qt.WindowDoesNotAcceptFocus
    HudPanel {
        anchors.fill: parent
        options: backend.hudSettings
        readings: hudWindow.visible ? backend.hudReadings : ({})
        historyA: hudWindow.controller ? hudWindow.controller.historyA : []
        historyB: hudWindow.controller ? hudWindow.controller.historyB : []
    }
}
