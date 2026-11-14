import QtQuick
import QtQuick.Shapes

// Replicator's icon set: line icons on a 24 unit grid, drawn as vector paths (crisp at any size, tinted by any
// token). `name` picks the path, `fill` (0..1) fills the outline for solid glyphs such as play.
// Add an icon by adding one SVG path string to `paths`; nothing else needs to change.
Item {
    id: ic
    property string name: ""
    property real size: 18
    property color color: Theme.text
    property real stroke: 1.7
    property real fill: solid.indexOf(name) >= 0 ? 1.0 : 0.0
    implicitWidth: size; implicitHeight: size
    width: size; height: size

    function circle(cx, cy, r) { return "M" + (cx - r) + " " + cy + " a" + r + " " + r + " 0 1 0 " + (2 * r) + " 0 a" + r + " " + r + " 0 1 0 " + (-2 * r) + " 0 " }
    function ellipse(cx, cy, rx, ry) { return "M" + (cx - rx) + " " + cy + " a" + rx + " " + ry + " 0 1 0 " + (2 * rx) + " 0 a" + rx + " " + ry + " 0 1 0 " + (-2 * rx) + " 0 " }
    readonly property string cube: "M12 3 L20 7.5 V16.5 L12 21 L4 16.5 V7.5 Z M4 7.5 L12 12 L20 7.5 M12 12 V21 "
    readonly property string globe: circle(12, 12, 8) + "M4 12 H20 M12 4 C8.4 8 8.4 16 12 20 M12 4 C15.6 8 15.6 16 12 20 "
    readonly property string frameCorners: "M4 9 V4 H9 M15 4 H20 V9 M20 15 V20 H15 M9 20 H4 V15 "
    readonly property string rays: "M12 2.5 V5 M12 19 V21.5 M2.5 12 H5 M19 12 H21.5 M5.3 5.3 L7 7 M17 17 L18.7 18.7 M5.3 18.7 L7 17 M17 7 L18.7 5.3 "
    readonly property var solid: ["play", "playBack", "shaded", "dot", "cursor"]

    readonly property var paths: ({
        // tools
        cursor: "M5 3 L5 19 L9.5 14.8 L12.6 21 L15 19.9 L12 13.8 L18 13.5 Z",
        move: "M12 3 V21 M3 12 H21 M9 6 L12 3 L15 6 M9 18 L12 21 L15 18 M6 9 L3 12 L6 15 M18 9 L21 12 L18 15",
        frame: frameCorners + circle(12, 12, 1.6),
        // display
        shaded: circle(12, 12, 8),
        lines: globe,
        wire: cube + "M12 3 V12 M4 16.5 L12 12 L20 16.5",
        xray: circle(12, 12, 8) + circle(12, 12, 3.4),
        layers: "M12 3 L21 8 L12 13 L3 8 Z M3 12 L12 17 L21 12 M3 16 L12 21 L21 16",
        grid: "M4 4 H20 V20 H4 Z M4 9.33 H20 M4 14.66 H20 M9.33 4 V20 M14.66 4 V20",
        reference: "M4 5 H14 V15 H4 Z M10 9 H20 V19 H10 Z",
        sun: circle(12, 12, 4) + rays,
        // primitives
        box: cube,
        cylinder: ellipse(12, 6.5, 7, 2.8) + "M5 6.5 V17.5 a7 2.8 0 0 0 14 0 V6.5",
        sphere: circle(12, 12, 8) + "M4 12 a8 3 0 0 0 16 0",
        torus: ellipse(12, 12, 9, 5.5) + "M8.5 11.3 a3.5 1.7 0 0 0 7 0",
        capsule: "M8 8 a4 4 0 0 1 8 0 V16 a4 4 0 0 1 -8 0 Z",
        gear: circle(12, 12, 2.6) + circle(12, 12, 6) + "M12 2.5 V6 M12 18 V21.5 M2.5 12 H6 M18 12 H21.5 M5.3 5.3 L7.8 7.8 M16.2 16.2 L18.7 18.7 M5.3 18.7 L7.8 16.2 M16.2 7.8 L18.7 5.3",
        helix: "M7 3.5 L17 6 L7 8.5 L17 11 L7 13.5 L17 16 L7 18.5 L17 21",
        pipe: "M3 18 H8 a5 5 0 0 0 5 -5 V11 a5 5 0 0 1 5 -5 H21",
        loft: "M8 4 H16 L20 20 H4 Z M6 12 H18",
        // transport
        play: "M8 5 L19 12 L8 19 Z",
        playBack: "M16 5 L5 12 L16 19 Z",
        pause: "M8.5 5 V19 M15.5 5 V19",
        first: "M6 5 V19 M19 5 L9.5 12 L19 19 Z",
        last: "M18 5 V19 M5 5 L14.5 12 L5 19 Z",
        // objects
        eye: "M2.5 12 C5.5 6.4 18.5 6.4 21.5 12 C18.5 17.6 5.5 17.6 2.5 12 Z " + circle(12, 12, 2.6),
        eyeOff: "M2.5 12 C5.5 6.4 18.5 6.4 21.5 12 C18.5 17.6 5.5 17.6 2.5 12 Z M4.5 4.5 L19.5 19.5",
        target: circle(12, 12, 6.5) + circle(12, 12, 1.8) + "M12 2 V5.5 M12 18.5 V22 M2 12 H5.5 M18.5 12 H22",
        chevronRight: "M9 6 L15 12 L9 18",
        chevronDown: "M6 9 L12 15 L18 9",
        dot: circle(12, 12, 3.2),
        // modes
        build: "M4 13 H11 V20 H4 Z M13 13 H20 V20 H13 Z M8.5 4 H15.5 V11 H8.5 Z",
        dissect: "M9.5 9.5 H14.5 V14.5 H9.5 Z M12 6.5 V2.5 M12 21.5 V17.5 M6.5 12 H2.5 M21.5 12 H17.5 M10.4 4.1 L12 2.5 L13.6 4.1 M10.4 19.9 L12 21.5 L13.6 19.9 M4.1 10.4 L2.5 12 L4.1 13.6 M19.9 10.4 L21.5 12 L19.9 13.6",
        reverse: frameCorners + "M3 12 H21",
        showcase: "M3 8 H7.5 L9 5.5 H15 L16.5 8 H21 V19 H3 Z " + circle(12, 13.2, 3.4),
        // actions
        search: circle(10.5, 10.5, 6.5) + "M15.5 15.5 L20.5 20.5",
        sliders: "M4 7 H13 M17 7 H20 M15 5 V9 M4 12 H7 M11 12 H20 M9 10 V14 M4 17 H14 M18 17 H20 M16 15 V19",
        image: "M4 5 H20 V19 H4 Z M4 16 L9 11 L13 15 L16 12.5 L20 16 " + circle(15.5, 8.8, 1.2),
        importIn: "M12 3 V14 M8 10 L12 14 L16 10 M4 15 V20 H20 V15",
        exportOut: "M12 14 V3 M8 7 L12 3 L16 7 M4 15 V20 H20 V15",
        folder: "M3 6 H9 L11 8.5 H21 V19 H3 Z",
        sparkle: "M11 3 L12.9 9.1 L19 11 L12.9 12.9 L11 19 L9.1 12.9 L3 11 L9.1 9.1 Z M18.5 15.5 L19.3 18.2 L22 19 L19.3 19.8 L18.5 22.5 L17.7 19.8 L15 19 L17.7 18.2 Z",
        pencil: "M4 20 L5 15.5 L16 4.5 L19.5 8 L8.5 19 Z M14 6.5 L17.5 10",
        undo: "M9 6 L4 10 L9 14 M4 10 H14 a5 5 0 0 1 0 10 H11",
        redo: "M15 6 L20 10 L15 14 M20 10 H10 a5 5 0 0 0 0 10 H13",
        terminal: "M3 5 H21 V19 H3 Z M7 9.5 L10 12 L7 14.5 M12.5 15 H17",
        close: "M6 6 L18 18 M18 6 L6 18",
        check: "M5 12.5 L10 17.5 L19 7",
        plus: "M12 5 V19 M5 12 H19",
        panelLeft: "M3 5 H21 V19 H3 Z M9 5 V19",
        panelRight: "M3 5 H21 V19 H3 Z M15 5 V19",
        panelBottom: "M3 5 H21 V19 H3 Z M3 14 H21",
        material: circle(12, 12, 8) + "M8.3 10.2 a4.5 4.5 0 0 1 4 -3.6",
        chip: "M7 7 H17 V17 H7 Z M10 3 V7 M14 3 V7 M10 17 V21 M14 17 V21 M3 10 H7 M3 14 H7 M17 10 H21 M17 14 H21",
        external: "M14 4 H20 V10 M20 4 L11 13 M18 14 V20 H4 V6 H10",
        render: "M3 6 H21 V18 H3 Z M3 10 H21 M7.5 6 L5.5 10 M12.5 6 L10.5 10 M17.5 6 L15.5 10",
        history: circle(12, 12, 8) + "M12 7.5 V12 L15 14",
        ruler: "M3 15 L15 3 L21 9 L9 21 Z M7.5 13.5 L9.5 15.5 M10.5 10.5 L12.5 12.5 M13.5 7.5 L15.5 9.5",
        spin: "M20 12 a8 8 0 1 1 -3 -6.2 M17.5 2.5 V6 H14",
        present: "M3 4.5 H21 V16.5 H3 Z M12 16.5 V20.5 M8 20.5 H16 M10.3 8 L14.6 10.5 L10.3 13 Z",
        mic: "M9.5 5.5 a2.5 2.5 0 0 1 5 0 V11 a2.5 2.5 0 0 1 -5 0 Z M6 11 a6 6 0 0 0 12 0 M12 17 V20.5 M8.5 20.5 H15.5",
        speaker: "M4 9.5 H7.5 L12 6 V18 L7.5 14.5 H4 Z M15.5 9 a4 4 0 0 1 0 6 M18 6.5 a7.5 7.5 0 0 1 0 11",
        speakerOff: "M4 9.5 H7.5 L12 6 V18 L7.5 14.5 H4 Z M16 9.5 L20.5 14.5 M20.5 9.5 L16 14.5",
        book: "M4 5 C7 4 10 4.5 12 6 C14 4.5 17 4 20 5 V18.5 C17 17.5 14 18 12 19.5 C10 18 7 17.5 4 18.5 Z M12 6 V19.5",
        link: "M10 14 a4 4 0 0 0 5.7 0 L19 10.7 a4 4 0 0 0 -5.7 -5.7 L12 6.3 M14 10 a4 4 0 0 0 -5.7 0 L5 13.3 a4 4 0 0 0 5.7 5.7 L12 17.7",
        alert: "M12 4 L21.5 20 H2.5 Z M12 10 V14.5 M12 17.2 V17.4",
        printer: "M7 9 V4 H17 V9 M7 17 H4 V9 H20 V17 H17 M7 14 H17 V20 H7 Z"
    })

    Shape {
        width: 24; height: 24
        scale: ic.size / 24
        transformOrigin: Item.TopLeft
        preferredRendererType: Shape.CurveRenderer
        ShapePath {
            strokeColor: ic.color
            strokeWidth: ic.stroke * Math.min(1.25, Math.max(0.85, 18 / ic.size))
            fillColor: Qt.rgba(ic.color.r, ic.color.g, ic.color.b, ic.color.a * ic.fill)
            capStyle: ShapePath.RoundCap
            joinStyle: ShapePath.RoundJoin
            PathSvg { path: ic.paths[ic.name] || "" }
        }
    }
}
