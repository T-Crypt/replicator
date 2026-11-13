import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

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
        RowLayout {
            spacing: 6
            Pill { text: "Import model…"; primary: true; onHit: lp.importRequested() }
            Pill { text: "Disassemble"; onHit: lp.disassemble() }
            Pill {
                text: studio.busy.indexOf("Naming") === 0 ? "Naming…" : "Name parts"
                enabled: studio.busy === "" && studio.components.length > 0
                onHit: studio.nameParts()
            }
        }
        Text {
            text: (studio.reportInput.file || "No model") + (studio.reportInput.format ? "  ·  " + studio.reportInput.format : "")
            color: Theme.text; font.pixelSize: Theme.fs; font.bold: true
        }
        Text {
            text: "CHECKLIST"; color: Theme.faint; font.pixelSize: 10; font.letterSpacing: 1.5
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
        Text { text: "EVIDENCE LEDGER"; color: Theme.faint; font.pixelSize: 10; font.letterSpacing: 1.5; Layout.topMargin: 6 }
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
                radius: 4
                color: Theme.panel2
                border.color: studio.selected !== "" && modelData.subject === studio.selected ? Theme.amber : "transparent"
                ColumnLayout {
                    id: body
                    x: 8; y: 5; width: parent.width - 16
                    spacing: 2
                    RowLayout {
                        spacing: 6
                        Rectangle {
                            implicitWidth: tag.implicitWidth + 10; implicitHeight: 15; radius: 3
                            color: modelData.kind === "observed" ? "#1f3a28" : modelData.kind === "inferred" ? "#3d3220" : "#2c2e33"
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
                    Text { text: modelData.claim; color: Theme.text; font.pixelSize: Theme.fsSmall; wrapMode: Text.WordWrap; Layout.fillWidth: true }
                    Text { text: "← " + modelData.evidence; color: Theme.dim; font.pixelSize: 10; wrapMode: Text.WordWrap; Layout.fillWidth: true }
                }
                MouseArea { anchors.fill: parent; onClicked: if (modelData.subject && modelData.subject.indexOf("pattern") < 0) studio.select(modelData.subject) }
            }
        }
    }
}
