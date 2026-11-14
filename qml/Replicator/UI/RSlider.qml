import QtQuick
import QtQuick.Controls

// A thin themed slider: accent fill, a round handle that grows on hover.
Slider {
    id: s
    implicitWidth: 160
    implicitHeight: 22
    background: Item {
        x: s.leftPadding; y: s.topPadding + s.availableHeight / 2 - 2
        width: s.availableWidth; height: 4
        Rectangle { anchors.fill: parent; radius: 2; color: Theme.line }
        Rectangle { width: s.visualPosition * parent.width; height: parent.height; radius: 2; color: Theme.accent }
    }
    handle: Rectangle {
        x: s.leftPadding + s.visualPosition * (s.availableWidth - width)
        y: s.topPadding + s.availableHeight / 2 - height / 2
        width: s.pressed || s.hovered ? 14 : 12; height: width; radius: width / 2
        color: Theme.dark ? "#f4f7fa" : "#ffffff"
        border.color: Theme.accent; border.width: 2
        Behavior on width { NumberAnimation { duration: Theme.fast } }
    }
}
