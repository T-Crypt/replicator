import QtQuick
import QtQuick.Layouts

// The title strip of a dock panel: an icon, a small-caps title, an optional count and trailing buttons.
Rectangle {
    id: dh
    property string title: ""
    property string icon: ""
    property string count: ""
    default property alias trailing: tail.data
    Layout.fillWidth: true
    implicitHeight: Theme.bar
    color: Theme.header
    Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: 1; color: Theme.line }
    Row {
        x: Theme.pad; anchors.verticalCenter: parent.verticalCenter; spacing: 7
        Icon { visible: dh.icon !== ""; name: dh.icon; size: 14; color: Theme.dim; anchors.verticalCenter: parent.verticalCenter }
        Text { text: dh.title.toUpperCase(); color: Theme.dim; anchors.verticalCenter: parent.verticalCenter
               font.pixelSize: Theme.fsTiny; font.family: Theme.sans; font.weight: Font.DemiBold; font.letterSpacing: Theme.caps }
        Rectangle {
            visible: dh.count !== ""; anchors.verticalCenter: parent.verticalCenter
            width: ct.implicitWidth + 10; height: 15; radius: 7.5; color: Theme.panel2
            Text { id: ct; anchors.centerIn: parent; text: dh.count; color: Theme.dim; font.pixelSize: 9; font.family: Theme.mono }
        }
    }
    Row { id: tail; anchors.right: parent.right; anchors.rightMargin: 4; anchors.verticalCenter: parent.verticalCenter; spacing: 1 }
}
