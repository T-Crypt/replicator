import QtQuick

// A segmented switch with a sliding thumb. model: [{ key, label, icon?, hint? }]. `current` is the selected key.
Rectangle {
    id: seg
    property var model: []
    property string current: ""
    property real segWidth: 104
    property bool iconsOnly: false
    signal pick(string key)
    implicitWidth: model.length * segWidth + 6
    implicitHeight: Theme.ctl + 6
    radius: height / 2
    color: Theme.field
    border.color: Theme.line

    readonly property int index: { for (let i = 0; i < model.length; i++) if (model[i].key === current) return i; return -1 }
    Rectangle {   // thumb
        visible: seg.index >= 0
        x: 3 + seg.index * seg.segWidth; y: 3
        width: seg.segWidth; height: parent.height - 6; radius: height / 2
        color: Theme.accent
        Behavior on x { NumberAnimation { duration: Theme.med; easing.type: Easing.OutCubic } }
    }
    Row {
        x: 3; y: 3
        Repeater {
            model: seg.model
            delegate: Item {
                id: cell
                required property var modelData
                required property int index
                readonly property bool sel: seg.current === modelData.key
                width: seg.segWidth; height: seg.height - 6
                Rectangle { anchors.fill: parent; radius: height / 2; color: Theme.hover; visible: sma.containsMouse && !cell.sel }
                Row {
                    anchors.centerIn: parent
                    spacing: 6
                    Icon { visible: !!cell.modelData.icon; name: cell.modelData.icon || ""; size: 15
                           anchors.verticalCenter: parent.verticalCenter
                           color: cell.sel ? Theme.onAccent : sma.containsMouse ? Theme.text : Theme.dim }
                    Text { visible: !seg.iconsOnly; text: cell.modelData.label || ""
                           anchors.verticalCenter: parent.verticalCenter
                           color: cell.sel ? Theme.onAccent : sma.containsMouse ? Theme.text : Theme.dim
                           font.pixelSize: Theme.fs; font.family: Theme.sans
                           font.weight: cell.sel ? Font.DemiBold : Font.Medium }
                    Text { visible: !seg.iconsOnly && !!cell.modelData.hint; text: cell.modelData.hint || ""
                           anchors.verticalCenter: parent.verticalCenter
                           color: cell.sel ? Qt.rgba(Theme.onAccent.r, Theme.onAccent.g, Theme.onAccent.b, 0.55) : Theme.faint
                           font.pixelSize: Theme.fsTiny; font.family: Theme.mono }
                }
                MouseArea { id: sma; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                            onClicked: seg.pick(cell.modelData.key) }
            }
        }
    }
}
