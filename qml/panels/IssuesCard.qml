import QtQuick
import QtQuick.Layouts
import Replicator.UI

// The accuracy critic's findings for the current build, measured from the geometry. A "fix" issue is a real defect
// (wrong axis, floating, buried); a "warn" is worth a look. Click one to select and frame its part.
Rectangle {
    id: card
    property bool open: false
    signal chosen(string cid)
    readonly property var issues: studio.issues
    readonly property int fixes: issues.filter(i => i.severity === "fix").length
    readonly property color tone: fixes ? Theme.danger : issues.length ? Theme.inferred : Theme.observed
    width: open ? 380 : head.implicitWidth + 22
    height: open ? Math.min(col.implicitHeight + 16, 340) : 28
    radius: open ? Theme.r3 : 14
    color: Theme.glass
    border.color: Qt.rgba(tone.r, tone.g, tone.b, 0.55)
    clip: true
    Behavior on height { NumberAnimation { duration: Theme.fast } }

    ColumnLayout {
        id: col
        x: 11; y: 6; width: card.width - 22
        spacing: 6
        RowLayout {
            id: head
            spacing: 6
            Icon { name: card.issues.length ? "alert" : "check"; size: 14; color: card.tone }
            Text {
                text: card.issues.length === 0 ? "Accuracy checks pass"
                    : (card.fixes ? card.fixes + " to fix" : "") + (card.fixes && card.issues.length > card.fixes ? ", " : "")
                      + (card.issues.length > card.fixes ? (card.issues.length - card.fixes) + " to review" : "")
                color: Theme.viewText; font.pixelSize: Theme.fsSmall; font.family: Theme.sans; font.weight: Font.DemiBold
            }
            Icon { visible: card.issues.length > 0; name: card.open ? "chevronDown" : "chevronRight"; size: 11; color: Theme.viewDim }
            MouseArea { Layout.fillWidth: true; implicitHeight: 1 }
        }
        Repeater {
            model: card.open ? card.issues : []
            delegate: Rectangle {
                id: it
                required property var modelData
                Layout.fillWidth: true
                implicitHeight: msg.implicitHeight + 10
                radius: Theme.r1
                color: ima.containsMouse ? Theme.hover : "transparent"
                Rectangle { x: 0; y: 5; width: 2; height: parent.height - 10; radius: 1
                            color: it.modelData.severity === "fix" ? Theme.danger : Theme.inferred }
                Text {
                    id: msg
                    x: 9; y: 5; width: parent.width - 12
                    text: it.modelData.message; wrapMode: Text.WordWrap
                    color: Theme.viewText; font.pixelSize: Theme.fsTiny; font.family: Theme.sans
                }
                MouseArea { id: ima; anchors.fill: parent; hoverEnabled: true; enabled: it.modelData.subject !== ""
                            cursorShape: Qt.PointingHandCursor; onClicked: card.chosen(it.modelData.subject) }
            }
        }
        Pill {
            visible: card.open && card.fixes > 0
            text: studio.busy.indexOf("Fixing") === 0 ? "Fixing…" : "Fix with the agent"
            icon: "sparkle"; primary: true
            enabled: studio.busy === ""
            onHit: studio.fixIssues()
        }
    }
    MouseArea {
        width: card.width; height: 28
        enabled: card.issues.length > 0
        cursorShape: Qt.PointingHandCursor
        onClicked: card.open = !card.open
    }
}
