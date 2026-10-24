pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Controls.Basic as Basic
import QtQuick.Layouts

Item {
    id: workbench
    objectName: vibration ? "ovcWorkbenchPage" : "pulseWorkbenchPage"
    required property var controller
    property bool vibration: false
    property bool dialogMode: false
    property string section: "strength"
    property string battleChannel: "A"
    property string storyChannel: "A"
    property string battleFilter: "all"
    property bool queueExpanded: false
    property bool audioExpanded: false
    property bool presetsExpanded: false
    property int draftLow: 0
    property int draftMedium: 0
    property int draftHigh: 0
    property int draftDeath: 0
    property int draftCap: 0
    property real draftGain: 1
    property int draftMinimum: 0
    property string savedStrength: ""
    property string savedAudio: ""
    // Backend.changed also carries telemetry. Keep delegate models stable when
    // saved configuration has not changed; no polling timer or output work.
    property var cachedPolicies: ({})
    property var cachedCatalog: []
    property var cachedQueues: ({})
    property string policySnapshot: ""
    property string catalogSnapshot: ""
    property string queueSnapshot: ""
    readonly property string prefix: vibration ? "ovc" : "pulse"
    readonly property color accent: "#8fbd83"
    readonly property bool valid: 0 <= draftLow && draftLow <= draftMedium && draftMedium <= draftHigh && draftHigh <= draftDeath && draftDeath <= draftCap && draftCap <= (vibration ? 200 : 100)
    readonly property bool strengthDirty: savedStrength !== JSON.stringify([draftLow,draftMedium,draftHigh,draftDeath,draftCap])
    readonly property bool audioDirty: savedAudio !== JSON.stringify([draftGain,draftMinimum])
    readonly property bool hasUnsavedQueue: queueEditor.dirty
    readonly property bool hasUnsavedChanges: strengthDirty || audioDirty || hasUnsavedQueue
    readonly property var policy: cachedPolicies[battleChannel] || ({})
    readonly property var storyPolicy: cachedPolicies[storyChannel] || ({})
    signal closeRequested()
    signal waveformLibraryRequested()
    signal audioSourceRequested()
    signal hotkeySettingsRequested()
    signal manualControlRequested()
    implicitWidth: 1040
    implicitHeight: 720

    function loadSaved() {
        draftLow=controller.lowStrength; draftMedium=controller.mediumStrength
        draftHigh=controller.highStrength; draftDeath=controller.deathStrength; draftCap=controller.hardCap
        if(vibration) { draftLow=Math.floor(draftLow/10)*10;draftMedium=Math.floor(draftMedium/10)*10;draftHigh=Math.floor(draftHigh/10)*10;draftDeath=Math.floor(draftDeath/10)*10;draftCap=Math.floor(draftCap/10)*10 }
        savedStrength=JSON.stringify([draftLow,draftMedium,draftHigh,draftDeath,draftCap])
        draftGain=controller.audioGain; draftMinimum=controller.audioQueueMinimum
        if(vibration) draftMinimum=Math.floor(draftMinimum/10)*10
        savedAudio=JSON.stringify([draftGain,draftMinimum])
    }
    function refreshSavedView() {
        var policies=controller.channelPolicies,catalog=controller.waveformCatalog,queues=controller.storyQueues
        var policyText=JSON.stringify(policies),catalogText=JSON.stringify(catalog),queueText=JSON.stringify(queues)
        if(policySnapshot!==policyText) { cachedPolicies=policies;policySnapshot=policyText }
        if(catalogSnapshot!==catalogText) { cachedCatalog=catalog;catalogSnapshot=catalogText }
        if(queueSnapshot!==queueText) { cachedQueues=queues;queueSnapshot=queueText }
    }
    function showSection(name) {
        if(name==="manual"){manualControlRequested();return}
        section=name === "strategy" ? "battle" : name === "queue" ? "story" : name
        if (["strength","battle","story"].indexOf(section)<0) section="strength"
        if(name === "queue") queueExpanded=true
    }
    function openChannel(channel) { battleChannel=channel; section="battle"; editChannel(channel,"battle","all") }
    function editChannel(channel, category, filter) {
        strategy.openChannel(channel);strategy.category=category
        if(category === "battle") strategy.filterBattle(filter || "all")
    }
    function showQueue(channel) {
        section="story"; queueExpanded=true; selectStoryChannel(channel)
    }
    function selectStoryChannel(channel) {
        if(queueEditor.dirty && queueEditor.channel!==channel) {
            confirmation.ask("切换通道并放弃未保存修改？", "当前队列尚未保存。已保存的另一通道队列不会改变。", function(){queueEditor.loadChannel(channel);workbench.storyChannel=channel}, "放弃并切换")
        } else { storyChannel=channel; if(queueEditor.channel!==channel)queueEditor.loadChannel(channel) }
    }
    function requestClose() {
        if(hasUnsavedChanges) confirmation.ask("放弃未保存的修改？", "只放弃当前未保存的修改，不恢复出厂值。", function(){workbench.loadSaved();queueEditor.loadChannel(queueEditor.channel);workbench.closeRequested()}, "放弃并关闭")
        else closeRequested()
    }
    function wave(key) {
        var catalog=cachedCatalog
        for(var i=0;i<catalog.length;i++)if(catalog[i].key===key)return catalog[i]
        return {name:key || "待机",points:[],color:accent}
    }
    function effective(value, cap) { return Math.floor(Math.max(0,Math.min(Number(value),cap===undefined ? draftCap : cap))/10)*10 }
    function fillPreset(values) { draftLow=values[0];draftMedium=values[1];draftHigh=values[2];draftDeath=values[3];draftCap=values[4] }
    function strength(rule) { return !rule ? 0 : rule.custom_strength==null ? Number(controller[rule.tier+"Strength"]) : Number(rule.custom_strength) }
    function tier(rule) { return rule.custom_strength!=null ? "自定义强度" : ({low:"低强度",medium:"中强度",high:"高强度",death:"死亡惩罚"})[rule.tier] || "强度" }
    function modeName(policy) { return ({hp:"HP 伤害",action:"动作反馈",both:"HP + 动作",none:"不接收战斗事件",audio:"剧情音频（旧包络）",action_audio:"战斗动作 / 剧情音频队列",off:"关闭"})[policy.mode] || "关闭" }
    function storyMode(policy) {
        if(policy.story_mode)return policy.story_mode
        if(policy.mode==="audio")return "audio"
        var queued=policy.rules && policy.rules.defeat_interaction.playback==="queue"
        return (queued ? "queue" : "fixed")+(policy.mode==="action_audio" ? "_audio" : "")
    }
    function storyModeName(policy) { return ({fixed:"固定波形",queue:"循环队列",audio:"实时音频",fixed_audio:"固定＋音频",queue_audio:"循环＋音频",off:"关闭剧情输出"})[storyMode(policy)] || "固定波形" }
    function battleRows() {
        var rules=policy.rules || {},mode=policy.mode,result=[]
        var order=["damage_light","damage_medium","damage_heavy","hit_small","hit_normal","heavy_land","wall_bounce","struggle","boss_catch","armor_break","player_down"]
        for(var i=0;i<order.length;i++) {
            var key=order[i],group=key==="player_down" || key==="armor_break" ? "penalty" : key.indexOf("damage_")===0 ? "hp" : "action"
            if(!rules[key] || mode==="off")continue
            if(battleFilter!=="all" && battleFilter!==group)continue
            if(key!=="player_down" && group==="hp" && mode!=="hp" && mode!=="both")continue
            if(key!=="player_down" && group!=="hp" && mode!=="action" && mode!=="both" && mode!=="action_audio")continue
            result.push({key:key,group:group,rule:rules[key]})
        }
        return result
    }
    Component.onCompleted: { refreshSavedView();loadSaved() }
    Connections {
        target:workbench.controller
        function onChanged() {
            workbench.refreshSavedView()
            var strength=JSON.stringify([workbench.controller.lowStrength,workbench.controller.mediumStrength,workbench.controller.highStrength,workbench.controller.deathStrength,workbench.controller.hardCap])
            if(!workbench.strengthDirty && strength!==workbench.savedStrength) {
                workbench.draftLow=workbench.controller.lowStrength;workbench.draftMedium=workbench.controller.mediumStrength
                workbench.draftHigh=workbench.controller.highStrength;workbench.draftDeath=workbench.controller.deathStrength;workbench.draftCap=workbench.controller.hardCap;workbench.savedStrength=strength
            }
            var audio=JSON.stringify([workbench.controller.audioGain,workbench.controller.audioQueueMinimum])
            if(!workbench.audioDirty && audio!==workbench.savedAudio) {
                workbench.draftGain=workbench.controller.audioGain;workbench.draftMinimum=workbench.controller.audioQueueMinimum;workbench.savedAudio=audio
            }
        }
    }
    component Label: LocalizedLabel { color:"#f3ecd9";font.pixelSize:12;wrapMode:Text.WordWrap }
    component Action: Basic.Button {
        id:button
        property bool primary:false
        implicitHeight:40;leftPadding:16;rightPadding:16
        contentItem:Label { sourceText:button.text;color:button.primary ? "#142017" : "#f3ecd9";opacity:button.enabled ? 1 : .45;horizontalAlignment:Text.AlignHCenter;verticalAlignment:Text.AlignVCenter;wrapMode:Text.NoWrap }
        background:Rectangle { radius:11;color:button.primary ? "#8fbd83" : button.hovered ? "#483e2d" : "#353025";border.color:button.primary ? "#8fbd83" : "#65573f";opacity:button.enabled ? 1 : .55 }
    }
    component ValueSlider: Basic.Slider {
        id:slider
        snapMode: workbench.vibration ? Slider.SnapAlways : Slider.NoSnap
        implicitHeight:30
        background:Rectangle { x:slider.leftPadding;y:slider.topPadding+slider.availableHeight/2-height/2;width:slider.availableWidth;height:5;radius:3;color:"#574a36"
            Rectangle { width:parent.width*slider.visualPosition;height:parent.height;radius:3;color:"#8fbd83" }
        }
        handle:Rectangle { x:slider.leftPadding+slider.visualPosition*(slider.availableWidth-width);y:slider.topPadding+slider.availableHeight/2-height/2;width:17;height:21;radius:6;color:"#8fbd83" }
    }
    component Panel: Rectangle { color:"#18241b";radius:14;border.color:"#574a36" }
    component Wave: Canvas {
        property var points:[]
        property color stroke:"#8fbd83"
        onPointsChanged:requestPaint()
        onWidthChanged:requestPaint()
        onHeightChanged:requestPaint()
        onVisibleChanged:if(visible)requestPaint()
        onPaint:{var ctx=getContext("2d");ctx.clearRect(0,0,width,height);ctx.strokeStyle="#443e2e";ctx.lineWidth=1;ctx.beginPath();ctx.moveTo(0,height-3);ctx.lineTo(width,height-3);ctx.stroke();if(!points ||points.length<2)return;ctx.strokeStyle=stroke;ctx.lineWidth=2.2;ctx.beginPath();for(var i=0;i<points.length;i++){var x=i*width/(points.length-1),y=height-4-Number(points[i])*(height-8)/100;if(i===0)ctx.moveTo(x,y);else ctx.lineTo(x,y)}ctx.stroke()}
    }
    component IntensityRow: ColumnLayout {
        id:row
        required property string title
        required property int currentValue
        signal edited(int value)
        spacing:4
        RowLayout {
            Layout.fillWidth:true
            Label { sourceText:row.title;font.bold:true;Layout.preferredWidth:160 }
            ValueSlider { Layout.fillWidth:true;from:0;to:workbench.vibration ? 200 : 100;stepSize:workbench.vibration ? 10 : 1;value:row.currentValue;onMoved:row.edited(Math.round(value)) }
            Label { sourceText:row.currentValue.toString();font.pixelSize:18;font.bold:true;color:workbench.accent;Layout.preferredWidth:40;horizontalAlignment:Text.AlignRight }
        }
    }
    Rectangle { anchors.fill:parent;color:"#25251c";radius:20;border.color:"#574a36" }
    ColumnLayout {
        anchors.fill:parent;anchors.margins:22;spacing:16
        RowLayout {
            Layout.fillWidth:true
            ColumnLayout {
                Layout.fillWidth:true;spacing:4
                Label { sourceText:workbench.vibration ? "负鼠振动" : "郊狼 Pulse";font.pixelSize:20;font.bold:true }
                Label { sourceText:"先设强度，再选战斗与剧情反馈。两个设备分别保存，互不影响。";color:"#aaa68d";font.pixelSize:11;Layout.fillWidth:true }
            }
            Label { objectName:workbench.prefix+"SaveState";sourceText:workbench.section==="manual" ? "仅本次会话" : workbench.hasUnsavedChanges ? "未保存" : "已保存";color:workbench.hasUnsavedChanges ? "#e6be73" : workbench.accent }
            Action { visible:workbench.dialogMode;text:"关闭设置";onClicked:workbench.requestClose() }
        }
        RowLayout {
            Layout.fillWidth:true;spacing:10
            visible:workbench.section!=="manual"
            Label {objectName:workbench.prefix+"RouteState";Layout.fillWidth:true;wrapMode:Text.WordWrap;color:"#e6be73";sourceText:(workbench.vibration ? backend.ovcRoutePaused : backend.pulseRoutePaused) ? "当前设备已暂停，进入剧情不会自动恢复。" : (workbench.vibration ? backend.ovcEnableReason : backend.pulseEnableReason) || "当前设备已启用，剧情反馈遵循本页通道开关。"}
            Action {
                objectName:workbench.prefix+"WorkbenchOutputToggle"
                readonly property bool routePaused:workbench.vibration ? backend.ovcRoutePaused : backend.pulseRoutePaused
                readonly property string reason:workbench.vibration ? backend.ovcEnableReason : backend.pulseEnableReason
                readonly property bool unavailable:(routePaused || !(workbench.vibration ? backend.ovcConnected : backend.deviceConnected) || backend.emergencyStopped) && reason!==""
                text:unavailable ? "无法启用 · 查看原因" : workbench.vibration ? routePaused ? "启用振动" : "暂停振动" : routePaused ? "启用 Pulse" : "暂停 Pulse"
                onClicked:unavailable ? backend.explainOutputUnavailable(workbench.vibration ? "ovc" : "coyote") : workbench.vibration ? backend.toggleOvcOutput() : backend.togglePulseOutput()
            }
        }
        RowLayout {
            Layout.fillWidth:true;spacing:10
            Action { objectName:workbench.prefix+"StrengthSectionButton";Layout.fillWidth:true;text:"强度设置";primary:workbench.section==="strength";onClicked:workbench.section="strength" }
            Action { objectName:workbench.prefix+"StrategySectionButton";Layout.fillWidth:true;text:"战斗反馈";primary:workbench.section==="battle";onClicked:workbench.section="battle" }
            Action { objectName:workbench.prefix+"QueueSectionButton";Layout.fillWidth:true;text:"剧情与鉴赏";primary:workbench.section==="story";onClicked:workbench.section="story" }
        }
        ScrollView {
            id:strengthScroll
            objectName:workbench.prefix+"StrengthScroll"
            visible:workbench.section==="strength";Layout.fillWidth:true;Layout.fillHeight:true;clip:true;contentWidth:availableWidth;rightPadding:10
            ScrollBar.horizontal.policy:ScrollBar.AlwaysOff
            ColumnLayout {
                width:strengthScroll.availableWidth;spacing:18
                Label { Layout.fillWidth:true;sourceText:"事件使用这些档位；每个事件仍可单独指定强度。";color:"#aaa68d" }
                Panel {
                    Layout.fillWidth:true;implicitHeight:strengthRows.implicitHeight+36
                    ColumnLayout {
                        id:strengthRows
                        anchors.left:parent.left;anchors.right:parent.right;anchors.top:parent.top;anchors.margins:18;spacing:14
                        IntensityRow { Layout.fillWidth:true;title:"低强度";currentValue:workbench.draftLow;onEdited:function(value){workbench.draftLow=value} }
                        IntensityRow { Layout.fillWidth:true;title:"中强度";currentValue:workbench.draftMedium;onEdited:function(value){workbench.draftMedium=value} }
                        IntensityRow { Layout.fillWidth:true;title:"高强度";currentValue:workbench.draftHigh;onEdited:function(value){workbench.draftHigh=value} }
                        IntensityRow { Layout.fillWidth:true;title:"死亡惩罚";currentValue:workbench.draftDeath;onEdited:function(value){workbench.draftDeath=value} }
                        Rectangle { Layout.fillWidth:true;height:1;color:"#574a36" }
                        IntensityRow { Layout.fillWidth:true;title:"安全硬上限";currentValue:workbench.draftCap;onEdited:function(value){workbench.draftCap=value} }
                    }
                }
                Label { Layout.fillWidth:true;sourceText:workbench.vibration ? "负鼠按 10 向下对齐发送，1–9 不输出。这里不会改动郊狼强度。" : "这里只调整郊狼电刺激；不会改动负鼠振动强度。";color:"#aaa68d";font.pixelSize:11 }
                Label { visible:!workbench.valid;Layout.fillWidth:true;sourceText:"请保持：低强度 ≤ 中强度 ≤ 高强度 ≤ 死亡惩罚 ≤ 安全上限";color:"#ff5d7a" }
                Action { visible:!workbench.vibration;text:workbench.presetsExpanded ? "收起快速强度方案" : "快速强度方案";onClicked:workbench.presetsExpanded=!workbench.presetsExpanded }
                Panel {
                    visible:!workbench.vibration && workbench.presetsExpanded;Layout.fillWidth:true;implicitHeight:presetRows.implicitHeight+32
                    ColumnLayout {
                        id:presetRows
                        anchors.left:parent.left;anchors.right:parent.right;anchors.top:parent.top;anchors.margins:16;spacing:12
                        Label { Layout.fillWidth:true;sourceText:"仅填入草稿，检查强度与上限后再保存。";color:"#aaa68d";font.pixelSize:11 }
                        RowLayout {
                            Layout.fillWidth:true
                            Action { Layout.fillWidth:true;text:"低强度方案";onClicked:workbench.fillPreset([5,15,25,25,30]) }
                            Action { Layout.fillWidth:true;text:"中强度方案";onClicked:workbench.fillPreset([15,30,40,55,60]) }
                            Action { Layout.fillWidth:true;text:"高强度方案";onClicked:workbench.fillPreset([30,45,60,80,90]) }
                        }
                    }
                }
                Action { visible:!workbench.vibration;text:"全局急停快捷键";onClicked:workbench.hotkeySettingsRequested() }
            }
        }
        RowLayout {
            visible:workbench.section==="strength";Layout.fillWidth:true
            Action { text:"恢复已保存";enabled:workbench.strengthDirty;onClicked:confirmation.ask("放弃未保存的强度调整？","将重新载入已保存的数值，不会恢复出厂值或改写配置文件。",function(){workbench.draftLow=workbench.controller.lowStrength;workbench.draftMedium=workbench.controller.mediumStrength;workbench.draftHigh=workbench.controller.highStrength;workbench.draftDeath=workbench.controller.deathStrength;workbench.draftCap=workbench.controller.hardCap;workbench.savedStrength=JSON.stringify([workbench.draftLow,workbench.draftMedium,workbench.draftHigh,workbench.draftDeath,workbench.draftCap])}) }
            Item { Layout.fillWidth:true }
            Action { objectName:workbench.vibration ? "saveOvcIntensityButton" : "saveIntensityButton";text:"保存强度设置";primary:true;enabled:workbench.valid && workbench.strengthDirty;onClicked:if(workbench.controller.saveIntensitySettings(workbench.draftLow,workbench.draftMedium,workbench.draftHigh,workbench.draftDeath,workbench.draftCap))workbench.savedStrength=JSON.stringify([workbench.draftLow,workbench.draftMedium,workbench.draftHigh,workbench.draftDeath,workbench.draftCap]) }
        }
        ScrollView {
            id:battleScroll
            objectName:workbench.prefix+"BattleScroll"
            visible:workbench.section==="battle";Layout.fillWidth:true;Layout.fillHeight:true;clip:true;contentWidth:availableWidth;rightPadding:10
            ScrollBar.horizontal.policy:ScrollBar.AlwaysOff
            ColumnLayout {
                width:battleScroll.availableWidth;spacing:14
                RowLayout {
                    Layout.fillWidth:true
                    Action { objectName:"battleChannelA";text:"A 通道";primary:workbench.battleChannel==="A";onClicked:workbench.battleChannel="A" }
                    Action { objectName:"battleChannelB";text:"B 通道";primary:workbench.battleChannel==="B";onClicked:workbench.battleChannel="B" }
                    Label { sourceText:workbench.modeName(workbench.policy);color:workbench.accent;Layout.fillWidth:true }
                    Action { objectName:workbench.vibration ? "openOvcStrategyA" : "openPulseStrategyA";text:"通道与高级设置";onClicked:workbench.editChannel(workbench.battleChannel,"battle","all") }
                }
                Label { Layout.fillWidth:true;sourceText:"选择要修改的事件。强度、波形和持续时间在同一处调整。";color:"#aaa68d" }
                RowLayout {
                    Layout.fillWidth:true;spacing:8
                    Repeater {
                        model:[{key:"all",name:"全部"},{key:"hp",name:"HP"},{key:"action",name:"动作"},{key:"penalty",name:"高强度惩罚"}]
                        delegate:Action { required property var modelData;text:modelData.name;primary:workbench.battleFilter===modelData.key;onClicked:workbench.battleFilter=modelData.key }
                    }
                    Item { Layout.fillWidth:true }
                }
                Repeater {
                    model:workbench.battleRows()
                    delegate:Panel {
                        id:ruleRow
                        required property var modelData
                        readonly property var rule:modelData.rule
                        objectName:"battleRule_"+modelData.key
                        Layout.fillWidth:true;implicitHeight:80
                        RowLayout {
                            anchors.fill:parent;anchors.margins:14;spacing:14
                            Rectangle { width:7;height:7;radius:4;color:ruleRow.rule.enabled ? workbench.accent : "#777764" }
                            ColumnLayout {
                                Layout.preferredWidth:165;spacing:4
                                Label { Layout.fillWidth:true;sourceText:ruleRow.modelData.key==="player_down" ? "死亡惩罚" : ruleRow.rule.label;font.bold:true }
                                Label { Layout.fillWidth:true;sourceText:!ruleRow.rule.enabled ? "已关闭" : workbench.tier(ruleRow.rule)+" · "+workbench.strength(ruleRow.rule);color:ruleRow.rule.enabled ? workbench.accent : "#aaa68d";font.pixelSize:11 }
                            }
                            ColumnLayout {
                                Layout.fillWidth:true;spacing:4
                                Label { sourceText:workbench.wave(ruleRow.rule.wave).name;Layout.fillWidth:true;elide:Text.ElideRight;wrapMode:Text.NoWrap }
                                Label { sourceText:ruleRow.modelData.key==="struggle" ? "持续至挣脱" : Number(ruleRow.rule.duration || .1).toFixed(1)+" 秒";color:"#aaa68d";font.pixelSize:11 }
                            }
                            Wave { Layout.preferredWidth:110;Layout.preferredHeight:36;points:workbench.wave(ruleRow.rule.wave).points;stroke:workbench.battleChannel==="A" ? "#8fbd83" : "#ccab77" }
                            Action { objectName:"editBattleRule_"+ruleRow.modelData.key;text:"修改";onClicked:strategy.openEvent(workbench.battleChannel,ruleRow.modelData.key) }
                        }
                    }
                }
                Panel {
                    visible:workbench.battleRows().length===0;Layout.fillWidth:true;implicitHeight:84
                    Label { anchors.fill:parent;anchors.margins:18;verticalAlignment:Text.AlignVCenter;sourceText:"当前通道没有这类战斗反馈，可在“通道与高级设置”修改来源。";color:"#aaa68d" }
                }
                RowLayout {
                    Layout.fillWidth:true
                    Label { sourceText:"波形选择会保留预览；修改并保存后才应用。";color:"#aaa68d";font.pixelSize:11;Layout.fillWidth:true }
                    Action { visible:!workbench.vibration;text:"波形库与编辑器";onClicked:workbench.waveformLibraryRequested() }
                }
                Action { text:"恢复默认反馈";onClicked:confirmation.ask("恢复默认通道策略？","仅恢复当前设备的事件与通道策略，不修改强度、队列或另一台设备。",function(){workbench.controller.resetEventMappings()}) }
            }
        }
        ScrollView {
            id:storyScroll
            objectName:workbench.prefix+"StoryScroll"
            visible:workbench.section==="story";Layout.fillWidth:true;Layout.fillHeight:true;clip:true;contentWidth:availableWidth;rightPadding:10
            ScrollBar.horizontal.policy:ScrollBar.AlwaysOff
            ColumnLayout {
                width:storyScroll.availableWidth;spacing:16
                RowLayout {
                    Layout.fillWidth:true
                    Action { objectName:"storyChannelA";text:"A 通道";primary:workbench.storyChannel==="A";onClicked:workbench.selectStoryChannel("A") }
                    Action { objectName:"storyChannelB";text:"B 通道";primary:workbench.storyChannel==="B";onClicked:workbench.selectStoryChannel("B") }
                    Item { Layout.fillWidth:true }
                    Action { text:"修改播放方式";onClicked:workbench.editChannel(workbench.storyChannel,"story","all") }
                }
                Panel {
                    Layout.fillWidth:true;implicitHeight:storySummary.implicitHeight+36
                    ColumnLayout {
                        id:storySummary
                        anchors.left:parent.left;anchors.right:parent.right;anchors.top:parent.top;anchors.margins:18;spacing:10
                        Label { sourceText:workbench.storyModeName(workbench.storyPolicy);font.pixelSize:20;font.bold:true;color:workbench.accent }
                        Label { Layout.fillWidth:true;sourceText:workbench.storyPolicy.mode==="off" ? "此通道整体关闭，剧情设置会保留，但不会输出。" : workbench.storyMode(workbench.storyPolicy)==="off" || (workbench.storyPolicy.rules && !workbench.storyPolicy.rules.defeat_interaction.enabled) ? "关闭剧情输出" : "进入剧情或鉴赏时使用，离开后恢复战斗反馈。";color:"#aaa68d" }
                        RowLayout {
                            Layout.fillWidth:true
                            Label { Layout.fillWidth:true;sourceText:workbench.storyMode(workbench.storyPolicy).indexOf("queue")>=0 ? "队列段数 " + (workbench.cachedQueues[workbench.storyChannel] || []).length : workbench.storyMode(workbench.storyPolicy)==="audio" ? "实时音频包络（自动生成）" : workbench.wave((workbench.storyPolicy.rules || {}).defeat_interaction ? workbench.storyPolicy.rules.defeat_interaction.wave : "").name }
                            Action { objectName:workbench.prefix+"OpenQueueButton";text:workbench.queueExpanded ? "收起队列" : "编辑循环队列";onClicked:{workbench.queueExpanded=!workbench.queueExpanded;if(workbench.queueExpanded && queueEditor.channel!==workbench.storyChannel)queueEditor.selectChannel(workbench.storyChannel)} }
                        }
                    }
                }
                StoryQueueEditor { id:queueEditor;objectName:workbench.prefix+"StoryQueueEditor";controller:workbench.controller;visible:workbench.queueExpanded;Layout.fillWidth:true;Layout.preferredHeight:implicitHeight;onChannelChanged:workbench.storyChannel=channel }
                Action { text:workbench.audioExpanded ? "收起音频调节" : "音频强度调节";onClicked:workbench.audioExpanded=!workbench.audioExpanded }
                Panel {
                    visible:workbench.audioExpanded;Layout.fillWidth:true;implicitHeight:audioRows.implicitHeight+36
                    ColumnLayout {
                        id:audioRows
                        anchors.left:parent.left;anchors.right:parent.right;anchors.top:parent.top;anchors.margins:18;spacing:14
                        RowLayout {
                            Layout.fillWidth:true
                            Label { sourceText:"音频只调节强度，不更换当前波形。";Layout.fillWidth:true;color:"#aaa68d" }
                            Action { text:"音频来源与监听";onClicked:workbench.audioSourceRequested() }
                        }
                        RowLayout {
                            Layout.fillWidth:true
                            Label { sourceText:"音频强度增益";Layout.preferredWidth:160 }
                            ValueSlider { Layout.fillWidth:true;from:0;to:10;stepSize:.1;value:workbench.draftGain;onMoved:workbench.draftGain=Math.round(value*10)/10 }
                            Label { sourceText:workbench.draftGain.toFixed(1)+"×";Layout.preferredWidth:50 }
                        }
                        RowLayout {
                            Layout.fillWidth:true
                            Label { sourceText:"音频队列最低强度";Layout.preferredWidth:160 }
                            ValueSlider { Layout.fillWidth:true;from:0;to:workbench.vibration ? Math.floor(workbench.controller.hardCap/10)*10 : workbench.controller.hardCap;stepSize:workbench.vibration ? 10 : 1;value:workbench.draftMinimum;onMoved:workbench.draftMinimum=Math.round(value) }
                            Label { sourceText:workbench.draftMinimum.toString();Layout.preferredWidth:50 }
                        }
                        RowLayout {
                            Layout.fillWidth:true
                            Label { sourceText:backend.audioEmpathyEnabled ? "音频监听已开启" : "音频监听未开启，音频模式暂不响应。";Layout.fillWidth:true;color:backend.audioEmpathyEnabled ? workbench.accent : "#e6be73";font.pixelSize:11 }
                            Action { objectName:workbench.prefix+"SaveAudioButton";text:"保存音频调节";primary:true;enabled:workbench.audioDirty;onClicked:{if(workbench.controller.saveAudioGain(workbench.draftGain) && workbench.controller.saveAudioQueueMinimum(workbench.draftMinimum))workbench.savedAudio=JSON.stringify([workbench.draftGain,workbench.draftMinimum])} }
                        }
                    }
                }
            }
        }
    }
    ChannelStrategyDialog { id:strategy;objectName:workbench.prefix+"ChannelStrategyDialog";controller:workbench.controller;onQueueEditorRequested:function(channel){workbench.showQueue(channel)} }
    ConfirmResetDialog { id:confirmation;objectName:workbench.prefix+"ResetConfirmation" }
}
