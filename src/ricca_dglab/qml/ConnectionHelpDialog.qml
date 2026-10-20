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
    background: Rectangle { color: "#101725"; border.color: "#34465f"; radius: 20 }
    component ActionButton: Button {
        id: button
        implicitHeight: 38; leftPadding: 16; rightPadding: 16
        font.family: "Microsoft YaHei UI"; font.pixelSize: 12
        contentItem: Label { text: button.text; color: "#f7f9fd"; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter }
        background: Rectangle { color: button.hovered ? "#23304a" : "#172134"; border.color: "#34465f"; radius: 10 }
    }
    contentItem: ColumnLayout {
        spacing: 16
        RowLayout { Layout.fillWidth: true
            Label { text: "连接不上？"; font.pixelSize: 22; font.bold: true; color: "#f7f9fd"; Layout.fillWidth: true }
            ActionButton { text: "关闭"; onClicked: dialog.close() }
        }
        Label { Layout.fillWidth: true; wrapMode: Text.WordWrap; text: "只读诊断本机服务、网卡和端口占用；不会自动修改防火墙或 VPN。"; color: "#8e9aaf" }
        ScrollView { Layout.fillWidth: true; Layout.fillHeight: true; clip: true
            TextArea {
                objectName: "connectionDiagnosticText"
                text: dialog.controller.connectionDiagnostics
                readOnly: true; selectByMouse: true; wrapMode: TextEdit.Wrap
                color: "#d1daeb"; font.family: "Microsoft YaHei UI"; font.pixelSize: 12
                padding: 14
                background: Rectangle { color: "#09101b"; radius: 12 }
            }
        }
        RowLayout { Layout.fillWidth: true; spacing: 12
            ActionButton { text: "刷新诊断"; onClicked: dialog.controller.diagnoseConnection() }
            ActionButton { text: "复制诊断"; onClicked: dialog.controller.copyConnectionDiagnostics() }
            Item { Layout.fillWidth: true }
            ActionButton { text: "重试 Socket"; onClicked: { dialog.controller.restartSocket(); dialog.close() } }
        }
        Label { Layout.fillWidth: true; wrapMode: Text.WordWrap; color: "#f7c55b"; font.pixelSize: 10; text: "重试会先归零并暂停输出。关闭占用端口的旧窗口后再重试；连接成功后，点击右上角“恢复输出”解除这次暂停。无需 A/B 测试。" }
    }
}
