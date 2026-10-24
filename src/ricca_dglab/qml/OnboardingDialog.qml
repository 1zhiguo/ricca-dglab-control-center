import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Dialog {
    id: guide
    objectName: "onboardingDialog"
    required property var controller
    signal navigateRequested(int page)
    property int step: 0
    readonly property var steps: [
        {page:0, title:"实时总览：先核对游戏状态", body:"左侧“实时总览”显示 HP、动作、护甲，以及捕获状态和挣扎进度。", hint:"A / B 面板可核对波形与强度。死亡惩罚优先于普通暂停，右上角会明确显示；请用“紧急归零”停止全部输出。"},
        {page:1, title:"设备与游戏：连接 DG-LAB", body:"打开游戏后自动检测；选择 V3 或 V4，用 DG-LAB App 扫码，再选择要使用的郊狼和负鼠设备。", hint:"两台设备可同时运行，配置独立。暂停和紧急归零在右上角；连接不上可展开地址详情或打开连接帮助。"},
        {page:2, title:"工作台：先设置强度", body:"郊狼和负鼠工作台布局相同：强度设置、战斗反馈、剧情与鉴赏。先在强度设置中核对档位和硬上限。", hint:"低、中、高、死亡强度和硬上限分别调整；保存后生效。两台设备的数值不通用，不会互相覆盖。"},
        {page:3, title:"战斗与剧情：按事件调整", body:"战斗反馈先选择 A 或 B，再查看每个事件的强度、波形和时长；需要修改时点击对应事件。", hint:"剧情与鉴赏中设置固定波形、循环队列或音频调节。音频来源在“音频共感”开启；捕获反馈持续到挣脱，不按秒计时。"},
        {page:2, title:"全局急停：直接录入按键", body:"默认 Ctrl+F12。点击“录入按键”后直接按键，也支持 Pause、F10 等单键；不需要打字。", hint:"游戏在前台也可暂停并归零全部输出，再按不会恢复。录入或保存时先急停，完成后需手动恢复；单键请避开游戏操作键。"},
        {page:2, title:"最后一步：手动设置安全硬上限", body:"请输入郊狼安全硬上限（0–100 的整数），保存后应用。手动暂停和紧急归零不会自动解除；负鼠上限在负鼠工作台单独设置。", hint:"0 禁用郊狼输出。硬上限仅限制数值，不保证物理安全，请从低值开始。超过上限的档位会下调，以后可在郊狼工作台修改。"}
    ]
    readonly property bool lastStep: step === steps.length - 1
    readonly property bool hotkeyStep: step === steps.length - 2
    parent: Overlay.overlay
    anchors.centerIn: parent
    width: Math.min(640, parent.width - 64)
    height: Math.min(530, parent.height - 48)
    padding: 24
    modal: true
    closePolicy: Popup.NoAutoClose
    background: Rectangle { color: "#25251c"; radius: 20; border.color: "#65573f" }

    function openGuide() {
        controller.beginOnboarding()
        step = 0
        capInput.text = ""
        hotkeyRecorder.chord = controller.emergencyHotkey
        hotkeyRecorder.cancelRecording()
        navigateRequested(steps[0].page)
        open()
    }
    onStepChanged: {
        hotkeyRecorder.cancelRecording()
        navigateRequested(steps[step].page)
        if (lastStep) capInput.forceActiveFocus()
    }
    onClosed: hotkeyRecorder.cancelRecording()
    component ActionButton: Button {
        id: button
        implicitHeight: 42; leftPadding: 18; rightPadding: 18
        property bool primary: false
        contentItem: LocalizedLabel { sourceText: button.text; color: button.enabled ? button.primary ? "#162214" : "#f3ecd9" : "#89856c"; font.family: backend.uiFontFamily; font.pixelSize: 12; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter }
        background: Rectangle { radius: 11; color: button.enabled && button.primary ? "#8fbd83" : "#353025"; border.color: "#65573f" }
    }
    contentItem: ColumnLayout {
        spacing: 16
        RowLayout { Layout.fillWidth: true
            LocalizedLabel { sourceText:"新手教程 · " + (guide.step + 1) + " / " + guide.steps.length; color:"#8fbd83"; font.pixelSize:13; Layout.fillWidth:true }
            ActionButton { visible: guide.controller.onboardingCompleted; text:"关闭教程"; onClicked: guide.close() }
        }
        RowLayout { Layout.fillWidth: true; spacing: 8
            Repeater { model: guide.steps.length
                Rectangle { required property int index; Layout.fillWidth:true; height:4; radius:2; color:index <= guide.step ? "#8fbd83" : "#443e2e" }
            }
        }
        LocalizedLabel { Layout.fillWidth:true; sourceText:guide.steps[guide.step].title; font.family:backend.uiFontFamily; font.pixelSize:23; font.bold:true; color:"#f3ecd9"; wrapMode:Text.WordWrap }
        LocalizedLabel { Layout.fillWidth:true; sourceText:guide.steps[guide.step].body; font.family:backend.uiFontFamily; font.pixelSize:14; lineHeight:1.3; color:"#ded7c0"; wrapMode:Text.WordWrap }
        HotkeyRecorder { id:hotkeyRecorder; objectName:"onboardingHotkeyRecorder"; visible:guide.hotkeyStep; Layout.fillWidth:true; controller:guide.controller }
        Rectangle {
            visible: guide.lastStep; Layout.fillWidth:true; Layout.preferredHeight:94; color:"#101b13"; radius:12; border.color:"#65573f"
            RowLayout { anchors.fill:parent; anchors.margins:16; spacing:16
                ColumnLayout { Layout.fillWidth:true; spacing:5
                    LocalizedLabel { sourceText:"安全硬上限"; color:"#e6be73"; font.pixelSize:15; font.bold:true }
                    LocalizedLabel { sourceText:"请输入整数，留空不能完成"; color:"#aaa68d"; font.pixelSize:11 }
                }
                TextField {
                    id:capInput; objectName:"onboardingCapInput"
                    Layout.preferredWidth:130; Layout.preferredHeight:50
                    placeholderText:"0–100"; color:"#f3ecd9"; placeholderTextColor:"#89856c"
                    font.pixelSize:22; horizontalAlignment:Text.AlignHCenter
                    inputMethodHints:Qt.ImhDigitsOnly
                    validator:IntValidator { bottom:0; top:100 }
                    background:Rectangle { radius:10; color:"#353025"; border.color:capInput.activeFocus ? "#8fbd83" : "#65573f" }
                }
            }
        }
        LocalizedLabel { Layout.fillWidth:true; sourceText:guide.steps[guide.step].hint; color:guide.lastStep ? "#e6be73" : "#aaa68d"; font.family:backend.uiFontFamily; font.pixelSize:12; lineHeight:1.2; wrapMode:Text.WordWrap }
        LocalizedLabel { visible:guide.lastStep && guide.controller.onboardingError !== ""; Layout.fillWidth:true; sourceText:guide.controller.onboardingError; color:"#ff5d7a"; wrapMode:Text.WordWrap }
        Item { Layout.fillHeight:true }
        RowLayout { Layout.fillWidth:true
            ActionButton { objectName:"onboardingBack"; text:"上一步"; enabled:guide.step > 0; onClicked:--guide.step }
            Item { Layout.fillWidth:true }
            ActionButton {
                objectName:"onboardingNext"; primary:true
                text:guide.lastStep ? "保存并应用" : "下一步"
                enabled:(!guide.lastStep || (capInput.text.trim() !== "" && capInput.acceptableInput)) && (!guide.hotkeyStep || !hotkeyRecorder.recording)
                onClicked: {
                    if (guide.hotkeyStep) { if(guide.controller.saveEmergencyHotkey(hotkeyRecorder.chord)) ++guide.step }
                    else if (!guide.lastStep) ++guide.step
                    else if (guide.controller.completeOnboarding(capInput.text)) guide.close()
                }
            }
        }
    }
}
