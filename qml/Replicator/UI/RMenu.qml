import QtQuick
import QtQuick.Controls

// A themed drop-down menu fed from the action registry. `actions` is a list of action objects
// ({ title, keys, icon, run, enabled, checked }) or the string "-" for a separator.
Popup {
    id: menu
    property var actions: []
    padding: 5
    implicitWidth: 286
    background: Rectangle { radius: Theme.r3; color: Theme.raised; border.color: Theme.line }
    enter: Transition { NumberAnimation { property: "opacity"; from: 0; to: 1; duration: Theme.fast } }
    contentItem: Column {
        spacing: 1
        Repeater {
            model: menu.actions
            delegate: Item {
                id: it
                required property var modelData
                readonly property bool sep: modelData === "-"
                readonly property bool ok: !sep && (modelData.enabled === undefined || modelData.enabled)
                width: menu.availableWidth
                height: sep ? 9 : Theme.row
                Rectangle { visible: it.sep; anchors.centerIn: parent; width: parent.width - 12; height: 1; color: Theme.line }
                Rectangle { visible: !it.sep && mma.containsMouse && it.ok; anchors.fill: parent; radius: Theme.r1; color: Theme.accentSoft }
                Icon { visible: !it.sep; x: 8; anchors.verticalCenter: parent.verticalCenter
                       name: it.sep ? "" : (it.modelData.checked ? "check" : (it.modelData.icon || ""))
                       size: 15; color: it.modelData.checked ? Theme.accentHi : Theme.dim; opacity: it.ok ? 1 : 0.4 }
                Text { visible: !it.sep; x: 32; anchors.verticalCenter: parent.verticalCenter
                       text: it.sep ? "" : it.modelData.title; color: Theme.text; opacity: it.ok ? 1 : 0.4
                       font.pixelSize: Theme.fs; font.family: Theme.sans }
                Text { visible: !it.sep; anchors.right: parent.right; anchors.rightMargin: 10; anchors.verticalCenter: parent.verticalCenter
                       text: it.sep ? "" : (it.modelData.keys || ""); color: Theme.faint
                       font.pixelSize: Theme.fsTiny; font.family: Theme.mono }
                MouseArea { id: mma; anchors.fill: parent; hoverEnabled: true; enabled: !it.sep
                            onClicked: if (it.ok) { menu.close(); it.modelData.run() } }
            }
        }
    }
}
