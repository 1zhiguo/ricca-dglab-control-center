pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import QtQuick.Controls.Basic as Basic
import QtQuick.Layouts

Dialog {
    id: dialog
    objectName: "hudSettingsDialog"
    parent: Overlay.overlay; anchors.centerIn:parent
    width:Math.min(760,parent.width-48);height:Math.min(700,parent.height-40)
    padding:24;modal:true;closePolicy:Popup.CloseOnEscape
    property var draft: ({scale:100,opacity:80,anchor:"auto",x:50,y:92,show_pulse:true,show_ovc:true,show_a:true,show_b:true,show_numbers:true,show_waveforms:true,show_status:true})
    readonly property var positions: [
        {key:"auto",name:backend.localize("自动：战斗靠下，剧情靠上",backend.language)},
        {key:"top_left",name:backend.localize("左上",backend.language)},
        {key:"top_center",name:backend.localize("顶部居中",backend.language)},
        {key:"top_right",name:backend.localize("右上",backend.language)},
        {key:"bottom_left",name:backend.localize("左下",backend.language)},
        {key:"bottom_center",name:backend.localize("底部居中",backend.language)},
        {key:"bottom_right",name:backend.localize("右下",backend.language)},
        {key:"custom",name:backend.localize("自定义位置",backend.language)}]
    function openSettings(){draft=JSON.parse(JSON.stringify(backend.hudSettings));open()}
    function setOption(key,value){var copy=JSON.parse(JSON.stringify(draft));copy[key]=value;draft=copy}
    function positionIndex(){for(var i=0;i<positions.length;i++)if(positions[i].key===draft.anchor)return i;return 0}
    background:Rectangle {color:"#25251c";radius:20;border.color:"#65573f"}
    component Label:LocalizedLabel {color:"#f3ecd9";font.pixelSize:12;wrapMode:Text.WordWrap}
    component Action:Basic.Button {
        id:button
        property bool primary:false
        implicitHeight:42;leftPadding:18;rightPadding:18
        contentItem:Label {sourceText:button.text;color:button.primary ? "#172118" : "#f3ecd9";horizontalAlignment:Text.AlignHCenter;verticalAlignment:Text.AlignVCenter}
        background:Rectangle {radius:11;color:button.primary ? "#8fbd83" : "#353025";border.color:"#65573f";opacity:button.enabled ? 1 : .45}
    }
    component Option:Basic.CheckBox {
        id:option
        required property string optionKey
        required property string label
        checked:!!dialog.draft[optionKey]
        onClicked:dialog.setOption(optionKey,checked)
        spacing:10;leftPadding:0
        indicator:Rectangle {x:0;y:(option.height-height)/2;width:18;height:18;radius:4;color:option.checked ? "#8fbd83" : "#17231c";border.color:"#8a855e"
            Text {anchors.centerIn:parent;text:option.checked ? "✓" : "";color:"#172118";font.pixelSize:14}}
        contentItem:Label {sourceText:option.label;leftPadding:28;verticalAlignment:Text.AlignVCenter}
    }
    component SettingSlider:RowLayout {
        id:row
        required property string optionKey
        required property string label
        property real minimum:0
        property real maximum:100
        property real step:1
        Layout.fillWidth:true
        Label {sourceText:row.label;Layout.preferredWidth:130}
        Basic.Slider {
            id:slider
            objectName:"hudSetting_"+row.optionKey
            from:row.minimum;to:row.maximum;stepSize:row.step;snapMode:Slider.SnapAlways
            value:Number(dialog.draft[row.optionKey] || 0);Layout.fillWidth:true
            onMoved:dialog.setOption(row.optionKey,Math.round(value))
            background:Rectangle {x:slider.leftPadding;y:slider.topPadding+slider.availableHeight/2-2;width:slider.availableWidth;height:4;radius:2;color:"#574a36"
                Rectangle {width:parent.width*slider.visualPosition;height:4;radius:2;color:"#8fbd83"}}
            handle:Rectangle {width:16;height:22;radius:5;color:"#8fbd83";x:slider.leftPadding+slider.visualPosition*(slider.availableWidth-width);y:slider.topPadding+(slider.availableHeight-height)/2}
        }
        Label {sourceText:(dialog.draft[row.optionKey] || 0)+"%";Layout.preferredWidth:48;horizontalAlignment:Text.AlignRight}
    }
    contentItem:ColumnLayout {
        spacing:14
        RowLayout {Layout.fillWidth:true
            Label {sourceText:"HUD 显示设置";font.pixelSize:23;font.bold:true;Layout.fillWidth:true}
            Action {text:"关闭";onClicked:dialog.close()}
        }
        ScrollView {
            Layout.fillWidth:true;Layout.fillHeight:true;clip:true;contentWidth:availableWidth
            ColumnLayout {
                width:parent.width;spacing:14
                Label {sourceText:"示例预览（不会发送输出）";color:"#b7ad91";Layout.fillWidth:true}
                Rectangle {
                    Layout.fillWidth:true;Layout.preferredHeight:100;color:"#12231f";radius:12;border.color:"#4d604d"
                    HudPanel {
                        anchors.centerIn:parent
                        width:Math.min(parent.width-20,600*Number(dialog.draft.scale || 100)/100)
                        height:Math.min(84,68*Number(dialog.draft.scale || 100)/100)
                        options:dialog.draft
                        readings:({pulseA:{strength:18,bars:3,status:"同步",live:true},pulseB:{strength:24,bars:4,status:"同步",live:true},ovcA:{strength:80,bars:2,status:"同步",live:true},ovcB:{strength:160,bars:4,status:"同步",live:true}})
                        historyA:[0,.2,.5,.9,.3,0,.4,.7,.1,0]
                        historyB:[0,.8,.1,.6,.2,0,.9,.3,.6,0]
                    }
                }
                SettingSlider {optionKey:"scale";label:"HUD 大小";minimum:60;maximum:180;step:10}
                SettingSlider {optionKey:"opacity";label:"背景不透明度";minimum:20;maximum:100;step:5}
                RowLayout {Layout.fillWidth:true
                    Label {sourceText:"显示位置";Layout.preferredWidth:130}
                    Basic.ComboBox {
                        id:position
                        objectName:"hudPositionChoice";Layout.fillWidth:true;implicitHeight:40
                        model:dialog.positions;textRole:"name";currentIndex:dialog.positionIndex()
                        onActivated:dialog.setOption("anchor",dialog.positions[currentIndex].key)
                        contentItem:Text {text:position.currentText;color:"#f3ecd9";font.family:backend.uiFontFamily;verticalAlignment:Text.AlignVCenter;leftPadding:12}
                        background:Rectangle {radius:10;color:"#353025";border.color:"#65573f"}
                    }
                }
                SettingSlider {visible:dialog.draft.anchor==="custom";optionKey:"x";label:"水平位置"}
                SettingSlider {visible:dialog.draft.anchor==="custom";optionKey:"y";label:"垂直位置"}
                Label {sourceText:"显示内容";font.bold:true;Layout.fillWidth:true}
                GridLayout {
                    Layout.fillWidth:true;columns:2;columnSpacing:24;rowSpacing:4
                    Option {objectName:"hudShowPulse";optionKey:"show_pulse";label:"郊狼 Pulse";Layout.fillWidth:true}
                    Option {objectName:"hudShowOvc";optionKey:"show_ovc";label:"负鼠振动";Layout.fillWidth:true}
                    Option {optionKey:"show_a";label:"A 通道";Layout.fillWidth:true}
                    Option {optionKey:"show_b";label:"B 通道";Layout.fillWidth:true}
                    Option {optionKey:"show_numbers";label:"数字强度";Layout.fillWidth:true}
                    Option {optionKey:"show_status";label:"连接与输出状态";Layout.fillWidth:true}
                    Option {optionKey:"show_waveforms";label:"郊狼波形";Layout.fillWidth:true}
                }
                Label {sourceText:"五格按当前设备硬上限显示比例；数字为插件发送强度，并非设备实测。";color:"#b7ad91";font.pixelSize:11;Layout.fillWidth:true}
                Label {visible:!(dialog.draft.show_pulse || dialog.draft.show_ovc) || !(dialog.draft.show_a || dialog.draft.show_b);sourceText:"至少显示一种设备和一个通道。";color:"#ff7e88";Layout.fillWidth:true}
                Label {sourceText:"HUD 支持窗口和无边框全屏；独占全屏可能遮挡桌面悬浮窗。HUD 隐藏不代表设备停止输出。";color:"#b7ad91";font.pixelSize:11;Layout.fillWidth:true}
            }
        }
        RowLayout {
            Layout.fillWidth:true
            Action {text:"恢复默认";onClicked:confirmation.ask("恢复 HUD 默认设置？","只修改 HUD 显示，不影响设备强度、波形或输出状态。",function(){dialog.draft={scale:100,opacity:80,anchor:"auto",x:50,y:92,show_pulse:true,show_ovc:true,show_a:true,show_b:true,show_numbers:true,show_waveforms:true,show_status:true}})}
            Item {Layout.fillWidth:true}
            Action {text:"取消";onClicked:dialog.close()}
            Action {objectName:"saveHudSettingsButton";primary:true;text:"应用并保存";enabled:(dialog.draft.show_pulse || dialog.draft.show_ovc) && (dialog.draft.show_a || dialog.draft.show_b);onClicked:if(backend.saveHudSettings(dialog.draft))dialog.close()}
        }
    }
    ConfirmResetDialog {id:confirmation}
}
