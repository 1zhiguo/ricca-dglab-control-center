import QtQuick

Text {
    property string sourceText: ""
    property bool translateEnabled: true
    text: translateEnabled ? backend.localize(sourceText, backend.language) : sourceText
    font.family: backend.uiFontFamily
    elide: Text.ElideRight
}
