import QtQuick
import QtQuick.Layouts
import Replicator.UI

// The status bar: the last console line on the left, kernel read-outs on the right (step, parts, triangles,
// size, how long the last rebuild took and how much of it came from the cache, the model, the display GPU).
Rectangle {
    id: sb
    implicitHeight: 26
    color: Theme.header
    Rectangle { width: parent.width; height: 1; color: Theme.line }
    readonly property var st: studio.stats
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
        Chip { visible: studio.stepCount > 0; label: "TRIS"; value: sb.n(sb.st.triangles) }
        Chip { visible: studio.dimensions.length === 3; label: "SIZE"
               value: studio.dimensions.map(d => Math.round(d)).join(" × ") + " mm" }
        Chip { visible: studio.stepCount > 0; label: "KERNEL"
               value: (sb.st.buildMs !== undefined ? sb.st.buildMs.toFixed(1) : "—") + " ms"
               valueColor: sb.st.buildMs > 120 ? Theme.amber : Theme.text }
        Chip { visible: studio.stepCount > 0; label: "CACHE"
               value: sb.n(sb.st.cacheHits) + " hit · " + sb.n(sb.st.cacheMisses) + " built" }
        Rectangle { width: 1; height: 12; color: Theme.line }
        Chip { icon: "chip"; label: "DRAWS ON"; value: "iGPU" }
    }
}
