import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// Object Manager: components (colour, name, part count) with their parts beneath. Eye = hide, target = isolate.
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
            Rectangle {
                width: row.width; height: 28
                color: row.sel ? "#2f4a66" : hov.containsMouse ? Theme.panel2 : "transparent"
                MouseArea {
                    id: hov; anchors.fill: parent; hoverEnabled: true
                    onClicked: studio.select(row.modelData.id)
                    onDoubleClicked: om.isolateComponent(om.isolate === row.modelData.id ? "" : row.modelData.id)
                }
                RowLayout {
                    anchors.fill: parent; anchors.leftMargin: 6; anchors.rightMargin: 6; spacing: 6
                    Text {
                        text: row.open ? "▾" : "▸"; color: Theme.dim; font.pixelSize: 11
                        MouseArea { anchors.fill: parent; anchors.margins: -4
                            onClicked: { const e = Object.assign({}, om.expanded); e[row.modelData.id] = !row.open; om.expanded = e } }
                    }
                    Rectangle { width: 10; height: 10; radius: 2; color: row.modelData.color }
                    Text {
                        Layout.fillWidth: true; text: row.modelData.label; elide: Text.ElideRight
                        color: om.hidden[row.modelData.id] ? Theme.faint : Theme.text; font.pixelSize: Theme.fs
                    }
                    Text { text: row.modelData.count; color: Theme.faint; font.pixelSize: 10 }
                    Text {   // play how it's made
                        text: "▶"; color: playMa.containsMouse ? Theme.holo : Theme.faint; font.pixelSize: 10
                        MouseArea { id: playMa; anchors.fill: parent; anchors.margins: -4; hoverEnabled: true
                            onClicked: om.playComponent(row.modelData.id) }
                        ToolTip.visible: playMa.containsMouse; ToolTip.text: "Play how this component is made"
                    }
                    Text {   // isolate
                        text: "◎"; color: om.isolate === row.modelData.id ? Theme.holo : Theme.faint; font.pixelSize: 12
                        MouseArea { anchors.fill: parent; anchors.margins: -4
                            onClicked: om.isolateComponent(om.isolate === row.modelData.id ? "" : row.modelData.id) }
                    }
                    Text {   // visibility
                        text: om.hidden[row.modelData.id] ? "○" : "●"
                        color: om.hidden[row.modelData.id] ? Theme.faint : Theme.dim; font.pixelSize: 11
                        MouseArea { anchors.fill: parent; anchors.margins: -4; onClicked: om.toggleHidden(row.modelData.id) }
                    }
                }
            }
            Repeater {
                model: row.open ? row.modelData.shapes : []
                delegate: Rectangle {
                    required property var modelData
                    width: row.width; height: 24
                    color: studio.selected === modelData ? "#2f4a66" : pm.containsMouse ? Theme.panel2 : "transparent"
                    Text {
                        x: 40; anchors.verticalCenter: parent.verticalCenter
                        text: "◆  " + parent.modelData; color: Theme.dim; font.pixelSize: Theme.fsSmall
                    }
                    MouseArea { id: pm; anchors.fill: parent; hoverEnabled: true; onClicked: studio.select(parent.modelData) }
                }
            }
        }
    }
    Text {
        anchors.centerIn: parent; visible: studio.components.length === 0
        text: "No objects yet.\nDream one, add a primitive,\nor import a model."
        horizontalAlignment: Text.AlignHCenter; color: Theme.faint; font.pixelSize: Theme.fs
    }
}
