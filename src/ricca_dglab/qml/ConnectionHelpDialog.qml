import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Dialog {
    id: dialog
    required property var controller
    objectName: "connectionHelpDialog"
    parent: Overlay.overlay
    anchors.centerIn: parent
    width: Math.min(820, parent.width - 60)
    height: Math.min(650, parent.height - 60)
    padding: 22
    modal: true
    background: Rectangle { color: "#25251c"; border.color: "#65573f"; radius: 20 }
    component ActionButton: Button {
        id: button
        implicitHeight: 38; leftPadding: 16; rightPadding: 16
        font.family: backend.uiFontFamily; font.pixelSize: 12
        contentItem: LocalizedLabel { sourceText: button.text; color: "#f3ecd9"; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter }
        background: Rectangle { color: button.hovered ? "#423d2b" : "#353025"; border.color: "#65573f"; radius: 10 }
    }
    contentItem: ColumnLayout {
        spacing: 16
        RowLayout { Layout.fillWidth: true
            LocalizedLabel { sourceText: "连接不上？"; font.pixelSize: 22; font.bold: true; color: "#f3ecd9"; Layout.fillWidth: true }
            ActionButton { text: "关闭"; onClicked: dialog.close() }
        }
        LocalizedLabel { Layout.fillWidth: true; wrapMode: Text.WordWrap; sourceText: "只读诊断本机服务、网卡和端口占用；不会自动修改防火墙或 VPN。"; color: "#aaa68d" }
        ScrollView { Layout.fillWidth: true; Layout.fillHeight: true; clip: true
            TextArea {
                objectName: "connectionDiagnosticText"
                text: dialog.controller.connectionDiagnostics
                readOnly: true; selectByMouse: true; wrapMode: TextEdit.Wrap
                color: "#ded7c0"; font.family: backend.uiFontFamily; font.pixelSize: 12
                padding: 14
                background: Rectangle { color: "#101b13"; radius: 12 }
            }
        }
        RowLayout { Layout.fillWidth: true; spacing: 12
            ActionButton { text: "刷新诊断"; onClicked: dialog.controller.diagnoseConnection() }
            ActionButton { text: "复制诊断"; onClicked: dialog.controller.copyConnectionDiagnostics() }
            Item { Layout.fillWidth: true }
            ActionButton { text: "重试 Socket"; onClicked: { dialog.controller.restartSocket(); dialog.close() } }
        }
        LocalizedLabel { Layout.fillWidth: true; wrapMode: Text.WordWrap; color: "#e6be73"; font.pixelSize: 10; sourceText: "重试会先归零并暂停输出。关闭占用端口的旧窗口后再重试；连接成功后，点击右上角“恢复输出”解除这次暂停。无需 A/B 测试。" }
    }
}
