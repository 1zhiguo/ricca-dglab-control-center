pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls

Dialog {
    id: dialog
    objectName: "ovcConfigDialog"
    required property var controller
    property alias section: workbench.section
    readonly property bool hasUnsavedQueue: workbench.hasUnsavedQueue
    parent: Overlay.overlay
    anchors.centerIn: parent
    width: Math.min(1050, parent.width - 48)
    height: Math.min(770, parent.height - 48)
    modal: true
    padding: 0
    closePolicy: workbench.hasUnsavedQueue ? Popup.NoAutoClose : Popup.CloseOnEscape
    background: Item {}

    function loadSaved() { workbench.loadSaved() }
    function openSettings() { workbench.showSection("strength"); open() }
    function openChannel(channel) { open(); workbench.openChannel(channel) }
    function showQueue(channel) { workbench.showQueue(channel) }
    function requestClose() { workbench.requestClose() }

    contentItem: OvcWorkbench {
        id: workbench
        objectName: "ovcDialogWorkbench"
        controller: dialog.controller
        dialogMode: true
        onCloseRequested: dialog.close()
    }
}
