import QtQuick

// A material preview ball drawn in 2D: base colour, a key light whose size follows roughness, a rim for metals
// and a glow for emissive materials. Cheap enough to show a whole shelf of them.
Item {
    id: sw
    property color base: "#b8bbc2"
    property real metal: 0
    property real rough: 0.5
    property color glow: "black"
    property bool selected: false
    property real size: 34
    implicitWidth: size; implicitHeight: size
    readonly property bool lit: glow.r + glow.g + glow.b > 0.05

    Rectangle {   // emissive halo
        visible: sw.lit
        anchors.centerIn: parent; width: sw.size + 6; height: width; radius: width / 2
        color: "transparent"; border.width: 3
        border.color: Qt.rgba(sw.glow.r, sw.glow.g, sw.glow.b, 0.35)
    }
    Rectangle {
        id: ball
        anchors.centerIn: parent
        width: sw.size - 4; height: width; radius: width / 2
        gradient: Gradient {
            GradientStop { position: 0.0; color: sw.lit ? Qt.lighter(sw.glow, 1.25) : Qt.lighter(sw.base, 1.0 + 0.55 * (1 - sw.rough * 0.6)) }
            GradientStop { position: 0.55; color: sw.lit ? sw.glow : sw.base }
            GradientStop { position: 1.0; color: sw.lit ? Qt.darker(sw.glow, 1.5) : Qt.darker(sw.base, 1.9 + sw.metal * 1.6) }
        }
        Rectangle {   // key light: tight on polished surfaces, wide and faint on rough ones
            x: parent.width * 0.24; y: parent.height * 0.16
            width: parent.width * (0.2 + sw.rough * 0.28); height: width * 0.62; radius: height / 2
            color: "white"; opacity: sw.lit ? 0.5 : (0.85 - sw.rough * 0.7)
        }
        Rectangle {   // environment band on metals
            visible: sw.metal > 0.5 && !sw.lit
            anchors.horizontalCenter: parent.horizontalCenter; y: parent.height * 0.6
            width: parent.width * 0.72; height: parent.height * 0.1; radius: height / 2
            color: "white"; opacity: 0.16 * (1 - sw.rough)
        }
    }
    Rectangle {
        anchors.centerIn: parent; width: sw.size; height: width; radius: width / 2
        color: "transparent"; border.width: sw.selected ? 2 : 0; border.color: Theme.accent
    }
}
