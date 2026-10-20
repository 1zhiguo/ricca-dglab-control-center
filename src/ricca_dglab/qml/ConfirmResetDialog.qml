import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Dialog {
    id: dialog
    objectName: "confirmResetDialog"
    property string heading: "确认恢复默认？"
    property string explanation: ""
    property string confirmLabel: "确认恢复"
    property var action: null
    parent: Overlay.overlay
    anchors.centerIn: parent
    width: Math.min(540, parent.width - 64)
    padding: 24
    modal: true
    closePolicy: Popup.CloseOnEscape
    background: Rectangle { color: "#101725"; radius: 20; border.color: "#34465f" }
    function ask(title, body, callback, buttonLabel) {
        heading = title; explanation = body; action = callback
        confirmLabel = buttonLabel || "确认恢复"
        open()
    }
    onClosed: action = null
    component ActionButton: Button {
        id: button
        property bool primary: false
        implicitHeight: 42; leftPadding: 20; rightPadding: 20
        contentItem: Label { text: button.text; color: button.primary ? "#101725" : "#f7f9fd"; font.pixelSize: 13; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter }
        background: Rectangle { radius: 11; color: button.primary ? "#f7c55b" : "#172134"; border.color: "#34465f" }
    }
    contentItem: ColumnLayout {
        spacing: 20
        Label { text: dialog.heading; color: "#f7f9fd"; font.pixelSize: 21; font.bold: true; Layout.fillWidth: true; wrapMode: Text.WordWrap }
        Label { text: dialog.explanation; color: "#a8b5ca"; font.pixelSize: 13; Layout.fillWidth: true; wrapMode: Text.WordWrap; lineHeight: 1.4 }
        RowLayout {
            Layout.alignment: Qt.AlignRight; spacing: 12
            ActionButton { objectName: "cancelResetButton"; text: "取消"; onClicked: dialog.close() }
            ActionButton {
                primary: true
                objectName: "confirmResetButton"; text: dialog.confirmLabel
                onClicked: { var callback = dialog.action; dialog.close(); if (callback) callback() }
            }
        }
    }
}
