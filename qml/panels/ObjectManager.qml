import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Replicator.UI

// Object Manager: components (colour, name, part count) with their parts beneath. Row buttons appear on hover:
// play how it is made, isolate, hide. Double-click isolates.
Rectangle {
    id: om
    color: Theme.panel
    property var hidden: ({})
    property string isolate: ""
    signal toggleHidden(string cid)
    signal isolateComponent(string cid)
    signal playComponent(string cid)
    property var expanded: ({})

    ListView {
        id: list
        anchors.fill: parent
        anchors.topMargin: 4
        clip: true
        model: studio.components
        boundsBehavior: Flickable.StopAtBounds
        ScrollBar.vertical: ScrollBar {}
        delegate: Column {
            id: row
            required property var modelData
            required property int index
            width: list.width
            readonly property bool open: om.expanded[modelData.id] === true
            readonly property bool sel: studio.selectedComponent === modelData.id || studio.selected === modelData.id
            readonly property bool off: om.hidden[modelData.id] === true
            readonly property bool solo: om.isolate === modelData.id
            Item {
                width: row.width; height: Theme.row
                Rectangle {
                    anchors.fill: parent; anchors.leftMargin: 4; anchors.rightMargin: 4; radius: Theme.r1
                    color: row.sel ? Theme.accentSoft : hov.containsMouse ? Theme.hover : "transparent"
                }
                Rectangle { visible: row.sel; x: 4; width: 2; height: parent.height - 10; anchors.verticalCenter: parent.verticalCenter; radius: 1; color: Theme.accent }
                MouseArea {
                    id: hov; anchors.fill: parent; hoverEnabled: true
                    onClicked: studio.select(row.modelData.id)
                    onDoubleClicked: om.isolateComponent(row.solo ? "" : row.modelData.id)
                }
                RowLayout {
                    anchors.fill: parent; anchors.leftMargin: 10; anchors.rightMargin: 8; spacing: 6
                    Item {
                        implicitWidth: 14; implicitHeight: 14
                        Icon { anchors.centerIn: parent; name: row.open ? "chevronDown" : "chevronRight"; size: 11; color: Theme.faint }
                        MouseArea { anchors.fill: parent; anchors.margins: -5
                            onClicked: { const e = Object.assign({}, om.expanded); e[row.modelData.id] = !row.open; om.expanded = e } }
                    }
                    Rectangle { width: 10; height: 10; radius: 3; color: row.modelData.color; opacity: row.off ? 0.35 : 1 }
                    Text {
                        Layout.fillWidth: true; text: row.modelData.label; elide: Text.ElideRight
                        color: row.off ? Theme.faint : Theme.text; font.pixelSize: Theme.fs; font.family: Theme.sans
                    }
                    Text { text: row.modelData.count; color: Theme.faint; font.pixelSize: Theme.fsTiny; font.family: Theme.mono
                           visible: !hov.containsMouse && !row.solo && !row.off }
                    IconButton { size: 22; iconSize: 12; icon: "play"; tip: "Play how this component is made"
                                 visible: hov.containsMouse || containsHover; property bool containsHover: false
                                 onHit: om.playComponent(row.modelData.id) }
                    IconButton { size: 22; iconSize: 13; icon: "target"; tip: "Isolate"; on: row.solo
                                 visible: hov.containsMouse || row.solo
                                 onHit: om.isolateComponent(row.solo ? "" : row.modelData.id) }
                    IconButton { size: 22; iconSize: 13; icon: row.off ? "eyeOff" : "eye"; tip: row.off ? "Show" : "Hide"
                                 visible: hov.containsMouse || row.off
                                 onHit: om.toggleHidden(row.modelData.id) }
                }
            }
            Repeater {
                model: row.open ? row.modelData.shapes : []
                delegate: Item {
                    id: leaf
                    required property var modelData
                    width: row.width; height: Theme.row - 4
                    Rectangle {
                        anchors.fill: parent; anchors.leftMargin: 4; anchors.rightMargin: 4; radius: Theme.r1
                        color: studio.selected === leaf.modelData ? Theme.accentSoft : pm.containsMouse ? Theme.hover : "transparent"
                    }
                    Rectangle { x: 23; width: 1; height: parent.height; color: Theme.lineSoft }
                    Text {
                        x: 40; anchors.verticalCenter: parent.verticalCenter
                        text: leaf.modelData; color: studio.selected === leaf.modelData ? Theme.text : Theme.dim
                        font.pixelSize: Theme.fsSmall; font.family: Theme.mono
                    }
                    MouseArea { id: pm; anchors.fill: parent; hoverEnabled: true; onClicked: studio.select(leaf.modelData) }
                }
            }
        }
    }
    Column {
        anchors.centerIn: parent; visible: studio.components.length === 0; spacing: 8
        Icon { name: "layers"; size: 26; color: Theme.faint; anchors.horizontalCenter: parent.horizontalCenter }
        Text {
            text: "No objects yet.\nDream one, add a primitive,\nor import a model."
            horizontalAlignment: Text.AlignHCenter; color: Theme.faint; font.pixelSize: Theme.fs; font.family: Theme.sans; lineHeight: 1.3
        }
    }
}
