pragma ComponentBehavior: Bound
import QtQuick

Item {
    id: panel
    required property var options
    required property var readings
    property var historyA: []
    property var historyB: []
    readonly property real unit: height / 68
    readonly property int count: (Number(options.show_pulse) + Number(options.show_ovc)) * (Number(options.show_a) + Number(options.show_b))
    implicitWidth: 730; implicitHeight: 68
    Rectangle {
        anchors.fill: parent; anchors.margins: 1
        color: Qt.rgba(.035,.085,.075, panel.options.opacity / 100)
        border.color: "#bba063"; border.width: 1; radius: 3
        Rectangle { anchors.fill:parent; anchors.margins:3; color:"transparent";border.color:"#546e6650";radius:2 }
    }
    Canvas {
        anchors.fill: parent
        onWidthChanged:requestPaint()
        onHeightChanged:requestPaint()
        onPaint: {
            var ctx=getContext("2d");ctx.reset();ctx.strokeStyle="#e1c581";ctx.lineWidth=1
            for(var side=0;side<2;side++) {
                var x=side ? width-7 : 7, direction=side ? -1 : 1
                ctx.beginPath();ctx.moveTo(x,6);ctx.lineTo(x+direction*6,12);ctx.lineTo(x,18);ctx.stroke()
                ctx.beginPath();ctx.moveTo(x, height-6);ctx.lineTo(x+direction*6,height-12);ctx.lineTo(x,height-18);ctx.stroke()
            }
        }
    }
    Row {
        anchors.fill:parent;anchors.margins:8*panel.unit;anchors.leftMargin:Math.max(16,10*panel.unit);anchors.rightMargin:Math.max(16,10*panel.unit);spacing:12*panel.unit
        Repeater {
            model:["pulseA","pulseB","ovcA","ovcB"]
            delegate:Item {
                id:cell
                required property string modelData
                readonly property bool vibration:modelData.indexOf("ovc")===0
                readonly property string letter:modelData.slice(-1)
                readonly property var reading:panel.readings[modelData] || ({strength:0,bars:0,status:"待机",live:false})
                readonly property color accent:letter==="A" ? "#d8ad68" : "#8bccc1"
                visible:(vibration ? panel.options.show_ovc : panel.options.show_pulse) && (letter==="A" ? panel.options.show_a : panel.options.show_b)
                width:(parent.width-Math.max(0,panel.count-1)*parent.spacing)/Math.max(1,panel.count)
                height:parent.height
                Rectangle { visible:cell.modelData!=="pulseA";x:-6*panel.unit;y:2;height:parent.height-4;width:1;color:"#606f7154" }
                LocalizedText {
                    id:titleText
                    objectName:"hudTitle"+cell.modelData
                    anchors.left:parent.left;anchors.top:parent.top
                    width:Math.max(1,parent.width-(panel.options.show_numbers ? numberText.implicitWidth+5*panel.unit : 0))
                    sourceText:cell.letter + " · " + (cell.vibration ? "负鼠" : "郊狼")
                    color:"#f1dfaf";font.family:backend.uiFontFamily;font.bold:true;font.pixelSize:Math.max(9,11*panel.unit)
                }
                LocalizedText {
                    id:numberText
                    objectName:"hudNumber"+cell.modelData
                    visible:panel.options.show_numbers
                    anchors.right:parent.right;anchors.top:parent.top
                    sourceText:cell.reading.strength
                    color:cell.reading.live ? "#fff4d5" : "#a99f86";font.bold:true;font.pixelSize:Math.max(10,15*panel.unit)
                }
                LocalizedText {
                    visible:panel.options.show_status
                    anchors.left:parent.left;anchors.bottom:parent.bottom
                    width:cell.vibration || !panel.options.show_waveforms ? Math.max(1,parent.width-signalBars.width-3*panel.unit) : parent.width
                    sourceText:cell.reading.status;color:cell.reading.live ? "#a5d9be" : "#b5ac94"
                    font.family:backend.uiFontFamily;font.pixelSize:Math.max(8,9*panel.unit)
                }
                Item {
                    id:signalBars
                    visible:cell.vibration || !panel.options.show_waveforms
                    anchors.right:parent.right;anchors.bottom:parent.bottom
                    width:Math.min(55*panel.unit,parent.width*.55);height:23*panel.unit
                    Row {
                        anchors.right:parent.right;anchors.bottom:parent.bottom;spacing:3*panel.unit
                        Repeater {
                            model:5
                            delegate:Rectangle {
                                required property int index
                                objectName:"hudBar"+cell.modelData+index
                                width:Math.max(1,(signalBars.width-12*panel.unit)/5);height:(7+index*4)*panel.unit
                                anchors.bottom:parent.bottom
                                color:cell.reading.bars > index ? cell.accent : "#3e4b41"
                                border.width:1;border.color:cell.reading.bars > index ? "#e8d9a1" : "#67634d"
                                radius:1
                            }
                        }
                    }
                }
                Canvas {
                    id:graph
                    visible:!cell.vibration && panel.options.show_waveforms
                    x:0;y:parent.height*.40;width:parent.width;height:parent.height*(panel.options.show_status ? .36 : .60)
                    property var values:cell.letter==="A" ? panel.historyA : panel.historyB
                    property color line:cell.reading.live ? cell.accent : "#677365"
                    onValuesChanged:requestPaint()
                    onLineChanged:requestPaint()
                    onWidthChanged:requestPaint()
                    onHeightChanged:requestPaint()
                    onPaint:{
                        var ctx=getContext("2d");ctx.reset();ctx.strokeStyle="#506b6b4b";ctx.lineWidth=1
                        ctx.beginPath();ctx.moveTo(0,height-1);ctx.lineTo(width,height-1);ctx.stroke()
                        if(!values || values.length<2)return
                        ctx.strokeStyle=line;ctx.lineWidth=Math.max(1.2,1.8*panel.unit);ctx.lineJoin="round";ctx.beginPath()
                        for(var i=0;i<values.length;i++){var x=i*width/(values.length-1),y=height-1-Math.max(0,Math.min(1,values[i]))*(height-2);if(i===0)ctx.moveTo(x,y);else ctx.lineTo(x,y)}ctx.stroke()
                    }
                }
            }
        }
    }
}
