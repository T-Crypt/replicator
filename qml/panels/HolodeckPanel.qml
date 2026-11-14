import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Replicator.UI

// Holodeck character sheets (the operator's ComfyUI character console, newest first). Pick a sheet and turn it
// into a 3D model via Hunyuan3D in ComfyUI (one Berth batch, the app stays on the iGPU): "Make 3D (sheet)" runs
// the multi-view model over the sheet's labelled views, "Front only" the single-image model on the front.
// The result loads as a reverse-engineering project. Shown in Reverse mode above the evidence ledger, collapsed
// until asked for: the newest sheet has nothing to do with whatever model is being reversed.
Rectangle {
    id: hp
    color: "transparent"
    implicitHeight: open ? 188 : 34
    property bool open: false
    property int selected: 0
    readonly property bool canRun: studio.busy === "" && studio.holodeckSheets.length > 0

    function sheet() {
        const rows = studio.holodeckSheets
        if (!rows.length)
            return null
        return rows[Math.min(selected, rows.length - 1)]
    }

    Connections {
        target: studio
        function onHolodeckChanged() {   // a sheet vanished: keep the selection on something
            if (hp.selected >= studio.holodeckSheets.length)
                hp.selected = Math.max(0, studio.holodeckSheets.length - 1)
        }
    }

    Rectangle { anchors.top: parent.top; width: parent.width; height: 1; color: Theme.line }

    ColumnLayout {
        anchors.fill: parent
        anchors.topMargin: 6; anchors.leftMargin: 10; anchors.rightMargin: 10; anchors.bottomMargin: 8
        spacing: 6

        RowLayout {
            Layout.fillWidth: true
            spacing: 6
            Icon { name: hp.open ? "chevronDown" : "chevronRight"; size: 11; color: Theme.faint }
            Text {
                Layout.fillWidth: true
                text: "MAKE 3D FROM A HOLODECK SHEET" + (studio.holodeckSheets.length ? "  (" + studio.holodeckSheets.length + ")" : "")
                color: Theme.faint; font.pixelSize: Theme.fsTiny; font.family: Theme.sans; font.weight: Font.DemiBold; font.letterSpacing: Theme.caps
            }
            TapHandler { onTapped: hp.open = !hp.open }
        }
        Text {
            visible: hp.open && studio.holodeckSheets.length === 0
            text: "No character sheets in the Holodeck output folder. File > Image to 3D… works with any picture."
            color: Theme.faint; font.pixelSize: Theme.fsSmall; wrapMode: Text.WordWrap; Layout.fillWidth: true
        }

        Flickable {
            Layout.fillWidth: true
            Layout.preferredHeight: 56
            clip: true
            visible: hp.open && studio.holodeckSheets.length > 0
            flickableDirection: Flickable.HorizontalFlick
            boundsBehavior: Flickable.StopAtBounds
            contentWidth: thumbs.width + 1

            Row {
                id: thumbs
                spacing: 6
                Repeater {
                    model: studio.holodeckSheets
                    delegate: Rectangle {
                        required property var modelData
                        required property int index
                        width: 56; height: 56; radius: Theme.r2
                        color: Theme.field
                        border.width: 2
                        border.color: hp.selected === index ? Theme.accent : Theme.line
                        Image {
                            anchors.fill: parent; anchors.margins: 2; clip: true
                            source: "file://" + modelData.path
                            asynchronous: true
                            cache: false   // sheets are regenerated in place; a cached copy would be stale
                            fillMode: Image.PreserveAspectCrop
                        }
                        MouseArea { anchors.fill: parent; onClicked: hp.selected = index }
                    }
                }
            }
        }

        Text {
            visible: hp.open && hp.sheet() !== null
            text: hp.sheet() ? (hp.sheet().subject || hp.sheet().name) : ""
            color: Theme.text; font.pixelSize: Theme.fsSmall; Layout.fillWidth: true
            wrapMode: Text.WordWrap; maximumLineCount: 2; elide: Text.ElideRight
        }

        RowLayout {
            visible: hp.open && studio.holodeckSheets.length > 0
            spacing: 6
            Pill {
                icon: "sparkle"
                text: "Make 3D (sheet)"
                primary: true
                enabled: hp.canRun
                onHit: studio.imageTo3D(hp.sheet().path, false)
            }
            Pill {
                icon: "image"
                text: "Front only"
                enabled: hp.canRun
                onHit: studio.imageTo3D(hp.sheet().path, true)
            }
        }
    }
}
