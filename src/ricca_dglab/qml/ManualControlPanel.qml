pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import QtQuick.Controls.Basic as Basic
import QtQuick.Layouts

Item {
    id: panel
    required property var controller
    property bool vibration: false
    property var catalog: []
    readonly property string device: vibration ? "ovc" : "coyote"
    readonly property var state: backend.manualOutputs ? backend.manualOutputs[device] || ({}) : ({})
    property int strengthA: 0
    property int strengthB: 0
    property int seconds: 30
    property string waveA: catalog.length ? catalog[0].key : ""
    property string waveB: catalog.length ? catalog[0].key : ""
    readonly property var reasons: ({"manual-running":"手动播放中", "manual-stopped":"已停止，需手动再次开始", "manual-idle":"等待手动开始", "manual-timeout":"定时结束，已归零", "manual-device-lost":"设备断开或未就绪，已停止", "manual-route-paused":"当前设备已暂停", "emergency-stop":"紧急停止", "manual-wave-missing":"波形不可用，已停止", "manual-device-changed":"设备已更换，需重新开始"})
    implicitHeight: body.implicitHeight+36
    component Label: LocalizedLabel { color:"#f3ecd9";font.pixelSize:12;wrapMode:Text.WordWrap }
    component Action: Basic.Button {
        id:button
        property bool primary:false
        implicitHeight:40;leftPadding:16;rightPadding:16
        contentItem:Label { sourceText:button.text;color:button.primary ? "#142017" : "#f3ecd9";opacity:button.enabled ? 1 : .45;horizontalAlignment:Text.AlignHCenter;verticalAlignment:Text.AlignVCenter;wrapMode:Text.NoWrap }
        background:Rectangle { radius:11;color:button.primary ? "#8fbd83" : button.hovered ? "#483e2d" : "#353025";border.color:"#65573f";opacity:button.enabled ? 1 : .55 }
    }
    component Slider: Basic.Slider {
        id:control
        snapMode: panel.vibration ? Basic.Slider.SnapAlways : Basic.Slider.NoSnap
        implicitHeight:30
        background:Rectangle { x:control.leftPadding;y:control.topPadding+(control.availableHeight-height)/2;width:control.availableWidth;height:5;radius:3;color:"#574a36"
            Rectangle { width:parent.width*control.visualPosition;height:5;radius:3;color:"#8fbd83" }
        }
        handle:Rectangle { width:17;height:22;radius:6;x:control.leftPadding+control.visualPosition*(control.availableWidth-width);y:control.topPadding+(control.availableHeight-height)/2;color:"#8fbd83" }
    }
    component Channel: Rectangle {
        id:channel
        required property string letter
        property int strength: letter === "A" ? panel.strengthA : panel.strengthB
        property string wave: letter === "A" ? panel.waveA : panel.waveB
        function waveIndex(){for(var i=0;i<panel.catalog.length;i++)if(panel.catalog[i].key===wave)return i;return 0}
        Layout.fillWidth:true;implicitHeight:126;radius:14;color:"#18241b";border.color:"#574a36"
        ColumnLayout {
            anchors.fill:parent;anchors.margins:16;spacing:10
            RowLayout {
                Layout.fillWidth:true
                Label { sourceText:channel.letter+" 通道";font.bold:true;Layout.preferredWidth:100 }
                Slider { objectName:"manualStrength"+channel.letter;Layout.fillWidth:true;from:0;to:panel.vibration ? Math.floor(panel.controller.hardCap/10)*10 : panel.controller.hardCap;stepSize:panel.vibration ? 10 : 1;value:channel.strength;onMoved:{if(channel.letter==="A")panel.strengthA=Math.round(value);else panel.strengthB=Math.round(value)} }
                Label { sourceText:channel.strength+" / "+panel.controller.hardCap;color:"#8fbd83";Layout.preferredWidth:80;horizontalAlignment:Text.AlignRight }
            }
            RowLayout {
                Layout.fillWidth:true
                Label { sourceText:"波形";Layout.preferredWidth:100 }
                Basic.ComboBox {
                    id:choice
                    objectName:"manualWave"+channel.letter
                    Layout.fillWidth:true;Layout.preferredHeight:38
                    model:panel.catalog;textRole:"name";valueRole:"key";currentIndex:channel.waveIndex()
                    onActivated:{if(channel.letter==="A")panel.waveA=currentValue;else panel.waveB=currentValue}
                    contentItem:Label { sourceText:choice.displayText;leftPadding:12;rightPadding:25;verticalAlignment:Text.AlignVCenter;elide:Text.ElideRight;wrapMode:Text.NoWrap }
                    indicator:Label { sourceText:"⌄";x:choice.width-20;anchors.verticalCenter:parent.verticalCenter;color:"#8fbd83" }
                    background:Rectangle { radius:10;color:"#353025";border.color:"#65573f" }
                    delegate:ItemDelegate { required property int index;width:choice.width;height:40;contentItem:Label { sourceText:choice.textAt(index);verticalAlignment:Text.AlignVCenter } background:Rectangle { color:highlighted ? "#483e2d" : "#25251c" } }
                    popup:Popup { y:choice.height+4;width:choice.width;padding:6;implicitHeight:Math.min(contentItem.implicitHeight+12,240);background:Rectangle { radius:10;color:"#25251c";border.color:"#65573f" } contentItem:ListView { implicitHeight:contentHeight;clip:true;model:choice.popup.visible ? choice.delegateModel : null;ScrollBar.vertical:ScrollBar {} } }
                }
            }
        }
    }
    Rectangle { anchors.fill:parent;radius:14;color:"#25251c";border.color:"#574a36" }
    ColumnLayout {
        id:body
        anchors.left:parent.left;anchors.right:parent.right;anchors.top:parent.top;anchors.margins:18;spacing:14
        Label { Layout.fillWidth:true;sourceText:"不依赖游戏检测。仅接管当前设备，另一台设备保持原模式；不会改写已保存的强度、波形或队列。";color:"#aaa68d" }
        RowLayout {
            Layout.fillWidth:true
            Label { objectName:"manualModeStatus";Layout.fillWidth:true;sourceText:!panel.state.enabled ? "自动模式" : panel.state.blocker || panel.reasons[panel.state.reason] || "等待手动开始";color:panel.state.running ? "#8fbd83" : "#e6be73";font.bold:true }
            Action { objectName:"enterManualModeButton";visible:!panel.state.enabled;text:"进入手动模式";onClicked:backend.setManualMode(panel.device,true) }
            Action { objectName:"exitManualModeButton";visible:panel.state.enabled;text:"返回自动模式";onClicked:confirmation.ask("返回自动模式？","当前设备先归零并保持暂停；需要在设备页手动启用后才恢复游戏同步。",function(){backend.setManualMode(panel.device,false)},"确认切换") }
        }
        Label { Layout.fillWidth:true;sourceText:"修改下方草稿不会立即发送。点击开始或重新应用后生效；0 表示关闭该通道。";color:"#aaa68d";font.pixelSize:11 }
        RowLayout {
            Layout.fillWidth:true
            Label { Layout.fillWidth:true;sourceText:panel.state.running ? "剩余 "+panel.state.remaining+" 秒" : "手动控制保留设备与急停保护，不绕过静音或硬上限。";color:"#aaa68d";font.pixelSize:11 }
            Action { objectName:"stopManualOutputButton";text:"停止并归零";enabled:panel.state.enabled;onClicked:backend.stopManualOutput(panel.device) }
            Action { objectName:"startManualOutputButton";text:panel.state.running ? "重新应用并开始" : "开始手动播放";primary:true;enabled:!!panel.state.can_start && (panel.strengthA>0 || panel.strengthB>0);onClicked:backend.startManualOutput(panel.device,panel.strengthA,panel.waveA,panel.strengthB,panel.waveB,panel.seconds) }
        }
        Channel { letter:"A" }
        Channel { letter:"B" }
        RowLayout {
            Layout.fillWidth:true
            Label { sourceText:"播放时长";Layout.preferredWidth:100 }
            Slider { objectName:"manualDurationSlider";Layout.fillWidth:true;from:1;to:300;stepSize:1;value:panel.seconds;onMoved:panel.seconds=Math.round(value) }
            Label { sourceText:panel.seconds+" 秒";Layout.preferredWidth:80;horizontalAlignment:Text.AlignRight;color:"#8fbd83" }
        }
        Label { Layout.fillWidth:true;sourceText:panel.vibration ? "负鼠使用振动波形，按 10 向下取整；最终发送仍受 App 通道上限约束。" : "郊狼沿用电刺激波形及已有硬上限；手动强度不叠加破甲倍率。";color:"#aaa68d";font.pixelSize:11 }
        Label { Layout.fillWidth:true;sourceText:"每次最多 5 分钟，到时归零。断连、暂停或急停会结束本次播放，恢复后需重新点击开始。";color:"#e6be73";font.pixelSize:11 }
    }
    ConfirmResetDialog { id:confirmation }
}
