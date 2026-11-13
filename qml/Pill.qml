import QtQuick

// The one button style: a rounded pill, accent when primary.
Rectangle {
    id: pill
    property string text
    property bool primary: false
    signal hit()
    implicitWidth: pl.implicitWidth + 24; implicitHeight: 28; radius: 14
    opacity: enabled ? 1 : 0.45
    color: primary ? (pma.containsMouse ? Theme.accentHi : Theme.accent) : (pma.containsMouse ? Theme.panel2 : Theme.field)
    border.color: primary ? "transparent" : Theme.line
    Text { id: pl; anchors.centerIn: parent; text: pill.text; color: "white"; font.pixelSize: 12; font.bold: pill.primary }
    MouseArea { id: pma; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: pill.hit() }
}
