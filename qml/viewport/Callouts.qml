import QtQuick
import Replicator.UI

// Dissect callouts: one label per component, pinned to the exploded part by a leader line. Labels sit in two
// columns (left and right of the build), sorted by height and pushed apart so they never overlap; everything is
// re-projected every frame.
Item {
    id: co
    property var viewport
    property real explode: 0
    property string isolate: ""
    property var hidden: ({})
    signal chosen(string cid)

    readonly property int tick: viewport ? viewport.tick : 0
    readonly property var placed: {
        tick
        const comps = studio.components
        if (!viewport || explode < 0.12) return []
        const items = []
        for (let i = 0; i < comps.length; i++) {
            const c = comps[i]
            if (hidden[c.id] === true || (isolate !== "" && isolate !== c.id)) continue
            const w = Qt.vector3d(c.center[0] + c.offset[0] * explode, c.center[1] + c.offset[1] * explode,
                                  c.center[2] + c.offset[2] * explode)
            const p = viewport.project(w)
            if (!(p.z > 0) || isNaN(p.x)) continue
            items.push({ id: c.id, label: c.label, count: c.count, color: c.color, x: p.x, y: p.y })
        }
        const mid = width / 2
        const gap = 26
        for (const side of [-1, 1]) {
            const col = items.filter(it => (it.x < mid ? -1 : 1) === side).sort((a, b) => a.y - b.y)
            let lastY = -1e9
            for (const it of col) {
                it.side = side
                it.ly = Math.max(it.y - 40, lastY + gap, 70)
                lastY = it.ly
                const spread = Math.min(220, Math.max(90, Math.abs(it.x - mid) * 0.35 + 70))
                const tagW = 40 + (it.label.length + (it.count > 1 ? 4 : 0)) * 6.8     // estimated: keeps the tag inside the view
                it.lx = side < 0 ? Math.max(tagW + 12, Math.min(it.x - spread, mid - 260))
                                 : Math.min(width - tagW - 12, Math.max(it.x + spread, mid + 260))
            }
            const over = col.length ? col[col.length - 1].ly - (height - 150) : 0   // stay above the bottom bar
            if (over > 0) for (const it of col) it.ly = Math.max(60, it.ly - over)
        }
        return items
    }
    opacity: Math.min(1, Math.max(0, (explode - 0.12) * 4))

    Canvas {
        anchors.fill: parent
        property var items: co.placed
        onItemsChanged: requestPaint()
        onPaint: {
            const g = getContext("2d"); g.reset()
            for (const it of items) {
                g.strokeStyle = it.color; g.globalAlpha = 0.9; g.lineWidth = 1.2
                g.beginPath(); g.moveTo(it.x, it.y)
                g.lineTo(it.lx - it.side * 18, it.ly); g.lineTo(it.lx, it.ly); g.stroke()
                g.fillStyle = it.color; g.beginPath(); g.arc(it.x, it.y, 3.2, 0, 2 * Math.PI); g.fill()
            }
        }
    }
    Repeater {
        model: co.placed
        delegate: Rectangle {
            id: tag
            required property var modelData
            x: modelData.side < 0 ? modelData.lx - width : modelData.lx
            y: modelData.ly - height / 2
            width: lbl.implicitWidth + 32; height: 24; radius: 12
            color: studio.selectedComponent === modelData.id ? Theme.raised : Theme.glass
            border.color: studio.selectedComponent === modelData.id ? modelData.color : Qt.rgba(modelData.color.r, modelData.color.g, modelData.color.b, 0.55)
            Rectangle { x: 10; anchors.verticalCenter: parent.verticalCenter; width: 7; height: 7; radius: 3.5; color: tag.modelData.color }
            Text {
                id: lbl
                x: 23; anchors.verticalCenter: parent.verticalCenter
                text: tag.modelData.label + (tag.modelData.count > 1 && !/x\d/.test(tag.modelData.label) ? "  ×" + tag.modelData.count : "")
                color: Theme.text; font.pixelSize: Theme.fsSmall; font.family: Theme.sans
            }
            MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: co.chosen(tag.modelData.id) }
        }
    }
}
