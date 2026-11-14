import QtQuick

// The one button style: a rounded pill. `primary` fills it with the accent; `icon` adds a leading glyph.
Rectangle {
    id: pill
    property string text
    property string icon: ""
    property bool primary: false
    signal hit()
    implicitWidth: row.implicitWidth + 26; implicitHeight: Theme.ctl + 2; radius: height / 2
    opacity: enabled ? 1 : 0.4
    color: primary ? (pma.pressed ? Qt.darker(Theme.accent, 1.12) : pma.containsMouse ? Theme.accentHi : Theme.accent)
                   : (pma.pressed ? Theme.press : pma.containsMouse ? Theme.hover : "transparent")
    border.width: primary ? 0 : 1
    border.color: pma.containsMouse ? Theme.accentLine : Theme.line
    Behavior on color { ColorAnimation { duration: Theme.fast } }
    Row {
        id: row
        anchors.centerIn: parent
        spacing: 6
        Icon { visible: pill.icon !== ""; name: pill.icon; size: 14; anchors.verticalCenter: parent.verticalCenter
               color: pill.primary ? Theme.onAccent : Theme.text }
        Text { text: pill.text; anchors.verticalCenter: parent.verticalCenter
               color: pill.primary ? Theme.onAccent : Theme.text
               font.pixelSize: Theme.fs; font.family: Theme.sans; font.weight: pill.primary ? Font.DemiBold : Font.Medium }
    }
    MouseArea { id: pma; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: pill.hit() }
}
