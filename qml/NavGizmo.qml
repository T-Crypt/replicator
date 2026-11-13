import QtQuick

// Axis triad like C4D / Blender: X red, Y green, Z blue, positive ends labelled. Click an end to look down it.
Item {
    id: g
    property real yaw: 0
    property real pitch: 0
    signal snap(string name)
    width: 92; height: 92

    readonly property real cy: Math.cos(yaw * Math.PI / 180)
    readonly property real sy: Math.sin(yaw * Math.PI / 180)
    readonly property real cp: Math.cos(pitch * Math.PI / 180)
    readonly property real sp: Math.sin(pitch * Math.PI / 180)
    // camera basis (same as the viewport): dir to camera, right, up
    function proj(v) {
        const dir = [cp * sy, sp, cp * cy]
        const right = [cy, 0, -sy]
        const up = [dir[1] * right[2] - dir[2] * right[1], dir[2] * right[0] - dir[0] * right[2],
                    dir[0] * right[1] - dir[1] * right[0]]
        return { x: v[0] * right[0] + v[1] * right[1] + v[2] * right[2],
                 y: -(v[0] * up[0] + v[1] * up[1] + v[2] * up[2]),
                 z: v[0] * dir[0] + v[1] * dir[1] + v[2] * dir[2] }
    }
    readonly property var axes: {
        const a = [ { n: "X", v: [1, 0, 0], c: "#e5484d", view: "Right" }, { n: "Y", v: [0, 1, 0], c: "#7bd88f", view: "Top" },
                    { n: "Z", v: [0, 0, 1], c: "#3d8ee6", view: "Front" }, { n: "-X", v: [-1, 0, 0], c: "#e5484d", view: "Left" },
                    { n: "-Y", v: [0, -1, 0], c: "#7bd88f", view: "Bottom" }, { n: "-Z", v: [0, 0, -1], c: "#3d8ee6", view: "Back" } ]
        const out = a.map(o => Object.assign({ p: proj(o.v) }, o))
        out.sort((p, q) => p.p.z - q.p.z)
        return out
    }
    Rectangle { anchors.fill: parent; radius: width / 2; color: hover.containsMouse ? "#30ffffff" : "#18ffffff" }
    Canvas {
        id: cv
        anchors.fill: parent
        property var ax: g.axes
        onAxChanged: requestPaint()
        onPaint: {
            const c = getContext("2d"); c.reset()
            const R = width / 2 - 13, cx = width / 2, cyy = height / 2
            for (const a of ax) {
                const x = cx + a.p.x * R, y = cyy + a.p.y * R
                const pos = a.n.length === 1
                if (pos) { c.strokeStyle = a.c; c.lineWidth = 2.2; c.beginPath(); c.moveTo(cx, cyy); c.lineTo(x, y); c.stroke() }
                c.beginPath(); c.arc(x, y, pos ? 9 : 6, 0, 2 * Math.PI)
                c.fillStyle = pos ? a.c : "#3a1d1f".replace("3a1d1f", a.c === "#e5484d" ? "5a2326" : a.c === "#7bd88f" ? "2c4a33" : "1f3654")
                c.fill()
                if (!pos) { c.strokeStyle = a.c; c.lineWidth = 1.4; c.stroke() }
                if (pos) { c.fillStyle = "#101114"; c.font = "bold 10px sans-serif"; c.textAlign = "center"; c.textBaseline = "middle"; c.fillText(a.n, x, y + 0.5) }
            }
        }
    }
    MouseArea {
        id: hover
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onClicked: (m) => {
            const R = width / 2 - 13
            let best = null, bd = 1e9
            for (const a of g.axes) {
                const d = Math.hypot(width / 2 + a.p.x * R - m.x, height / 2 + a.p.y * R - m.y)
                if (d < bd && a.p.z > -0.98) { bd = d; best = a }
            }
            if (best && bd < 14) g.snap(best.view)
            else g.snap("Perspective")
        }
    }
}
