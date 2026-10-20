import QtQuick
import QtQuick.Controls
import QtQuick.Controls.Basic as Basic
import QtQuick.Layouts

Item {
    id: editor
    required property var controller
    objectName: "storyQueueEditor"
    property string channel: "A"
    property var draft: []
    property bool draftEnabled: false
    property bool dirty: false
    property var waves: []
    readonly property var tiers: [
        {key:"low",name:"低档"}, {key:"medium",name:"中档"},
        {key:"high",name:"高档"}, {key:"death",name:"死亡档"}, {key:"custom",name:"自定义"}
    ]
    readonly property var status: controller.storyQueueStatus[channel] || ({})
    readonly property color accent: channel === "A" ? "#8fbd83" : "#ccab77"
    implicitHeight: content.implicitHeight + 40
    function indexOf(values, key) {
        for (var i=0; i<values.length; ++i) if (values[i].key === key) return i
        return 0
    }
    function loadChannel(value) {
        channel = value
        waves = [{key:"idle",name:"休止（无输出）",points:[],color:"#aaa68d"}].concat(controller.waveformCatalog)
        draftEnabled = controller.channelPolicies[value].rules.defeat_interaction.playback === "queue"
        draft = JSON.parse(JSON.stringify(controller.storyQueues[value] || []))
        dirty = false
    }
    function selectChannel(value) {
        if (dirty) discardConfirmation.ask("切换通道并放弃未保存修改？", "当前队列尚未保存。已保存的另一通道队列不会改变。", function() { editor.loadChannel(value) }, "放弃并切换")
        else loadChannel(value)
    }
    function setStep(index, field, value) { draft[index][field] = value; dirty = true }
    function addStep() {
        if (draft.length >= 16) return
        var copy = JSON.parse(JSON.stringify(draft))
        copy.push({wave:"official_tide",duration:5,tier:"low",custom_strength:null})
        draft = copy; dirty = true
    }
    function moveStep(index, offset) {
        var target = index + offset
        if (target < 0 || target >= draft.length) return
        var copy = JSON.parse(JSON.stringify(draft)), item = copy[index]
        copy[index] = copy[target]; copy[target] = item
        draft = copy; dirty = true
    }
    function removeStep(index) {
        var copy = JSON.parse(JSON.stringify(draft)); copy.splice(index,1)
        draft = copy; dirty = true
    }
    function restoreSaved() {
        discardConfirmation.ask("恢复已保存的队列？", "只放弃当前未保存的修改，不恢复出厂值。", function() { editor.loadChannel(editor.channel) }, "恢复已保存")
    }
    function saveQueue() {
        if(controller.saveStoryQueue(channel,draft,draftEnabled)) loadChannel(channel)
    }
    Component.onCompleted: loadChannel("A")
    Connections {
        target: editor.controller
        function onChanged() {
            // Telemetry does not replace an in-progress edit.
            if (!editor.dirty) {
                var saved = JSON.stringify(editor.controller.storyQueues[editor.channel] || [])
                if (saved !== JSON.stringify(editor.draft)) editor.loadChannel(editor.channel)
                editor.draftEnabled = editor.controller.channelPolicies[editor.channel].rules.defeat_interaction.playback === "queue"
            }
        }
    }
    component Label: LocalizedText { color:"#f3ecd9"; font.family:backend.uiFontFamily; font.pixelSize:12; renderType: Text.NativeRendering }
    component Action: Basic.Button {
        id: action
        implicitHeight:38; leftPadding:13; rightPadding:13
        property bool primary:false
        contentItem: Label { sourceText:action.text; color:action.enabled ? action.primary ? "#142017" : "#f3ecd9" : "#777764"; horizontalAlignment:Text.AlignHCenter; verticalAlignment:Text.AlignVCenter }
        background: Rectangle { radius:10; color:action.primary ? editor.accent : action.hovered ? "#483e2d" : "#353025"; border.color:"#65573f" }
    }
    component Choice: Basic.ComboBox {
        id: choice
        implicitHeight:38; textRole:"name"; valueRole:"key"
        contentItem: Label { sourceText:choice.displayText; leftPadding:10; rightPadding:22; verticalAlignment:Text.AlignVCenter; elide:Text.ElideRight }
        indicator: Label { sourceText:"⌄"; x:choice.width-19; anchors.verticalCenter:parent.verticalCenter; color:editor.accent }
        background: Rectangle { radius:9; color:"#111a14"; border.color:"#574a36" }
        delegate: ItemDelegate { required property int index; width:choice.width; height:38
            contentItem: Label { sourceText:choice.textAt(index); verticalAlignment:Text.AlignVCenter; elide:Text.ElideRight }
            background: Rectangle { color:highlighted ? "#483e2d" : "#25251c" }
        }
        popup: Popup { y:choice.height+4; width:choice.width; padding:5; implicitHeight:Math.min(contentItem.implicitHeight+10,280)
            background: Rectangle { color:"#25251c"; border.color:"#65573f"; radius:10 }
            contentItem: ListView { clip:true; implicitHeight:contentHeight; model:choice.popup.visible ? choice.delegateModel : null; currentIndex:choice.highlightedIndex; ScrollIndicator.vertical:ScrollIndicator {} }
        }
    }
    component WavePreview: Canvas {
        property var points:[]
        onPointsChanged:requestPaint()
        onWidthChanged:requestPaint()
        onHeightChanged:requestPaint()
        onPaint:{
            var ctx=getContext("2d"); ctx.clearRect(0,0,width,height)
            ctx.strokeStyle="#574a36"; ctx.lineWidth=1; ctx.beginPath(); ctx.moveTo(0,height-2); ctx.lineTo(width,height-2); ctx.stroke()
            if(!points || points.length<2) return
            ctx.strokeStyle=editor.accent; ctx.lineWidth=2; ctx.beginPath()
            for(var i=0;i<points.length;++i) { var x=i*width/(points.length-1),y=height-3-Number(points[i])*(height-6)/100; if(i===0)ctx.moveTo(x,y);else ctx.lineTo(x,y) }
            ctx.stroke()
        }
    }
    Rectangle { anchors.fill:parent; radius:18; color:"#25251c"; border.color:"#574a36" }
    ColumnLayout {
        id: content
        anchors { left:parent.left; right:parent.right; top:parent.top; margins:20 }
        spacing:14
        RowLayout { Layout.fillWidth:true; spacing:10
            Label { sourceText:"剧情 Pulse 队列"; font.pixelSize:19; font.bold:true; Layout.fillWidth:true }
            Action { objectName:"storyQueueChannelA"; text:"A 通道"; primary:editor.channel==="A"; onClicked:editor.selectChannel("A") }
            Action { objectName:"storyQueueChannelB"; text:"B 通道"; primary:editor.channel==="B"; onClicked:editor.selectChannel("B") }
            Action { objectName:"saveStoryQueueQuickButton"; text:"保存并应用"; onClicked:editor.saveQueue() }
        }
        RowLayout { Layout.fillWidth:true
            Basic.Switch { id:queueEnabled; objectName:"storyQueueEnabled"; checked:editor.draftEnabled; implicitWidth:48; implicitHeight:30; onToggled:{ editor.draftEnabled=checked; editor.dirty=true }
                indicator:Rectangle { implicitWidth:44; implicitHeight:24; y:(queueEnabled.height-height)/2; radius:12; color:queueEnabled.checked ? editor.accent : "#574a36"
                    Rectangle { width:18; height:18; radius:9; anchors.verticalCenter:parent.verticalCenter; x:queueEnabled.checked ? parent.width-width-3 : 3; color:"#f3ecd9"; Behavior on x { NumberAnimation { duration:120 } } }
                }
            }
            Label { sourceText:"用于 " + editor.channel + " 通道的 CG 剧情循环"; font.bold:true; Layout.fillWidth:true }
            Label { sourceText:editor.dirty ? "未保存" : "已保存"; color:editor.dirty ? "#e6be73" : editor.accent }
        }
        Label { Layout.fillWidth:true; wrapMode:Text.WordWrap; color:"#aaa68d"; font.pixelSize:11
            sourceText:(editor.controller.channelPolicies[editor.channel].story_mode || (editor.controller.channelPolicies[editor.channel].mode === "action_audio" ? "queue_audio" : "queue")).indexOf("audio") >= 0 ? "循环＋音频：波形按段循环，当前段强度 × 音频系数；静音归零但队列继续计时。只在有效剧情 / Scene 响应；须在音频共感页启用监听。" : "逐段播放，到末尾回到第 1 段；每段 0.5–30 秒，最多 16 段。暂停冻结进度，离开场景停止；死亡惩罚优先。通道 / CG 循环关闭时不输出，强度仍受破甲倍率与硬上限约束。"
        }
        Rectangle { Layout.fillWidth:true; Layout.preferredHeight:42; radius:9; color:"#142017"
            Label { objectName:"storyQueueProgress"; anchors.fill:parent; anchors.margins:10; verticalAlignment:Text.AlignVCenter; color:editor.accent; elide:Text.ElideRight
                sourceText:!editor.status.configured ? "当前通道使用单波形循环；勾选上方开关并保存后使用队列"
                     : !editor.status.count ? "队列为空 · 不输出"
                     : !editor.status.enabled ? "队列已选择 · 当前通道或 CG 剧情循环开关关闭，不输出"
                     : (editor.status.playing ? "循环播放" : "等待 / 暂停") + " · 第 " + editor.status.index + "/" + editor.status.count + " 段 · 剩余 " + Number(editor.status.remaining).toFixed(1) + " 秒" + (editor.status.missing_wave ? " · 波形缺失，当前段静默" : "")
            }
        }
        Repeater {
            model:editor.draft
            delegate:Rectangle {
                id: step
                required property var modelData
                required property int index
                property string strengthMode:modelData.custom_strength == null ? modelData.tier : "custom"
                Layout.fillWidth:true; Layout.preferredHeight:140
                radius:12; color:"#18241b"; border.color:"#574a36"
                ColumnLayout { anchors.fill:parent; anchors.margins:14; spacing:10
                    RowLayout { Layout.fillWidth:true; spacing:9
                        Label { sourceText:(step.index+1).toString().padStart(2,"0"); color:editor.accent; font.bold:true; Layout.preferredWidth:24 }
                        Choice { id:queueWaveChoice; objectName:"queueWave_"+step.index; Layout.fillWidth:true; Layout.minimumWidth:140; model:editor.waves; currentIndex:editor.indexOf(editor.waves,step.modelData.wave); onActivated:editor.setStep(step.index,"wave",currentValue) }
                        Choice { objectName:"queueTier_"+step.index; Layout.preferredWidth:110; model:editor.tiers; currentIndex:editor.indexOf(editor.tiers,step.strengthMode); onActivated:{ step.strengthMode=currentValue; editor.setStep(step.index,"custom_strength",currentValue==="custom" ? customStrength.value : null); if(currentValue!=="custom") editor.setStep(step.index,"tier",currentValue) } }
                        Basic.SpinBox { id:customStrength; objectName:"queueStrength_"+step.index; visible:step.strengthMode==="custom"; Layout.preferredWidth:100; Layout.preferredHeight:38; from:0; to:100; editable:true; value:step.modelData.custom_strength == null ? editor.controller[step.modelData.tier+"Strength"] : step.modelData.custom_strength; onValueModified:editor.setStep(step.index,"custom_strength",value) }
                        Label { visible:step.strengthMode!=="custom"; sourceText:step.strengthMode==="custom" ? "" : editor.controller[step.strengthMode+"Strength"]; color:editor.accent; Layout.preferredWidth:28 }
                        Action { text:"↑"; enabled:step.index>0; onClicked:editor.moveStep(step.index,-1) }
                        Action { text:"↓"; enabled:step.index<editor.draft.length-1; onClicked:editor.moveStep(step.index,1) }
                        Action { objectName:"queueRemove_"+step.index; text:"×"; enabled:editor.draft.length>1; onClicked:editor.removeStep(step.index) }
                    }
                    RowLayout { Layout.fillWidth:true; spacing:12
                        Label { sourceText:"持续时间"; color:"#aaa68d"; Layout.preferredWidth:64 }
                        Basic.Slider { id:queueDuration; objectName:"queueDuration_"+step.index; Layout.fillWidth:true; from:0.5; to:30; stepSize:0.5; value:step.modelData.duration; onMoved:editor.setStep(step.index,"duration",Math.round(value*2)/2) }
                        Label { sourceText:Number(queueDuration.value).toFixed(1)+" 秒"; color:editor.accent; Layout.preferredWidth:60 }
                        WavePreview { Layout.preferredWidth:140; Layout.preferredHeight:28; points:(editor.waves[queueWaveChoice.currentIndex] || {}).points || [] }
                    }
                    Label { sourceText:queueWaveChoice.currentValue==="idle" ? "休止段：本通道归零，不叠加其他剧情音频" : "波形在本段内重复播放，结束后切换下一段"; color:"#aaa68d"; font.pixelSize:10 }
                }
            }
        }
        RowLayout { Layout.fillWidth:true; spacing:12
            Action { objectName:"addStoryQueueStep"; text:"＋ 添加一段"; enabled:editor.draft.length<16; onClicked:editor.addStep() }
            Item { Layout.fillWidth:true }
            Action { text:"恢复已保存"; onClicked:editor.restoreSaved() }
            Action { objectName:"saveStoryQueueButton"; text:"保存并应用 "+editor.channel+" 队列"; primary:true; onClicked:editor.saveQueue() }
        }
    }
    ConfirmResetDialog { id:discardConfirmation; objectName:"queueDiscardConfirmation" }
}
