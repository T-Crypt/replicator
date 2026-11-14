pragma Singleton
import QtQuick
import QtCore

// Replicator design tokens. Every colour, size and font in the workspace comes from here, so a theme, an accent or
// a density change repaints the whole app at once. The choices persist in ~/.config/Replicator/Replicator.conf.
//
//   Theme.themeName   abyss | graphite | carbon | daylight
//   Theme.accentName  holo | azure | violet | mint | amber | rose
//   Theme.density     compact | cozy | roomy
//
// A panel never hard-codes a colour: surfaces are bg < panel < panel2 < raised, text is text > dim > faint.
QtObject {
    id: t

    property string themeName: "abyss"
    property string accentName: "holo"
    property string density: "cozy"
    property bool motion: true                 // false = no easing anywhere (accessibility, slow machines)

    property Settings store: Settings {
        category: "appearance"
        property alias theme: t.themeName
        property alias accent: t.accentName
        property alias density: t.density
        property alias motion: t.motion
    }

    readonly property var themes: ({
        abyss: {
            label: "Abyss", note: "Deep-sea navy, the Replicator signature", dark: true,
            bg: "#060a10", panel: "#0b1119", panel2: "#111925", raised: "#172231", header: "#080d14",
            line: "#1c2735", lineSoft: "#141d29", field: "#070b11",
            text: "#dde6f0", dim: "#8494a7", faint: "#4f5e71",
            viewTop: "#1b2838", viewBottom: "#06090e", gridMinor: "#5d7590", gridMajor: "#86a3c2",
            stageTop: "#07080b", stageBottom: "#020203", scrim: "#b0030609"
        },
        graphite: {
            label: "Graphite", note: "Neutral studio grey, the classic DCC look", dark: true,
            bg: "#1a1b1e", panel: "#232528", panel2: "#2b2d32", raised: "#33363c", header: "#1e2023",
            line: "#383b41", lineSoft: "#2e3136", field: "#17181b",
            text: "#dcdfe4", dim: "#8d929b", faint: "#5d626b",
            viewTop: "#3d4046", viewBottom: "#232529", gridMinor: "#7e838c", gridMajor: "#a3a8b1",
            stageTop: "#07080b", stageBottom: "#020203", scrim: "#b00b0c0e"
        },
        carbon: {
            label: "Carbon", note: "True black for OLED and dark rooms", dark: true,
            bg: "#000000", panel: "#08090a", panel2: "#101113", raised: "#18191c", header: "#040405",
            line: "#1f2023", lineSoft: "#141517", field: "#020203",
            text: "#e4e4e7", dim: "#8a8b90", faint: "#525359",
            viewTop: "#16171a", viewBottom: "#000000", gridMinor: "#5c5e66", gridMajor: "#84868f",
            stageTop: "#07080b", stageBottom: "#020203", scrim: "#b0000000"
        },
        daylight: {
            label: "Daylight", note: "Light panels for a bright room", dark: false,
            bg: "#e9ecf0", panel: "#f5f6f8", panel2: "#e8ebef", raised: "#ffffff", header: "#eef0f3",
            line: "#cfd4db", lineSoft: "#dde1e6", field: "#ffffff",
            text: "#1b2029", dim: "#596270", faint: "#8e96a3",
            viewTop: "#dfe4ea", viewBottom: "#b9c1cb", gridMinor: "#7f8a98", gridMajor: "#566170",
            stageTop: "#07080b", stageBottom: "#020203", scrim: "#70202836"
        }
    })
    readonly property var accents: ({
        holo:   { label: "Holo",   base: "#2fc3ff", hi: "#74dbff" },
        azure:  { label: "Azure",  base: "#3d8ee6", hi: "#62a9f7" },
        violet: { label: "Violet", base: "#9d7bff", hi: "#b9a0ff" },
        mint:   { label: "Mint",   base: "#3fd9a0", hi: "#7aeac0" },
        amber:  { label: "Amber",  base: "#ffab3d", hi: "#ffc470" },
        rose:   { label: "Rose",   base: "#ff5d8a", hi: "#ff8aab" }
    })
    readonly property var densities: ({ compact: 0.92, cozy: 1.0, roomy: 1.1 })

    readonly property var p: themes[themeName] || themes.abyss
    readonly property var a: accents[accentName] || accents.holo
    readonly property real k: densities[density] || 1.0
    readonly property bool dark: p.dark

    // ---- surfaces
    readonly property color bg: p.bg
    readonly property color panel: p.panel
    readonly property color panel2: p.panel2
    readonly property color raised: p.raised
    readonly property color header: p.header
    readonly property color line: p.line
    readonly property color lineSoft: p.lineSoft
    readonly property color field: p.field
    readonly property color scrim: p.scrim
    readonly property color glass: Qt.rgba(panel.r, panel.g, panel.b, 0.88)        // floating bars over the viewport
    readonly property color glassLine: Qt.rgba(text.r, text.g, text.b, dark ? 0.10 : 0.16)
    readonly property color hover: Qt.rgba(text.r, text.g, text.b, dark ? 0.06 : 0.07)
    readonly property color press: Qt.rgba(text.r, text.g, text.b, dark ? 0.11 : 0.12)

    // ---- text
    readonly property color text: p.text
    readonly property color dim: p.dim
    readonly property color faint: p.faint

    // ---- accent
    readonly property color accent: a.base
    readonly property color accentHi: a.hi
    readonly property color onAccent: (0.299 * accent.r + 0.587 * accent.g + 0.114 * accent.b) > 0.55 ? "#041019" : "#ffffff"
    readonly property color accentSoft: Qt.rgba(accent.r, accent.g, accent.b, dark ? 0.16 : 0.18)   // selected rows
    readonly property color accentLine: Qt.rgba(accent.r, accent.g, accent.b, 0.55)

    // ---- fixed meanings (the same in every theme)
    readonly property color holo: "#33c6ff"          // the materialize scan, always cyan
    readonly property color amber: "#ffb347"         // selection in the viewport
    readonly property color observed: dark ? "#7bd88f" : "#1f9d55"
    readonly property color inferred: dark ? "#ffcb6b" : "#b7791f"
    readonly property color unknown: dim
    readonly property color danger: "#ff5d6c"
    readonly property color axisX: "#e5484d"
    readonly property color axisY: "#6fcf83"
    readonly property color axisZ: "#3d8ee6"

    // ---- viewport
    readonly property color viewTop: p.viewTop
    readonly property color viewBottom: p.viewBottom
    readonly property color gridMinor: p.gridMinor
    readonly property color gridMajor: p.gridMajor
    readonly property color stageTop: p.stageTop
    readonly property color stageBottom: p.stageBottom
    // overlays drawn over the 3D view stay light-on-dark in every theme except Daylight
    readonly property color viewText: dark ? "#eef2f7" : "#1b2029"
    readonly property color viewDim: dark ? "#93a0b1" : "#4c5562"

    // ---- type
    readonly property string sans: "Inter"
    readonly property string mono: "JetBrainsMono Nerd Font"
    readonly property int fs: Math.round(12 * k)
    readonly property int fsSmall: Math.round(11 * k)
    readonly property int fsTiny: Math.round(10 * k)
    readonly property int fsLarge: Math.round(14 * k)
    readonly property real caps: 1.4                 // letter spacing for small-caps section labels

    // ---- metrics
    readonly property int row: Math.round(28 * k)    // list rows
    readonly property int ctl: Math.round(26 * k)    // fields, combos, small buttons
    readonly property int bar: Math.round(34 * k)    // dock headers and tool bars
    readonly property int r1: 4
    readonly property int r2: 7
    readonly property int r3: 11
    readonly property int pad: Math.round(10 * k)

    // ---- motion
    readonly property int fast: motion ? 120 : 0
    readonly property int med: motion ? 220 : 0
    readonly property int slow: motion ? 420 : 0
}
