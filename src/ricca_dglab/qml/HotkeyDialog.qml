import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Dialog {
    id: dialog
    objectName: "hotkeyDialog"
    parent: Overlay.overlay; anchors.centerIn: parent
    width: Math.min(740,parent.width-48); height: Math.min(410,parent.height-48)
    padding: 24; modal: true
    onOpened: { chord.chord=backend.emergencyHotkey; chord.cancelRecording() }
    onClosed: chord.cancelRecording()
    background: Rectangle { radius:20; color:"#25251c"; border.color:"#65573f" }
    component Action: Button {
        id: button
        implicitHeight:42; leftPadding:18; rightPadding:18
        contentItem: LocalizedLabel { sourceText:button.text; color:"#f3ecd9"; horizontalAlignment:Text.AlignHCenter; verticalAlignment:Text.AlignVCenter }
        background: Rectangle { radius:10; color:button.hovered ? "#4a402c" : "#353025"; border.color:"#65573f" }
    }
    contentItem: ColumnLayout {
        spacing:14
        LocalizedLabel { sourceText:"全局急停快捷键"; color:"#f3ecd9"; font.pixelSize:23; font.bold:true }
        LocalizedLabel { sourceText:"游戏在前台也可归零并锁定全部输出；再次按下不会恢复。默认 Ctrl+F12。"; color:"#ded7c0"; wrapMode:Text.WordWrap; Layout.fillWidth:true }
        HotkeyRecorder { id:chord; objectName:"emergencyHotkeyRecorder"; controller:backend; Layout.fillWidth:true }
        LocalizedLabel { objectName:"hotkeyRegistrationStatus"; sourceText:backend.hotkeyStatus; color:"#e6be73"; wrapMode:Text.WordWrap; Layout.fillWidth:true }
        LocalizedLabel { sourceText:"保存时会先急停并保持暂停。占用或保存失败时保留原设置，成功后仍需手动恢复输出。"; color:"#e6be73"; font.pixelSize:11; wrapMode:Text.WordWrap; Layout.fillWidth:true }
        RowLayout { Layout.fillWidth:true
            Action { text:"恢复默认"; onClicked:{ chord.cancelRecording(); chord.chord="Ctrl+F12" } }
            Item { Layout.fillWidth:true }
            Action { text:"取消"; onClicked:dialog.close() }
            Action { objectName:"saveEmergencyHotkeyButton"; text:"保存快捷键"; enabled:!chord.recording; onClicked:if(backend.saveEmergencyHotkey(chord.chord)) dialog.close() }
        }
    }
}
