pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Item {
    id:page
    objectName:"manualControlPage"
    readonly property bool showOvc:backend.ovcConnected || (backend.v4AppConnected && backend.ovcDeviceIndex>0)
    property var pulseCatalog:[]
    property var ovcCatalog:[]
    property string pulseSnapshot:""
    property string ovcSnapshot:""
    function refreshCatalogs(){
        var pulse=backend.waveformCatalog,ovc=backend.ovcController.waveformCatalog
        var p=JSON.stringify(pulse),o=JSON.stringify(ovc)
        if(p!==pulseSnapshot){pulseCatalog=pulse;pulseSnapshot=p}
        if(o!==ovcSnapshot){ovcCatalog=ovc;ovcSnapshot=o}
    }
    Component.onCompleted:refreshCatalogs()
    onVisibleChanged:if(visible)refreshCatalogs()
    Connections {target:backend;function onChanged(){if(page.visible)page.refreshCatalogs()}}
    ColumnLayout {
        anchors.fill:parent;anchors.margins:16;spacing:12
        LocalizedLabel {Layout.fillWidth:true;sourceText:"不依赖游戏检测。仅接管当前设备，另一台设备保持原模式；不会改写已保存的强度、波形或队列。";color:"#aaa68d";font.pixelSize:11;wrapMode:Text.WordWrap}
        RowLayout {
            objectName:"manualDeviceColumns";Layout.fillWidth:true;Layout.fillHeight:true;spacing:16
            ManualDeviceConsole {objectName:"pulseManualPanel";Layout.fillWidth:true;Layout.preferredWidth:1;Layout.fillHeight:true;controller:backend;catalog:page.pulseCatalog}
            ManualDeviceConsole {objectName:"ovcManualPanel";visible:page.showOvc;Layout.fillWidth:true;Layout.preferredWidth:1;Layout.fillHeight:true;controller:backend.ovcController;vibration:true;catalog:page.ovcCatalog}
        }
    }
}
