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
        {page:1, title:"设备与游戏：连接 DG-LAB", body:"在“设备与游戏”选择手机可访问的局域网 IPv4，用 DG-LAB 3.0 App 的 Socket 模式扫码。", hint:"保存安全硬上限后，连接成功即按有效游戏状态自动输出，无需测试 A/B 或单独启用。右上角可暂停或紧急归零；连接不上可查看诊断。"},
        {page:2, title:"个性化范围：快速设置强度", body:"“个性化范围”提供低、中、高方案，低强度、中强度、高强度和死亡惩罚也能分别调整。", hint:"各方案包含强度与上限，请核对后再“应用并保存”。实际输出始终受已保存的安全硬上限约束。"},
        {page:3, title:"波形工作台：调整更多细节", body:"在“波形工作台”打开 A / B 通道策略，分别选择 HP、动作、两者结合、剧情音频或关闭。", hint:"每类事件可设置强度、波形和开关，并预览波形。挣扎中持续至挣脱，不按秒计时。剧情音频还需在“音频共感”单独开启。"},
        {page:2, title:"全局急停：直接录入按键", body:"默认 Ctrl+F12。点击“录入按键”后直接按键，也支持 Pause、F10 等单键；不需要打字。", hint:"游戏在前台也可暂停并归零全部输出，再按不会恢复。录入或保存时先急停，完成后需手动恢复；单键请避开游戏操作键。"},
        {page:2, title:"最后一步：手动设置安全硬上限", body:"请输入安全硬上限（0–100 的整数）。保存应用后，已连接的设备将按有效游戏状态自动输出；手动暂停或紧急归零不会自动解除。", hint:"0 表示禁用所有设备输出。硬上限仅限制数值，不保证体感安全，请从低值开始。超过上限的档位会下调；以后可在“个性化范围”修改。"}
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
