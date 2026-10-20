import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

ColumnLayout {
    id: recorder
    required property var controller
    property string chord: ""
    property bool recording: false
    property bool invalidKey: false
    spacing: 10
    function cancelRecording() { recording=false; invalidKey=false }
    function beginRecording() {
        controller.emergencyStop()
        recording=true; invalidKey=false
        capture.forceActiveFocus()
    }
    RowLayout {
        Layout.fillWidth: true; spacing: 12
        Rectangle {
            Layout.fillWidth:true; Layout.preferredHeight:48
            color:"#111a14"; radius:10; border.color:recorder.recording ? "#8fbd83" : "#65573f"
            LocalizedLabel { anchors.fill:parent; anchors.margins:12; sourceText:recorder.recording ? "请直接按下快捷键…" : recorder.chord; color:"#f3ecd9"; font.pixelSize:18; verticalAlignment:Text.AlignVCenter }
        }
        Button {
            id:capture; objectName:"emergencyHotkeyCapture"
            Layout.preferredHeight:48; leftPadding:18; rightPadding:18
            text:recorder.recording ? "重新录入" : "录入按键"
            contentItem: LocalizedLabel { sourceText:capture.text; color:"#f3ecd9"; horizontalAlignment:Text.AlignHCenter; verticalAlignment:Text.AlignVCenter }
            background:Rectangle { radius:10; color:"#353025"; border.color:capture.activeFocus ? "#8fbd83" : "#65573f" }
            onClicked:recorder.beginRecording()
            onActiveFocusChanged:if(!activeFocus) recorder.cancelRecording()
            Keys.priority:Keys.BeforeItem
            Keys.onPressed:function(event) {
                if(!recorder.recording) return
                event.accepted=true
                if(event.isAutoRepeat) return
                if(event.key===Qt.Key_Escape) { recorder.cancelRecording(); return }
                if(event.key===Qt.Key_Control || event.key===Qt.Key_Shift || event.key===Qt.Key_Alt || event.key===Qt.Key_Meta) return
                let value=recorder.controller.captureEmergencyHotkey(event.key,event.modifiers)
                recorder.invalidKey=value===""
                if(value!=="") { recorder.chord=value; recorder.recording=false }
            }
            Keys.onReleased:function(event) { if(recorder.recording) event.accepted=true }
        }
    }
    LocalizedLabel {
        Layout.fillWidth:true; wrapMode:Text.WordWrap; font.pixelSize:11
        sourceText:recorder.invalidKey ? "不支持此按键，请换一个；Esc 取消录入。" : "支持单键或组合键，如 Pause、F10、Ctrl+F12；Esc 取消。单键请避开游戏操作键。"
        color:recorder.invalidKey ? "#ff5d7a" : "#aaa68d"
    }
}
