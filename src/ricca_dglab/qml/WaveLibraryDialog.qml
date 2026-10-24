pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic as Basic
import QtQuick.Controls
import QtQuick.Layouts

Dialog {
    id: library
    objectName: "waveLibraryDialog"
    required property var controller
    signal editRequested(string name, var points, int frequency)
    property string selectedKey: "impact"
    property string filter: "all"
    property bool advanced: false
    property var cachedCatalog: []
    property string catalogSnapshot: ""
    function refreshCatalog() {
        var saved=controller.waveformCatalog, snapshot=JSON.stringify(saved)
        if(catalogSnapshot !== snapshot) { cachedCatalog=saved;catalogSnapshot=snapshot }
    }
    onOpened:refreshCatalog()
    Connections { target:library.controller;function onChanged(){if(library.visible)library.refreshCatalog()} }
    readonly property var catalog: {
        var rows = [], saved=cachedCatalog
        for (var i=0;i<saved.length;i++) {
            var wave = saved[i]
            if (filter === "all" || wave.group === filter) rows.push(wave)
        }
        return rows
    }
    readonly property var selectedWave: {
        var waves = cachedCatalog
        for (var i=0;i<waves.length;i++) if (waves[i].key === selectedKey) return waves[i]
        return waves.length ? waves[0] : ({name:"待机",points:[],frequency:24,color:"#8fbd83"})
    }
    parent: Overlay.overlay
    anchors.centerIn: parent
    width: Math.min(1010, parent.width-48)
    height: Math.min(720, parent.height-48)
    padding: 24
    modal: true
    background: Rectangle { radius:20; color:"#25251c"; border.color:"#65573f" }
    component Label: LocalizedLabel { color:"#f3ecd9"; font.family:backend.uiFontFamily; font.pixelSize:12; wrapMode:Text.WordWrap }
    component Action: Basic.Button {
        id: control
        property bool primary: false
        implicitHeight:40; leftPadding:16; rightPadding:16
        contentItem:Label { sourceText:control.text; color:control.primary ? "#142017" : "#f3ecd9"; horizontalAlignment:Text.AlignHCenter; verticalAlignment:Text.AlignVCenter; wrapMode:Text.NoWrap }
        background:Rectangle { radius:11; color:control.primary ? "#8fbd83" : control.hovered ? "#483e2d" : "#353025"; border.color:"#65573f" }
    }
    component Plot: Canvas {
        id: plot
        property var points: []
        property color stroke: "#8fbd83"
        onPointsChanged:requestPaint()
        onWidthChanged:requestPaint()
        onHeightChanged:requestPaint()
        onVisibleChanged:if(visible)requestPaint()
        onStrokeChanged:requestPaint()
        onPaint:{
            var ctx=getContext("2d");ctx.clearRect(0,0,width,height)
            ctx.strokeStyle="#443e2e";ctx.lineWidth=1
            for(var r=1;r<4;r++){ctx.beginPath();ctx.moveTo(0,height*r/4);ctx.lineTo(width,height*r/4);ctx.stroke()}
            if(!points || points.length<2)return
            ctx.strokeStyle=stroke;ctx.lineWidth=2.5;ctx.lineJoin="round";ctx.beginPath()
            for(var i=0;i<points.length;i++){var x=i*width/(points.length-1),y=height-5-points[i]*(height-10)/100;if(i===0)ctx.moveTo(x,y);else ctx.lineTo(x,y)}ctx.stroke()
        }
    }
    contentItem:ColumnLayout {
        spacing:14
        RowLayout {
            Layout.fillWidth:true
            ColumnLayout {
                Layout.fillWidth:true; spacing:4
                Label { sourceText:"波形库与编辑器"; font.pixelSize:22; font.bold:true }
                Label { Layout.fillWidth:true; sourceText:"这里仅预览和编辑波形；请在事件或剧情设置中选择要使用的波形。"; color:"#aaa68d" }
            }
            Action { text:"返回工作台"; onClicked:library.close() }
        }
        RowLayout {
            Layout.fillWidth:true
            Repeater {
                model:[{key:"all",name:"全部"},{key:"official",name:"官方波形"},{key:"custom",name:"自定义波形"},{key:"builtin",name:"内置波形"}]
                delegate:Action { required property var modelData; text:modelData.name; primary:library.filter===modelData.key; onClicked:library.filter=modelData.key }
            }
            Item { Layout.fillWidth:true }
            Label { sourceText:library.catalog.length+" 个波形"; color:"#aaa68d" }
        }
        ListView {
            id: waves
            Layout.fillWidth:true; Layout.fillHeight:true
            clip:true; spacing:8; model:library.catalog
            ScrollBar.vertical:ScrollBar {}
            delegate:Rectangle {
                required property var modelData
                width:waves.width-12; height:76; radius:12
                color:library.selectedKey===modelData.key ? "#243527" : "#353025"
                border.color:library.selectedKey===modelData.key ? "#8fbd83" : "#574a36"
                RowLayout {
                    anchors.fill:parent; anchors.margins:12; spacing:16
                    Label { Layout.preferredWidth:180; sourceText:modelData.name; font.bold:true }
                    Plot { Layout.fillWidth:true; Layout.fillHeight:true; points:modelData.points; stroke:modelData.color }
                    Label { Layout.preferredWidth:65; sourceText:modelData.frequency+" Hz"; color:"#aaa68d"; horizontalAlignment:Text.AlignRight }
                }
                MouseArea { anchors.fill:parent; cursorShape:Qt.PointingHandCursor; onClicked:library.selectedKey=modelData.key }
            }
        }
        RowLayout {
            Layout.fillWidth:true
            Action { objectName:"newCustomWaveButton"; text:"新建波形"; onClicked:library.editRequested("Ricca 自定义",[0,18,48,82,100,58,20,0,0,25,68,45,15,0,0,0],92) }
            Action { objectName:"editSelectedWaveButton"; text:"编辑当前波形"; primary:true; onClicked:library.editRequested(library.selectedWave.name,library.selectedWave.points,library.selectedWave.frequency) }
            Action { text:"打开目录"; onClicked:library.controller.openWaveformLibraryFolder() }
            Item { Layout.fillWidth:true }
            Action { objectName:"advancedWaveActionsButton"; text:library.advanced ? "收起高级操作" : "高级操作"; onClicked:library.advanced=!library.advanced }
        }
        Rectangle {
            visible:library.advanced; Layout.fillWidth:true; implicitHeight:90; radius:12; color:"#30271b"; border.color:"#66502a"
            RowLayout {
                anchors.fill:parent; anchors.margins:14; spacing:16
                Label { Layout.fillWidth:true; sourceText:"将当前波形应用到全部事件会覆盖已有波形分配；强度和硬上限不变。"; color:"#e6be73" }
                Action { text:"应用固定波形"; onClicked:confirmation.ask("将当前波形应用到全部事件？", "将覆盖郊狼事件的波形分配，不修改负鼠配置、强度或硬上限。",function(){library.controller.applyWaveformToAllEvents(library.selectedKey)},"确认应用") }
            }
        }
    }
    ConfirmResetDialog { id:confirmation }
}
