import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Dialog {
    id: dialog
    objectName: "hotkeyDialog"
    parent: Overlay.overlay; anchors.centerIn: parent
    width: Math.min(740,parent.width-48); height: Math.min(365,parent.height-48)
    padding: 24; modal: true
    onOpened: chord.text=backend.emergencyHotkey
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
        LocalizedLabel { sourceText:"游戏在前台也可归零并锁定全部输出；再次按下不会恢复。默认 Ctrl+Alt+F10。"; color:"#ded7c0"; wrapMode:Text.WordWrap; Layout.fillWidth:true }
        TextField { id:chord; objectName:"emergencyHotkeyInput"; Layout.fillWidth:true; Layout.preferredHeight:44; color:"#f3ecd9"; padding:12; font.family:backend.uiFontFamily; selectByMouse:true; maximumLength:40; background:Rectangle { color:"#111a14"; radius:10; border.color:"#65573f" } }
        LocalizedLabel { sourceText:"输入至少两个修饰键和一个按键，例如 Ctrl+Shift+F9。支持 F1–F11、字母、数字等；不支持 Win、F12 或系统保留组合。"; color:"#aaa68d"; font.pixelSize:11; wrapMode:Text.WordWrap; Layout.fillWidth:true }
        LocalizedLabel { objectName:"hotkeyRegistrationStatus"; sourceText:backend.hotkeyStatus; color:"#e6be73"; wrapMode:Text.WordWrap; Layout.fillWidth:true }
        LocalizedLabel { sourceText:"保存时会先急停并保持暂停。占用或保存失败时保留原设置，成功后仍需手动恢复输出。"; color:"#e6be73"; font.pixelSize:11; wrapMode:Text.WordWrap; Layout.fillWidth:true }
        RowLayout { Layout.fillWidth:true
            Action { text:"恢复默认"; onClicked:chord.text="Ctrl+Alt+F10" }
            Item { Layout.fillWidth:true }
            Action { text:"取消"; onClicked:dialog.close() }
            Action { objectName:"saveEmergencyHotkeyButton"; text:"保存快捷键"; onClicked:if(backend.saveEmergencyHotkey(chord.text)) dialog.close() }
        }
    }
}
