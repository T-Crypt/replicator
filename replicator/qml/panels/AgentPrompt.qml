import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Replicator.UI

// A one-line request to the local model about one part ("make the bell longer", "add 24 cooling tubes").
// The edit is scoped: the model may only change this component's ops, and anything else it touches is refused.
Popup {
    id: box
    property string cid: ""
    property string label: ""
    signal submitted(string cid, string text)
    parent: Overlay.overlay
    anchors.centerIn: parent
    width: 560
    modal: true
    padding: 16
    background: Rectangle { radius: Theme.r3; color: Theme.raised; border.color: Theme.accentLine }
    onOpened: { field.text = ""; field.forceActiveFocus() }
    function submit() {
        if (field.text.trim() === "") return
        box.submitted(box.cid, field.text.trim())
        box.close()
    }
    contentItem: ColumnLayout {
        spacing: 10
        RowLayout {
            spacing: 8
            Icon { name: "sparkle"; size: 16; color: Theme.accentHi }
            Text { text: "Rework " + box.label; color: Theme.text; font.pixelSize: Theme.fsLarge; font.family: Theme.sans; font.weight: Font.DemiBold
                   Layout.fillWidth: true; elide: Text.ElideRight }
            Text { text: studio.busy === "" ? "" : "busy: " + studio.busy; color: Theme.inferred; font.pixelSize: Theme.fsTiny }
        }
        TextField {
            id: field
            Layout.fillWidth: true
            placeholderText: "What should change? e.g. \"make it 20 % longer\", \"add 12 bolts around the flange\""
            font.pixelSize: Theme.fs
            onAccepted: box.submit()
        }
        Text {
            Layout.fillWidth: true; wrapMode: Text.WordWrap
            text: "Only this part's operations can change; an edit that touches anything else is refused. The result is one undo step."
            color: Theme.dim; font.pixelSize: Theme.fsTiny; font.family: Theme.sans
        }
        RowLayout {
            Layout.alignment: Qt.AlignRight
            spacing: 8
            Pill { text: "Cancel"; onHit: box.close() }
            Pill { text: "Rework"; icon: "sparkle"; primary: true; enabled: studio.busy === "" && field.text.trim() !== ""; onHit: box.submit() }
        }
    }
}
