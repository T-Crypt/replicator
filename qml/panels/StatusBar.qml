import QtQuick
import QtQuick.Layouts
import QtQuick.Controls
import Replicator.UI

// The status bar: the last console line on the left, kernel read-outs on the right (step, parts, triangles,
// size, how long the last rebuild took and how much of it came from the cache, the model, the display GPU).
Rectangle {
    id: sb
    implicitHeight: 26
    color: Theme.header
    Rectangle { width: parent.width; height: 1; color: Theme.line }
    readonly property var st: studio.stats
    readonly property bool roomy: width >= 1760   // below this the diagnostics (TRIS, CACHE) give way to what a user reads
    function n(v) { return v === undefined ? "—" : Number(v).toLocaleString(Qt.locale("en_US"), "f", 0) }

    RowLayout {
        anchors.fill: parent
        anchors.leftMargin: 12; anchors.rightMargin: 12
        spacing: 16
        Rectangle { width: 7; height: 7; radius: 3.5; color: studio.busy !== "" ? Theme.amber : Theme.observed
                    SequentialAnimation on opacity { running: studio.busy !== ""; loops: Animation.Infinite; alwaysRunToEnd: true
                        NumberAnimation { to: 0.3; duration: 500 } NumberAnimation { to: 1; duration: 500 } } }
        Text {
            Layout.fillWidth: true
            text: studio.lastLog; elide: Text.ElideRight
            color: studio.lastLog.indexOf("failed") >= 0 || studio.lastLog.indexOf("rejected") >= 0 || studio.lastLog.indexOf("error") >= 0
                   ? Theme.danger : Theme.dim
            font.pixelSize: Theme.fsTiny; font.family: Theme.mono
        }
        Chip { visible: studio.stepCount > 0; label: "STEP"; value: (studio.step + 1) + "/" + studio.stepCount }
        Chip { visible: studio.stepCount > 0; label: "PARTS"; value: sb.n(sb.st.parts) }
        Chip { visible: studio.stepCount > 0 && sb.roomy; label: "TRIS"; value: sb.n(sb.st.triangles) }
        Chip { visible: studio.dimensions.length === 3; label: "SIZE"
               value: studio.dimensions.map(d => Math.round(d)).join(" × ") + " mm" }
        Item {
            visible: studio.mass.kg !== undefined
            implicitWidth: massChip.implicitWidth; implicitHeight: massChip.implicitHeight
            readonly property var m: studio.mass
            Chip {
                id: massChip
                label: "MASS"
                value: parent.m.kg === undefined ? "" : (parent.m.kg >= 1000 ? (parent.m.kg / 1000).toFixed(2) + " t"
                       : parent.m.kg >= 1 ? parent.m.kg.toFixed(1) + " kg" : (parent.m.kg * 1000).toFixed(0) + " g") + (parent.m.assumed ? " *" : "")
                valueColor: parent.m.assumed ? Theme.inferred : Theme.text
            }
            MouseArea { id: massMa; anchors.fill: parent; hoverEnabled: true }
            ToolTip.visible: massMa.containsMouse; ToolTip.delay: 300
            ToolTip.text: "Computed from measured volumes and handbook densities by material name. Centre of gravity "
                          + (m.cg ? m.cg.join(", ") : "") + " mm."
                          + (m.assumed ? " * " + m.assumed + " part(s) have no recognised material and count as aluminium." : "")
                          + (m.stands === false ? " It would tip over." : m.stands ? " It stands on its footprint." : "")
        }
        Chip { visible: studio.stepCount > 0; label: "KERNEL"
               value: (sb.st.buildMs !== undefined ? sb.st.buildMs.toFixed(1) : "—") + " ms"
               valueColor: sb.st.buildMs > 120 ? Theme.amber : Theme.text }
        Chip { visible: studio.stepCount > 0 && sb.roomy; label: "CACHE"
               value: sb.n(sb.st.cacheHits) + " hit · " + sb.n(sb.st.cacheMisses) + " built" }
        Item {   // the active printer: every STL/3MF export is gated on this bed (empty when none is set)
            readonly property var p: studio.activePrinter
            visible: p.id !== undefined
            implicitWidth: printerChip.implicitWidth; implicitHeight: printerChip.implicitHeight
            Chip {
                id: printerChip
                icon: "printer"
                label: "PRINTER"
                value: parent.visible ? parent.p.name + " " + parent.p.usable.join("×") : ""
            }
            MouseArea { id: printerMa; anchors.fill: parent; hoverEnabled: true }
            ToolTip.visible: printerMa.containsMouse; ToolTip.delay: 300
            ToolTip.text: !visible ? "" : "Prints for " + p.name + ": usable volume " + p.usable.join(" × ") + " mm after a 2 mm margin. "
                          + "Set in services.json (active_printer); a build that overflows is refused, never clipped."
        }
        Rectangle { width: 1; height: 12; color: Theme.line }
        Chip { icon: "chip"; label: "DRAWS ON"; value: studio.drawsOn }
    }
}
