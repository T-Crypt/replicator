import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// The build timeline: one block per build step, coloured by component, a playhead you can drag, play forward
// (build) or backward (disassemble: parts dematerialize in reverse order), speed, and a component lane.
Rectangle {
    id: tl
    color: Theme.panel
    implicitHeight: 92
    property int playDir: 0            // 1 build, -1 disassemble, 0 stopped
    property real speed: 1.0
    property var playlist: []          // step indices to play (a component's "how it's made"), [] = all
    signal stepped()

    function play(dir) {
        if (studio.stepCount === 0) return
        if (dir > 0 && studio.step >= studio.stepCount - 1 && playlist.length === 0) studio.setStep(0)
        if (dir < 0 && studio.step <= 0) studio.setStep(studio.stepCount - 1)
        playDir = dir
    }
    function stop() { playDir = 0; playlist = [] }

    Timer {
        interval: Math.max(120, 1150 / tl.speed)
        repeat: true
        running: tl.playDir !== 0
        onTriggered: {
            if (tl.playlist.length) {
                const i = tl.playlist.indexOf(studio.step)
                const next = tl.playDir > 0 ? tl.playlist[i + 1] : tl.playlist[i - 1]
                if (next === undefined) { tl.stop(); return }
                studio.setStep(next)
            } else {
                const n = studio.step + tl.playDir
                if (n < 0 || n >= studio.stepCount) { tl.playDir = 0; return }
                studio.setStep(n)
            }
            tl.stepped()
        }
    }
    Rectangle { width: parent.width; height: 1; color: Theme.line }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 8
        spacing: 6
        RowLayout {
            spacing: 4
            Repeater {
                model: [ { t: "⏮", tip: "First step", f: () => { tl.stop(); studio.setStep(0) } },
                         { t: "◀◀", tip: "Disassemble (play backward)", f: () => tl.play(-1) },
                         { t: "⏸", tip: "Stop", f: () => tl.stop() },
                         { t: "▶", tip: "Build (play forward)", f: () => tl.play(1) },
                         { t: "⏭", tip: "Finished build", f: () => { tl.stop(); studio.setStep(studio.stepCount - 1) } } ]
                delegate: Rectangle {
                    required property var modelData
                    width: 30; height: 24; radius: 4
                    color: ma.containsMouse ? Theme.panel2 : "transparent"
                    border.color: (modelData.t === "▶" && tl.playDir > 0) || (modelData.t === "◀◀" && tl.playDir < 0) ? Theme.holo : "transparent"
                    Text { anchors.centerIn: parent; text: parent.modelData.t; color: Theme.text; font.pixelSize: 12 }
                    MouseArea { id: ma; anchors.fill: parent; hoverEnabled: true; onClicked: parent.modelData.f() }
                    ToolTip.visible: ma.containsMouse; ToolTip.text: modelData.tip; ToolTip.delay: 500
                }
            }
            Text { text: "speed"; color: Theme.dim; font.pixelSize: Theme.fsSmall; Layout.leftMargin: 8 }
            ComboBox {
                model: ["0.5x", "1x", "2x", "4x"]; currentIndex: 1; implicitWidth: 72; implicitHeight: 24
                onActivated: tl.speed = [0.5, 1, 2, 4][currentIndex]
            }
            Text {
                Layout.leftMargin: 10
                text: studio.stepCount ? ("Step " + (studio.step + 1) + " / " + studio.stepCount + "   ·   "
                      + (studio.ops[studio.step] ? studio.ops[studio.step].label + "  (" + studio.ops[studio.step].op + ")" : ""))
                      : "No build yet"
                color: Theme.text; font.pixelSize: Theme.fs
            }
            Text {
                visible: tl.playlist.length > 0
                text: "  ·  playing one component"
                color: Theme.holo; font.pixelSize: Theme.fsSmall
            }
            Item { Layout.fillWidth: true }
        }
        Item {
            id: track
            Layout.fillWidth: true
            Layout.fillHeight: true
            readonly property real bw: studio.stepCount ? width / studio.stepCount : width
            Row {
                anchors.fill: parent
                Repeater {
                    model: studio.ops
                    delegate: Rectangle {
                        required property var modelData
                        required property int index
                        width: track.bw; height: track.height
                        color: "transparent"
                        Rectangle {
                            anchors.fill: parent; anchors.margins: 1; radius: 3
                            color: index <= studio.step ? parent.modelData.color : Qt.darker(parent.modelData.color, 3.2)
                            opacity: index <= studio.step ? 0.85 : 0.6
                            border.color: index === studio.step ? "white" : "transparent"
                            border.width: 1.5
                        }
                        Text {
                            anchors.centerIn: parent; width: parent.width - 6
                            text: parent.modelData.label; elide: Text.ElideRight; horizontalAlignment: Text.AlignHCenter
                            color: index <= studio.step ? "#0b0c0e" : Theme.dim
                            font.pixelSize: 10; visible: track.bw > 46
                        }
                        ToolTip.visible: tipArea.containsMouse
                        ToolTip.text: (index + 1) + ". " + modelData.label + " — " + modelData.op + " · " + modelData.component
                        MouseArea { id: tipArea; anchors.fill: parent; hoverEnabled: true; acceptedButtons: Qt.NoButton }
                    }
                }
            }
            Rectangle {   // playhead
                x: (studio.step + 1) * track.bw - 1
                width: 2; height: track.height + 6; y: -3; color: Theme.holo
                visible: studio.stepCount > 0
                Behavior on x { NumberAnimation { duration: 160; easing.type: Easing.OutCubic } }
            }
            MouseArea {
                anchors.fill: parent
                function seek(x) { tl.stop(); studio.setStep(Math.floor(Math.max(0, x) / track.bw)) }
                onPressed: (m) => seek(m.x)
                onPositionChanged: (m) => seek(m.x)
                onClicked: (m) => { const o = studio.ops[Math.floor(m.x / track.bw)]; if (o) studio.select(o.id) }
            }
        }
    }
}
