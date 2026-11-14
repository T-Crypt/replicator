import QtQuick
import QtQuick.Layouts
import Replicator.UI

// The start screen, shown while nothing is open: the tagline, a slot the dream capsule floats into, three ways in
// (open, reverse engineer, picture to 3D), the bundled examples and the most recent builds.
Item {
    id: w
    signal openFile(string path)
    signal runAction(string id)
    readonly property real capsuleY: col.y + slot.y + 4      // Main.qml parks the dream capsule here

    readonly property var kinds: ({ example: ["Example", "build"], dream: ["Dream", "sparkle"],
                                    reverse: ["Reverse", "reverse"], image: ["Image to 3D", "image"] })

    Flickable {
        anchors.fill: parent
        contentHeight: col.y + col.height + 40
        clip: true
        boundsBehavior: Flickable.StopAtBounds
        Column {
            id: col
            width: Math.min(parent.width - 80, 1040)
            anchors.horizontalCenter: parent.horizontalCenter
            y: Math.max(36, w.height * 0.11)
            spacing: 0

            Text {
                anchors.horizontalCenter: parent.horizontalCenter
                text: "You dream it, you build it."
                color: Theme.viewText; font.family: Theme.sans; font.pixelSize: 38; font.weight: Font.DemiBold
                font.letterSpacing: -0.6
            }
            Item { width: 1; height: 10 }
            Text {
                anchors.horizontalCenter: parent.horizontalCenter
                width: Math.min(parent.width, 640); horizontalAlignment: Text.AlignHCenter; wrapMode: Text.WordWrap
                text: "Describe an object. A local model plans it, writes the build program, and it assembles on the floor one step at a time."
                color: Theme.viewDim; font.family: Theme.sans; font.pixelSize: 14; lineHeight: 1.35
            }
            Item { width: 1; height: 28 }
            Item { id: slot; width: 1; height: 62 }      // the dream capsule lands here
            Item { width: 1; height: 22 }

            Row {
                anchors.horizontalCenter: parent.horizontalCenter
                spacing: 10
                Repeater {
                    model: [ ["open", "folder", "Open a build", "Ctrl+O"], ["import", "importIn", "Take a model apart", "Ctrl+I"],
                             ["image3d", "image", "Picture to 3D", "Ctrl+Shift+I"], ["commander", "search", "Every action", "Ctrl+K"] ]
                    delegate: Rectangle {
                        required property var modelData
                        width: tRow.implicitWidth + 30; height: 38; radius: 19
                        color: tMa.containsMouse ? Theme.hover : "transparent"
                        border.color: tMa.containsMouse ? Theme.accentLine : Theme.glassLine
                        Row {
                            id: tRow
                            anchors.centerIn: parent; spacing: 8
                            Icon { name: modelData[1]; size: 15; color: Theme.accentHi; anchors.verticalCenter: parent.verticalCenter }
                            Text { text: modelData[2]; color: Theme.viewText; font.pixelSize: Theme.fs; font.family: Theme.sans
                                   font.weight: Font.Medium; anchors.verticalCenter: parent.verticalCenter }
                            Kbd { keys: modelData[3]; anchors.verticalCenter: parent.verticalCenter }
                        }
                        MouseArea { id: tMa; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                                    onClicked: w.runAction(modelData[0]) }
                    }
                }
            }
            Item { width: 1; height: 40 }

            Repeater {
                model: [ ["EXAMPLES", studio.examples], ["RECENT", studio.recents] ]
                delegate: Column {
                    id: sect
                    required property var modelData
                    width: col.width
                    visible: modelData[1].length > 0
                    spacing: 10
                    bottomPadding: 26
                    Text { text: sect.modelData[0]; color: Theme.viewDim; font.pixelSize: Theme.fsTiny; font.family: Theme.sans
                           font.weight: Font.DemiBold; font.letterSpacing: 1.8 }
                    Grid {
                        id: grid
                        columns: Math.max(1, Math.floor((col.width + 12) / 252))
                        spacing: 12
                        Repeater {
                            model: sect.modelData[1]
                            delegate: Rectangle {
                                id: card
                                required property var modelData
                                width: (col.width - (grid.columns - 1) * 12) / grid.columns; height: 104; radius: Theme.r3
                                color: cMa.containsMouse ? Theme.raised : Theme.glass
                                border.color: cMa.containsMouse ? Theme.accentLine : Theme.glassLine
                                Behavior on color { ColorAnimation { duration: Theme.fast } }
                                scale: cMa.pressed ? 0.985 : 1
                                Behavior on scale { NumberAnimation { duration: Theme.fast } }
                                ColumnLayout {
                                    anchors.fill: parent; anchors.margins: 13
                                    spacing: 5
                                    RowLayout {
                                        spacing: 6
                                        Icon { name: w.kinds[card.modelData.kind][1]; size: 13; color: Theme.accentHi }
                                        Text { text: w.kinds[card.modelData.kind][0].toUpperCase(); color: Theme.accentHi
                                               font.pixelSize: 9; font.family: Theme.sans; font.weight: Font.Bold; font.letterSpacing: 1.2 }
                                        Item { Layout.fillWidth: true }
                                        Text { text: card.modelData.when; color: Theme.faint; font.pixelSize: 9; font.family: Theme.mono
                                               visible: card.modelData.kind !== "example" }
                                    }
                                    Text { text: card.modelData.name; color: Theme.text; font.pixelSize: Theme.fsLarge; font.family: Theme.sans
                                           font.weight: Font.DemiBold; elide: Text.ElideRight; Layout.fillWidth: true }
                                    Item { Layout.fillHeight: true }
                                    Text { text: card.modelData.steps + (card.modelData.steps === 1 ? " step  ·  " : " steps  ·  ") + card.modelData.components + (card.modelData.components === 1 ? " component" : " components")
                                           color: Theme.dim; font.pixelSize: Theme.fsSmall; font.family: Theme.sans }
                                    Text { text: card.modelData.ops; color: Theme.faint; font.pixelSize: Theme.fsTiny; font.family: Theme.mono
                                           elide: Text.ElideRight; Layout.fillWidth: true }
                                }
                                MouseArea { id: cMa; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                                            onClicked: w.openFile(card.modelData.path) }
                            }
                        }
                    }
                }
            }
        }
    }
}
