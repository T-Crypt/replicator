import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Replicator.UI

// The build timeline: one block per build step with its component colour along the top, a playhead you can drag,
// play forward (build) or backward (disassemble: parts dematerialize in reverse order) and a speed control.
Rectangle {
    id: tl
    color: Theme.panel
    implicitHeight: 96
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
        anchors.leftMargin: 10; anchors.rightMargin: 10; anchors.topMargin: 7; anchors.bottomMargin: 9
        spacing: 7
        RowLayout {
            spacing: 2
            IconButton { size: 26; iconSize: 14; icon: "first"; tip: "First step"; onHit: { tl.stop(); studio.setStep(0) } }
            IconButton { size: 26; iconSize: 14; icon: "playBack"; tip: "Disassemble (play backward)"; keys: "Shift+Space"; on: tl.playDir < 0; onHit: tl.play(-1) }
            IconButton { size: 26; iconSize: 14; icon: tl.playDir !== 0 ? "pause" : "play"; tip: tl.playDir !== 0 ? "Pause" : "Build (play forward)"; keys: "Space"
                         on: tl.playDir > 0; onHit: tl.playDir !== 0 ? tl.stop() : tl.play(1) }
            IconButton { size: 26; iconSize: 14; icon: "last"; tip: "Finished build"; onHit: { tl.stop(); studio.setStep(studio.stepCount - 1) } }
            Segmented {
                Layout.leftMargin: 10
                implicitHeight: 24; segWidth: 38
                current: String(tl.speed)
                model: [ { key: "0.5", label: "½×" }, { key: "1", label: "1×" }, { key: "2", label: "2×" }, { key: "4", label: "4×" } ]
                onPick: (k) => tl.speed = parseFloat(k)
            }
            Text {
                Layout.leftMargin: 14
                text: studio.stepCount ? (studio.step + 1) + " / " + studio.stepCount : ""
                color: Theme.accentHi; font.pixelSize: Theme.fsSmall; font.family: Theme.mono
            }
            Text {
                Layout.leftMargin: 8
                readonly property var op: studio.ops[studio.step]
                text: studio.stepCount ? (op ? op.label : "") : "No build yet"
                color: Theme.text; font.pixelSize: Theme.fs; font.family: Theme.sans; font.weight: Font.Medium
            }
            Rectangle {
                readonly property var op: studio.ops[studio.step]
                visible: !!op
                Layout.leftMargin: 6
                implicitWidth: opk.implicitWidth + 12; implicitHeight: 17; radius: 8.5; color: Theme.panel2
                Text { id: opk; anchors.centerIn: parent; text: parent.op ? parent.op.op : ""; color: Theme.dim
                       font.pixelSize: Theme.fsTiny; font.family: Theme.mono }
            }
            Text {
                visible: tl.playlist.length > 0
                Layout.leftMargin: 8
                text: "playing one component"
                color: Theme.accentHi; font.pixelSize: Theme.fsSmall; font.family: Theme.sans
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
                    delegate: Item {
                        id: blk
                        required property var modelData
                        required property int index
                        readonly property bool built: index <= studio.step
                        readonly property bool cur: index === studio.step
                        readonly property color cc: modelData.color
                        width: track.bw; height: track.height
                        Rectangle {
                            anchors.fill: parent; anchors.leftMargin: 1; anchors.rightMargin: 1; radius: Theme.r1
                            color: blk.built ? Qt.rgba(blk.cc.r, blk.cc.g, blk.cc.b, blk.cur ? 0.42 : 0.2) : Theme.panel2
                            border.width: blk.cur ? 1 : 0
                            border.color: blk.cc
                            Behavior on color { ColorAnimation { duration: Theme.med } }
                            Rectangle {   // component strip
                                x: 1; y: 1; width: parent.width - 2; height: 3; radius: 1.5
                                color: blk.cc; opacity: blk.built ? 1 : 0.3
                            }
                            Rectangle { anchors.fill: parent; radius: parent.radius; color: Theme.hover; visible: tipArea.containsMouse }
                        }
                        Text {
                            anchors.centerIn: parent; anchors.verticalCenterOffset: 2; width: parent.width - 8
                            text: blk.modelData.label; elide: Text.ElideRight; horizontalAlignment: Text.AlignHCenter
                            color: blk.cur ? Theme.text : blk.built ? Theme.dim : Theme.faint
                            font.pixelSize: Theme.fsTiny; font.family: Theme.sans; font.weight: blk.cur ? Font.DemiBold : Font.Normal
                            visible: track.bw > 46
                        }
                        ToolTip.visible: tipArea.containsMouse
                        ToolTip.delay: 300
                        ToolTip.text: (index + 1) + ". " + modelData.label + "  ·  " + modelData.op + "  ·  " + modelData.component
                        MouseArea { id: tipArea; anchors.fill: parent; hoverEnabled: true; acceptedButtons: Qt.NoButton }
                    }
                }
            }
            Rectangle {   // playhead
                x: (studio.step + 1) * track.bw - 1
                width: 2; height: track.height + 8; y: -4; radius: 1; color: Theme.accent
                visible: studio.stepCount > 0
                Behavior on x { NumberAnimation { duration: Theme.fast + 40; easing.type: Easing.OutCubic } }
                Rectangle { anchors.horizontalCenter: parent.horizontalCenter; y: -3; width: 8; height: 8; radius: 4; color: Theme.accent }
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
