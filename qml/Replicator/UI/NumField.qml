import QtQuick
import QtQuick.Controls

// A DCC-style number field: drag on it horizontally to scrub (Shift = fine, Ctrl = coarse), click to type.
Rectangle {
    id: f
    property real value: 0
    property string label: ""
    property color labelColor: Theme.dim
    property real stepSize: 1
    property int decimals: 2
    signal committed(real v)
    implicitHeight: Theme.ctl - 2
    implicitWidth: 80
    radius: Theme.r1
    color: Theme.field
    border.color: input.activeFocus ? Theme.accent : drag.containsMouse ? Theme.accentLine : Theme.line

    property real _shown: value
    onValueChanged: if (!drag.active && !input.activeFocus) _shown = value

    Rectangle {   // axis stripe
        visible: f.label !== ""
        width: 2; height: parent.height - 8; x: 4; anchors.verticalCenter: parent.verticalCenter
        radius: 1; color: f.labelColor
    }
    Text {
        id: lab
        anchors.left: parent.left; anchors.leftMargin: 10; anchors.verticalCenter: parent.verticalCenter
        text: f.label; color: f.labelColor; font.pixelSize: Theme.fsTiny; font.weight: Font.DemiBold; font.family: Theme.sans
        visible: f.label !== ""
    }
    TextInput {
        id: input
        anchors.left: lab.visible ? lab.right : parent.left; anchors.leftMargin: 6
        anchors.right: parent.right; anchors.rightMargin: 7; anchors.verticalCenter: parent.verticalCenter
        horizontalAlignment: TextInput.AlignRight
        color: Theme.text; font.pixelSize: Theme.fsSmall; font.family: Theme.mono
        selectionColor: Theme.accent; selectedTextColor: Theme.onAccent
        selectByMouse: true
        clip: true
        text: Number(f._shown).toFixed(f.decimals)
        validator: DoubleValidator {}
        onEditingFinished: { const v = parseFloat(text); if (!isNaN(v)) { f._shown = v; f.committed(v) } }
    }
    MouseArea {
        id: drag
        anchors.fill: parent
        hoverEnabled: true
        property real startX: 0
        property real startV: 0
        property bool moved: false
        property bool active: pressed && moved
        cursorShape: Qt.SizeHorCursor
        onPressed: (m) => { startX = m.x; startV = f._shown; moved = false }
        onPositionChanged: (m) => {
            if (!pressed) return
            const dx = m.x - startX
            if (Math.abs(dx) > 3) moved = true
            if (!moved) return
            const k = (m.modifiers & Qt.ShiftModifier) ? 0.1 : (m.modifiers & Qt.ControlModifier) ? 10 : 1
            f._shown = startV + dx * f.stepSize * k * 0.5
        }
        onReleased: {
            if (moved) f.committed(f._shown)
            else { input.forceActiveFocus(); input.selectAll() }
        }
    }
}
