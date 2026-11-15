import QtQuick
import QtQuick.Controls

// A square icon button: hover wash, accent when `on`. `tip` shows after a short delay, with `keys` as a keycap.
Rectangle {
    id: b
    property string icon: ""
    property string tip: ""
    property string keys: ""
    property bool on: false
    property real size: Theme.ctl + 6
    property real iconSize: 17
    property color tint: Theme.dim
    signal hit()
    implicitWidth: size; implicitHeight: size
    radius: Theme.r2
    opacity: enabled ? 1 : 0.35
    color: on ? Theme.accentSoft : ma.pressed ? Theme.press : ma.containsMouse ? Theme.hover : "transparent"
    border.width: on ? 1 : 0
    border.color: Theme.accentLine
    Behavior on color { ColorAnimation { duration: Theme.fast } }
    Icon {
        anchors.centerIn: parent
        name: b.icon; size: b.iconSize
        color: b.on ? Theme.accentHi : ma.containsMouse ? Theme.text : b.tint
    }
    MouseArea { id: ma; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: b.hit() }
    ToolTip.visible: ma.containsMouse && b.tip !== ""
    ToolTip.text: b.tip + (b.keys !== "" ? "   " + b.keys : "")
    ToolTip.delay: 450
}
