import QtQuick

// A keycap: shows a shortcut ("Ctrl+K") as small raised keys.
Row {
    id: kbd
    property string keys: ""
    spacing: 3
    Repeater {
        model: kbd.keys === "" ? [] : kbd.keys.split("+")
        delegate: Rectangle {
            required property string modelData
            width: Math.max(18, kt.implicitWidth + 9); height: 18; radius: 4
            color: Theme.raised; border.color: Theme.line
            Text { id: kt; anchors.centerIn: parent; text: parent.modelData; color: Theme.dim
                   font.pixelSize: Theme.fsTiny; font.family: Theme.mono }
        }
    }
}
