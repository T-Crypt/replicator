import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Replicator.UI

// Reverse engineering: the evidence ledger (observed / inferred / unknown, each with its evidence) and the
// checklist of questions with their status. A guess is never shown as a measurement.
Rectangle {
    id: lp
    color: Theme.panel
    signal importRequested()
    signal disassemble()

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 10
        spacing: 8
        Flow {
            Layout.fillWidth: true
            spacing: 6
            Pill { text: "Import model…"; icon: "importIn"; primary: true; onHit: lp.importRequested() }
            Pill { text: "Disassemble"; icon: "playBack"; onHit: lp.disassemble() }
            Pill {
                visible: studio.reportInput.suggested_scale !== undefined && studio.dimensions.length === 3
                         && Math.max(studio.dimensions[0], studio.dimensions[1], studio.dimensions[2]) < 2
                icon: "ruler"
                text: "Metres → mm (×1000)"
                enabled: studio.busy === ""
                onHit: studio.rescale(studio.reportInput.suggested_scale)
            }
            Pill {
                icon: "sparkle"
                text: studio.busy.indexOf("Naming") === 0 ? "Naming…" : "Name parts"
                enabled: studio.busy === "" && studio.components.length > 0
                onHit: studio.nameParts()
            }
        }
        Text {
            text: (studio.reportInput.file || "No model") + (studio.reportInput.format ? "  ·  " + studio.reportInput.format : "")
            color: Theme.text; font.pixelSize: Theme.fs; font.family: Theme.sans; font.weight: Font.DemiBold
            elide: Text.ElideMiddle; Layout.fillWidth: true
        }
        Text {
            text: "CHECKLIST"; color: Theme.faint; font.pixelSize: Theme.fsTiny; font.family: Theme.sans; font.weight: Font.DemiBold; font.letterSpacing: Theme.caps
        }
        Repeater {
            model: studio.checklist
            delegate: RowLayout {
                required property var modelData
                Layout.fillWidth: true
                spacing: 6
                Rectangle {
                    width: 8; height: 8; radius: 4
                    color: modelData.status.indexOf("unresolved") === 0 ? Theme.unknown
                         : modelData.status.indexOf("partly") === 0 ? Theme.inferred : Theme.observed
                }
                Text { text: modelData.q; color: Theme.text; font.pixelSize: Theme.fsSmall; Layout.fillWidth: true; elide: Text.ElideRight }
                Text { text: modelData.status; color: Theme.dim; font.pixelSize: 10 }
            }
        }
        Text { text: "EVIDENCE LEDGER"; color: Theme.faint; font.pixelSize: Theme.fsTiny; font.family: Theme.sans; font.weight: Font.DemiBold; font.letterSpacing: Theme.caps; Layout.topMargin: 6 }
        ListView {
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            spacing: 4
            model: studio.ledger
            ScrollBar.vertical: ScrollBar {}
            delegate: Rectangle {
                required property var modelData
                width: ListView.view.width - 8
                height: body.implicitHeight + 10
                radius: Theme.r2
                color: Theme.panel2
                border.color: studio.selected !== "" && modelData.subject === studio.selected ? Theme.amber : Theme.lineSoft
                Rectangle {   // evidence class stripe
                    x: 0; y: 6; width: 2; height: parent.height - 12; radius: 1
                    color: modelData.kind === "observed" ? Theme.observed : modelData.kind === "inferred" ? Theme.inferred : Theme.unknown
                }
                ColumnLayout {
                    id: body
                    x: 8; y: 5; width: parent.width - 16
                    spacing: 2
                    RowLayout {
                        spacing: 6
                        Rectangle {
                            implicitWidth: tag.implicitWidth + 10; implicitHeight: 15; radius: 3
                            readonly property color kc: modelData.kind === "observed" ? Theme.observed : modelData.kind === "inferred" ? Theme.inferred : Theme.unknown
                            color: Qt.rgba(kc.r, kc.g, kc.b, 0.16)
                            Text {
                                id: tag; anchors.centerIn: parent; text: modelData.kind.toUpperCase()
                                color: modelData.kind === "observed" ? Theme.observed : modelData.kind === "inferred" ? Theme.inferred : Theme.unknown
                                font.pixelSize: 9; font.bold: true; font.letterSpacing: 1
                            }
                        }
                        Text {
                            visible: modelData.confidence !== undefined
                            text: "conf " + (modelData.confidence !== undefined ? modelData.confidence.toFixed(2) : "")
                            color: Theme.faint; font.pixelSize: 9; font.family: Theme.mono
                        }
                        Text { visible: modelData.subject !== ""; text: modelData.subject; color: Theme.faint; font.pixelSize: 9; font.family: Theme.mono }
                    }
                    Text { text: modelData.claim; color: Theme.text; font.pixelSize: Theme.fsSmall; font.family: Theme.sans; wrapMode: Text.WordWrap; Layout.fillWidth: true }
                    Text { text: "← " + modelData.evidence; color: Theme.dim; font.pixelSize: Theme.fsTiny; font.family: Theme.sans; wrapMode: Text.WordWrap; Layout.fillWidth: true }
                }
                MouseArea { anchors.fill: parent; onClicked: if (modelData.subject && modelData.subject.indexOf("pattern") < 0) studio.select(modelData.subject) }
            }
        }
    }
}
