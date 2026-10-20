import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Dialog {
    id: dialog
    required property var controller
    objectName: "sceneLibraryDialog"
    parent: Overlay.overlay
    anchors.centerIn: parent
    width: Math.min(1020, parent.width - 60)
    height: Math.min(700, parent.height - 60)
    padding: 24
    modal: true
    background: Rectangle { radius: 20; color: "#25251c"; border.color: "#65573f" }
    component ActionButton: Button {
        id: action
        implicitHeight: 38; leftPadding: 14; rightPadding: 14
        contentItem: LocalizedLabel { sourceText: action.text; color: action.enabled ? "#f3ecd9" : "#777764"; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter; font.pixelSize: 12 }
        background: Rectangle { color: action.hovered ? "#423d2b" : "#353025"; border.color: "#65573f"; radius: 10 }
    }
    contentItem: ColumnLayout {
        spacing: 14
        RowLayout { Layout.fillWidth: true
            LocalizedLabel { sourceText: "场景记录库"; color: "#f3ecd9"; font.pixelSize: 22; font.bold: true; Layout.fillWidth: true }
            ActionButton { text: "关闭"; onClicked: dialog.close() }
        }
        LocalizedLabel { sourceText: "记录与输出分开：自动收集不会启用 Pulse。启用循环后，剧情和回想都会按现有 A/B 策略响应。"; color: "#e6be73"; wrapMode: Text.WordWrap; Layout.fillWidth: true }
        RowLayout { Layout.fillWidth: true; spacing: 12
            ActionButton { objectName: "recordCurrentSceneDialogButton"; text: "记录当前场景"; enabled: dialog.controller.currentSceneId !== ""; onClicked: dialog.controller.recordCurrentScene() }
            ActionButton { objectName: "autoCaptureScenesButton"; text: dialog.controller.sceneCaptureEnabled ? "停止自动收集" : "开启自动收集"; onClicked: dialog.controller.setSceneCaptureEnabled(!dialog.controller.sceneCaptureEnabled) }
            ActionButton { objectName:"registerCollectedScenesButton"; text: "登记 34 个场景"; onClicked: enableConfirmation.ask("登记这 34 个场景？", "将已收集的 34 个场景加入当前进程白名单并保存。当前场景在有效采样后即可循环，不改变强度、波形或暂停状态。", function() { dialog.controller.registerCollectedScenes() }, "确认登记") }
            Item { Layout.fillWidth: true }
            LocalizedLabel { objectName:"sceneRegistrationCount"; sourceText: "记录 " + dialog.controller.sceneLibrary.length + " · 白名单 " + dialog.controller.registeredSceneCount; color: "#8fbd83" }
        }
        LocalizedLabel { sourceText: "当前：" + (dialog.controller.currentSceneId || "尚无有效场景"); color: "#aaa68d"; elide: Text.ElideMiddle; Layout.fillWidth: true }
        ListView {
            objectName: "sceneLibraryList"
            Layout.fillWidth: true; Layout.fillHeight: true
            clip: true; spacing: 10
            model: dialog.controller.sceneLibrary
            ScrollBar.vertical: ScrollBar {}
            LocalizedLabel { anchors.centerIn: parent; visible: dialog.controller.sceneLibrary.length === 0; sourceText: "进入剧情后点击记录，或开启自动收集再逐个切换场景。"; color: "#aaa68d" }
            delegate: Rectangle {
                id: row
                required property var modelData
                width: ListView.view.width - 16; height: 130; radius: 12
                color: "#18241b"; border.color: "#574a36"
                ColumnLayout { anchors.fill: parent; anchors.margins: 14; spacing: 8
                    RowLayout { Layout.fillWidth: true
                        LocalizedLabel { translateEnabled: false; sourceText: row.modelData.id; color: "#f3ecd9"; font.bold: true; Layout.fillWidth: true; elide: Text.ElideMiddle }
                        ActionButton { objectName: "sceneLoopToggle_" + row.modelData.id; text: row.modelData.enabled ? "停用循环" : "启用循环"; onClicked: {
                            if (row.modelData.enabled) dialog.controller.setSceneLoopEnabled(row.modelData.id, false)
                            else enableConfirmation.ask("启用这个场景的循环？", row.modelData.id + "\n进入剧情或回想后将自动循环 Pulse，沿用现有通道强度、波形与硬上限。记录本身不代表已实机验证，请先核对设置。", function() { dialog.controller.setSceneLoopEnabled(row.modelData.id, true) }, "确认启用")
                        } }
                    }
                    RowLayout { Layout.fillWidth: true
                        TextField { id: note; Layout.fillWidth: true; text: row.modelData.note; placeholderText: backend.localize("备注，例如：Goblin 对话 / 城堡", backend.language); maximumLength: 160; color: "#f3ecd9"; padding: 9; background: Rectangle { color: "#111a14"; radius: 8; border.color: "#574a36" } }
                        ActionButton { text: "保存备注"; onClicked: dialog.controller.saveSceneNote(row.modelData.id, note.text) }
                    }
                    LocalizedLabel { sourceText: "最近记录 " + row.modelData.lastSeen + " · " + row.modelData.assetCount + " 个脚本 · " + (row.modelData.enabled ? "循环已启用" : "仅记录"); color: "#aaa68d"; font.pixelSize: 10 }
                }
            }
        }
        RowLayout { Layout.fillWidth: true
            LocalizedLabel { translateEnabled: false; sourceText: dialog.controller.sceneLibraryPath; color: "#aaa68d"; font.pixelSize: 10; Layout.fillWidth: true; elide: Text.ElideMiddle }
            ActionButton { text: "打开记录目录"; onClicked: dialog.controller.openSceneLibraryFolder() }
        }
        LocalizedLabel { sourceText: "scenes.json 可备份 / 分享；只保存 ID、脚本路径、cut 和备注，不采集对白、音频或设备配对信息。自动收集每次启动默认关闭。"; color: "#aaa68d"; font.pixelSize: 10; Layout.fillWidth: true; wrapMode: Text.WordWrap }
    }
    ConfirmResetDialog { id: enableConfirmation; objectName: "sceneLoopEnableConfirmation" }
}
