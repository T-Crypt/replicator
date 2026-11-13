pragma Singleton
import QtQuick

// Cinema 4D-like dark workspace: charcoal panels, one blue accent, small dense type, holo cyan for Replicator.
QtObject {
    readonly property color bg: "#1c1d20"
    readonly property color panel: "#26282c"
    readonly property color panel2: "#2d3035"
    readonly property color header: "#212327"
    readonly property color line: "#3a3d43"
    readonly property color field: "#1a1b1e"
    readonly property color text: "#d9dce1"
    readonly property color dim: "#8b9099"
    readonly property color faint: "#5c616a"
    readonly property color accent: "#3d8ee6"
    readonly property color accentHi: "#5aa5f5"
    readonly property color holo: "#33c6ff"
    readonly property color amber: "#ffb347"
    readonly property color observed: "#7bd88f"
    readonly property color inferred: "#ffcb6b"
    readonly property color unknown: "#8b9099"
    readonly property color axisX: "#e5484d"
    readonly property color axisY: "#7bd88f"
    readonly property color axisZ: "#3d8ee6"
    readonly property color viewportBg: "#3a3d42"
    readonly property color viewportBg2: "#25272b"
    readonly property string mono: "JetBrains Mono"
    readonly property int fs: 12
    readonly property int fsSmall: 11
}
