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
    background: Rectangle { color: "#25251c"; radius: 20; border.color: "#65573f" }
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
        contentItem: LocalizedLabel { sourceText: button.text; color: button.primary ? "#25251c" : "#f3ecd9"; font.pixelSize: 13; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter }
        background: Rectangle { radius: 11; color: button.primary ? "#e6be73" : "#353025"; border.color: "#65573f" }
    }
    contentItem: ColumnLayout {
        spacing: 20
        LocalizedLabel { sourceText: dialog.heading; color: "#f3ecd9"; font.pixelSize: 21; font.bold: true; Layout.fillWidth: true; wrapMode: Text.WordWrap }
        LocalizedLabel { sourceText: dialog.explanation; color: "#bab399"; font.pixelSize: 13; Layout.fillWidth: true; wrapMode: Text.WordWrap; lineHeight: 1.4 }
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
