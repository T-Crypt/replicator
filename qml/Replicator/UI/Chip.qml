import QtQuick

// A read-out: a small-caps label and a monospace value, for the status bar and the viewport HUD.
Row {
    id: chip
    property string label: ""
    property string value: ""
    property string icon: ""
    property color valueColor: Theme.text
    property color labelColor: Theme.faint
    spacing: 5
    Icon { visible: chip.icon !== ""; name: chip.icon; size: 13; color: chip.labelColor; anchors.verticalCenter: parent.verticalCenter }
    Text { visible: chip.label !== ""; text: chip.label; color: chip.labelColor; anchors.verticalCenter: parent.verticalCenter
           font.pixelSize: Theme.fsTiny; font.family: Theme.sans; font.letterSpacing: 1.1; font.weight: Font.DemiBold }
    Text { text: chip.value; color: chip.valueColor; anchors.verticalCenter: parent.verticalCenter
           font.pixelSize: Theme.fsSmall; font.family: Theme.mono }
}
