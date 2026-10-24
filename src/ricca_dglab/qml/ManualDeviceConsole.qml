pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import QtQuick.Controls.Basic as Basic
import QtQuick.Layouts

Rectangle {
    id:panel
    required property var controller
    property bool vibration:false
    property var catalog:[]
    readonly property string device:vibration ? "ovc" : "coyote"
    readonly property color accent:"#e6cb7b"
    readonly property int step:vibration ? 10 : 1
    readonly property bool compact:height<620
    readonly property int maximum:vibration ? Math.floor(controller.hardCap/10)*10 : controller.hardCap
    readonly property var state:backend.manualOutputs ? backend.manualOutputs[device] || ({}) : ({})
    property int strengthA:0
    property int strengthB:0
    property int seconds:30
    property string selectedChannel:"A"
    property string waveA:catalog.length ? catalog[0].key : ""
    property string waveB:catalog.length ? catalog[0].key : ""
    readonly property var reasons:({"manual-running":"手动播放中","manual-stopped":"已停止，需手动再次开始","manual-idle":"等待手动开始","manual-timeout":"定时结束，已归零","manual-device-lost":"设备断开或未就绪，已停止","manual-route-paused":"当前设备已暂停","emergency-stop":"紧急停止","manual-wave-missing":"波形不可用，已停止","manual-device-changed":"设备已更换，需重新开始"})
    implicitHeight:650;implicitWidth:460
    radius:18;color:"#25251c";border.color:state.running ? accent : "#65573f";border.width:state.running ? 2 : 1
    function setStrength(letter,value){value=Math.max(0,Math.min(maximum,Math.floor(value/step)*step));if(letter==="A")strengthA=value;else strengthB=value}
    function waveName(key){for(var i=0;i<catalog.length;i++)if(catalog[i].key===key)return catalog[i].name;return "待机"}
    function chooseWave(key){if(selectedChannel==="A")waveA=key;else waveB=key}
    component Label:LocalizedLabel {color:"#f3ecd9";font.pixelSize:12;wrapMode:Text.WordWrap}
    component Action:Basic.Button {
        id:button
        property bool primary:false
        property real labelSize:12
        implicitHeight:40;leftPadding:13;rightPadding:13
        contentItem:Label {sourceText:button.text;font.pixelSize:button.labelSize;color:button.primary ? "#242418" : panel.accent;opacity:button.enabled ? 1 : .45;horizontalAlignment:Text.AlignHCenter;verticalAlignment:Text.AlignVCenter;wrapMode:Text.NoWrap}
        background:Rectangle {radius:10;color:button.primary ? panel.accent : button.hovered ? "#453e2d" : "#303025";border.color:button.primary ? panel.accent : "#5c543b";opacity:button.enabled ? 1 : .45}
    }
    component Channel:Rectangle {
        id:channel
        required property string letter
        readonly property int strength:letter==="A" ? panel.strengthA : panel.strengthB
        readonly property string wave:letter==="A" ? panel.waveA : panel.waveB
        Layout.fillWidth:true;Layout.preferredWidth:1;implicitHeight:panel.compact ? 164 : 206;radius:12;color:"#19211b"
        border.color:panel.selectedChannel===letter ? panel.accent : "#4b4937"
        ColumnLayout {
            anchors.fill:parent;anchors.margins:12;spacing:8
            Action {objectName:"manualWave"+channel.letter;Layout.fillWidth:true;Layout.preferredHeight:panel.compact ? 32 : 40;text:channel.letter+" · "+panel.waveName(channel.wave);primary:panel.selectedChannel===channel.letter;onClicked:panel.selectedChannel=channel.letter}
            RowLayout {
                Layout.fillWidth:true;Layout.fillHeight:true;spacing:8
                Basic.Slider {
                    id:level
                    objectName:"manualStrength"+channel.letter
                    orientation:Qt.Vertical;Layout.preferredWidth:22;Layout.fillHeight:true
                    from:0;to:panel.maximum;stepSize:panel.step;snapMode:Slider.SnapAlways;value:channel.strength
                    onMoved:panel.setStrength(channel.letter,Math.round(value))
                    background:Rectangle {width:5;height:level.availableHeight;x:level.leftPadding+(level.availableWidth-width)/2;y:level.topPadding;radius:3;color:"#3b4231"
                        Rectangle {anchors.bottom:parent.bottom;width:parent.width;height:parent.height*(1-level.visualPosition);radius:3;color:panel.accent}}
                    handle:Rectangle {width:17;height:8;radius:3;color:panel.accent;x:level.leftPadding+(level.availableWidth-width)/2;y:level.topPadding+level.visualPosition*(level.availableHeight-height)}
                }
                ColumnLayout {Layout.fillWidth:true;spacing:0
                    Label {objectName:"manualValue"+channel.letter;Layout.fillWidth:true;sourceText:channel.strength;font.pixelSize:panel.compact ? 32 : 36;color:panel.accent;horizontalAlignment:Text.AlignHCenter}
                    Label {Layout.fillWidth:true;sourceText:"上限 "+panel.maximum;color:"#aaa68d";font.pixelSize:11;horizontalAlignment:Text.AlignHCenter}
                }
            }
            RowLayout {Layout.fillWidth:true;spacing:10
                Action {objectName:"manualDecrease"+channel.letter;Layout.fillWidth:true;Layout.preferredWidth:1;Layout.preferredHeight:panel.compact ? 34 : 40;text:"−";labelSize:24;onClicked:panel.setStrength(channel.letter,channel.strength-panel.step)}
                Action {objectName:"manualIncrease"+channel.letter;Layout.fillWidth:true;Layout.preferredWidth:1;Layout.preferredHeight:panel.compact ? 34 : 40;text:"+";labelSize:24;onClicked:panel.setStrength(channel.letter,channel.strength+panel.step)}
            }
        }
    }
    ColumnLayout {
        anchors.fill:parent;anchors.margins:18;spacing:10
        RowLayout {Layout.fillWidth:true;spacing:8
            Rectangle {width:7;height:7;radius:4;color:(panel.vibration ? backend.ovcConnected : backend.deviceConnected) ? "#8fbd83" : "#77705c"}
            Label {Layout.fillWidth:true;Layout.minimumWidth:0;sourceText:panel.vibration ? "负鼠振动" : "郊狼 Pulse";font.pixelSize:17;font.bold:true;elide:Text.ElideRight;wrapMode:Text.NoWrap}
            Action {objectName:"enterManualModeButton";visible:!panel.state.enabled;text:"进入手动模式";labelSize:11;onClicked:backend.setManualMode(panel.device,true)}
            Action {objectName:"exitManualModeButton";visible:panel.state.enabled;text:"返回自动模式";labelSize:11;onClicked:confirmation.ask("返回自动模式？","当前设备先归零并保持暂停；需要在设备页手动启用后才恢复游戏同步。",function(){backend.setManualMode(panel.device,false)},"确认切换")}
        }
        Label {objectName:"manualModeStatus";Layout.fillWidth:true;sourceText:!panel.state.enabled ? "自动模式" : panel.state.blocker || panel.reasons[panel.state.reason] || "等待手动开始";color:panel.state.running ? "#8fbd83" : "#e6be73";font.pixelSize:11;maximumLineCount:2;elide:Text.ElideRight}
        Rectangle {Layout.fillWidth:true;height:1;color:"#4b4937"}
        ScrollView {
            id:bodyScroll
            objectName:"manualBodyScroll";Layout.fillWidth:true;Layout.fillHeight:true;clip:true;contentWidth:availableWidth
            ScrollBar.horizontal.policy:ScrollBar.AlwaysOff
            ColumnLayout {
                width:bodyScroll.availableWidth;spacing:panel.compact ? 8 : 12
                RowLayout {Layout.fillWidth:true;spacing:12;Channel {letter:"A"} Channel {letter:"B"}}
                Label {Layout.fillWidth:true;sourceText:"草稿：点击播放后生效，0 表示关闭通道。";color:"#aaa68d";font.pixelSize:11}
                RowLayout {Layout.fillWidth:true;spacing:8
                    Action {objectName:"manualSelectChannelA";Layout.fillWidth:true;Layout.preferredWidth:1;Layout.preferredHeight:panel.compact ? 34 : 40;text:"A 通道";primary:panel.selectedChannel==="A";onClicked:panel.selectedChannel="A"}
                    Action {objectName:"manualSelectChannelB";Layout.fillWidth:true;Layout.preferredWidth:1;Layout.preferredHeight:panel.compact ? 34 : 40;text:"B 通道";primary:panel.selectedChannel==="B";onClicked:panel.selectedChannel="B"}
                }
                Label {sourceText:panel.selectedChannel==="A" ? "为 A 通道选择波形" : "为 B 通道选择波形";font.bold:true;color:panel.accent;Layout.fillWidth:true}
                GridLayout {
                    id:waveGrid
                    objectName:"manualWaveGrid";Layout.fillWidth:true;columns:panel.width>=560 ? 4 : 3;columnSpacing:9;rowSpacing:9
                    Repeater {
                        model:panel.catalog
                        delegate:Basic.Button {
                            id:tile
                            required property var modelData
                            objectName:"manualWaveTile_"+modelData.key
                            readonly property bool selected:(panel.selectedChannel==="A" ? panel.waveA : panel.waveB)===modelData.key
                            readonly property bool official:String(modelData.source || "").indexOf("官方")>=0 || String(modelData.source || "").toLowerCase().indexOf("official")>=0
                            Layout.fillWidth:true;Layout.preferredWidth:1;implicitHeight:panel.compact ? 84 : 94;padding:9
                            onClicked:panel.chooseWave(modelData.key)
                            background:Rectangle {radius:11;color:tile.selected ? panel.accent : tile.hovered ? "#3b3929" : "#1c241c";border.color:tile.selected ? "#f1dda0" : "#4b4937";border.width:tile.selected ? 2 : 1}
                            contentItem:ColumnLayout {
                                spacing:4
                                Label {Layout.fillWidth:true;sourceText:tile.official ? "官方波形" : panel.vibration ? "振动波形" : "波形";color:tile.selected ? "#504828" : "#aaa68d";font.pixelSize:9;elide:Text.ElideRight;wrapMode:Text.NoWrap}
                                Canvas {
                                    id:graph
                                    Layout.fillWidth:true;Layout.fillHeight:true
                                    property var points:tile.modelData.points || []
                                    property bool chosen:tile.selected
                                    onPointsChanged:requestPaint()
                                    onChosenChanged:requestPaint()
                                    onWidthChanged:requestPaint()
                                    onHeightChanged:requestPaint()
                                    onPaint:{var ctx=getContext("2d");ctx.reset();if(points.length<2)return;ctx.strokeStyle=chosen ? "#303325" : "#d6c98e";ctx.lineWidth=2;ctx.lineJoin="round";ctx.beginPath();for(var i=0;i<points.length;i++){var x=i*width/(points.length-1),y=height-2-Math.max(0,Math.min(100,Number(points[i])))*(height-4)/100;if(i===0)ctx.moveTo(x,y);else ctx.lineTo(x,y)}ctx.stroke()}
                                }
                                Label {Layout.fillWidth:true;sourceText:tile.modelData.name;color:tile.selected ? "#242418" : "#f3ecd9";font.pixelSize:11;font.bold:tile.selected;horizontalAlignment:Text.AlignHCenter;elide:Text.ElideRight;wrapMode:Text.NoWrap}
                            }
                        }
                    }
                }
                RowLayout {Layout.fillWidth:true;spacing:10
                    Label {sourceText:"播放时长";Layout.preferredWidth:75}
                    Basic.Slider {objectName:"manualDurationSlider";Layout.fillWidth:true;from:1;to:300;stepSize:1;snapMode:Slider.SnapAlways;value:panel.seconds;onMoved:panel.seconds=Math.round(value)}
                    Label {sourceText:panel.seconds+" 秒";Layout.preferredWidth:48;horizontalAlignment:Text.AlignRight;color:panel.accent}
                }
                Label {Layout.fillWidth:true;sourceText:panel.vibration ? "负鼠使用振动波形，按 10 向下取整；最终发送仍受 App 通道上限约束。" : "郊狼沿用电刺激波形及已有硬上限；手动强度不叠加破甲倍率。";color:"#aaa68d";font.pixelSize:10}
            }
        }
        Rectangle {Layout.fillWidth:true;height:1;color:"#4b4937"}
        Label {Layout.fillWidth:true;sourceText:panel.state.running ? "剩余 "+panel.state.remaining+" 秒" : panel.state.blocker || "每次最多 5 分钟，到时归零。断连、暂停或急停会结束本次播放，恢复后需重新点击开始。";color:panel.state.running ? panel.accent : "#aaa68d";font.pixelSize:10;maximumLineCount:2;elide:Text.ElideRight}
        RowLayout {Layout.fillWidth:true;spacing:10
            Action {objectName:"stopManualOutputButton";text:"■  停止并归零";Layout.fillWidth:true;Layout.preferredWidth:1;enabled:panel.state.enabled;onClicked:backend.stopManualOutput(panel.device)}
            Action {objectName:"startManualOutputButton";text:panel.state.running ? "重新应用并开始" : "▶  开始手动播放";primary:true;Layout.fillWidth:true;Layout.preferredWidth:1;enabled:!!panel.state.can_start && (panel.strengthA>0 || panel.strengthB>0);onClicked:backend.startManualOutput(panel.device,panel.strengthA,panel.waveA,panel.strengthB,panel.waveB,panel.seconds)}
        }
    }
    ConfirmResetDialog {id:confirmation}
}
