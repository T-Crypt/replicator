import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Dialogs
import QtQuick.Shapes
import QtQml
import QtCore
import Replicator.UI
import "panels"
import "viewport"

// Replicator: a studio workspace for local models. Header (menus, modes, Commander), tool rail, the viewport with
// its floating bars and the dream capsule, the manager dock on the right, the build timeline and a status bar.
// Every command lives once in `actions`: the menus, the keyboard shortcuts and the Commander all read that list.
ApplicationWindow {
    id: window
    width: 1760
    height: 1020
    visible: true
    title: "Replicator — " + studio.title
    color: Theme.bg

    palette.window: Theme.panel
    palette.windowText: Theme.text
    palette.base: Theme.field
    palette.alternateBase: Theme.panel2
    palette.text: Theme.text
    palette.button: Theme.panel2
    palette.buttonText: Theme.text
    palette.highlight: Theme.accent
    palette.highlightedText: Theme.onAccent
    palette.toolTipBase: Theme.raised
    palette.toolTipText: Theme.text
    palette.placeholderText: Theme.faint
    palette.mid: Theme.line
    palette.dark: Theme.bg
    palette.light: Theme.line

    // ------------------------------------------------------------------ state
    property real blueprint: 0.0
    property real explodeTarget: 0.0
    property real explode: explodeTarget
    Behavior on explode { NumberAnimation { duration: 650; easing.type: Easing.OutCubic } }
    property var hidden: ({})
    property string isolate: ""
    readonly property string part: studio.selectedComponent
    readonly property string partLabel: { const c = studio.components.find(c => c.id === part); return c ? c.label : part }
    readonly property bool idle: studio.busy === ""
    property alias renderGate: viewport.renderGate   // [DEBUG-rg] harness
    readonly property bool showcase: studio.mode === "showcase"
    readonly property bool present: studio.mode === "present"
    readonly property bool empty: studio.stepCount === 0
    property bool needFrame: true
    property bool playing: false                 // set by the launcher: play the build once it is loaded
    onPlayingChanged: if (playing) timeline.play(1)

    // workspace layout, remembered between sessions
    property bool showLeft: true
    property bool showRight: true
    property bool showTimeline: true
    property bool showGrid: true
    property bool showReference: true
    property bool focusMode: false               // F11: the viewport alone
    property real rightWidth: 380
    property int rightTab: 0
    Settings {
        category: "workspace"
        property alias showLeft: window.showLeft
        property alias showRight: window.showRight
        property alias showTimeline: window.showTimeline
        property alias showGrid: window.showGrid
        property alias showReference: window.showReference
        property alias rightWidth: window.rightWidth
    }
    readonly property bool chrome: !showcase && !present && !focusMode

    Component.onCompleted: {
        if (boot.theme) Theme.themeName = boot.theme
        if (boot.accent) Theme.accentName = boot.accent
        if (boot.density) Theme.density = boot.density
        if (boot.ui === "commander" || boot.ui === "preferences" || boot.ui === "context") bootUi.start()
        if (boot.ui === "materials") rightTab = 1
        if (boot.ui === "console") rightTab = 2
    }

    Timer { id: bootUi; interval: 400
            onTriggered: boot.ui === "commander" ? commander.open()
                       : boot.ui === "context" ? window.openContext(studio.shapes.length ? studio.shapes[0].shapeId : "", 760, 330)
                       : preferences.open() }

    function setMode(m) {
        studio.setMode(m)
        if (m === "build") { explodeTarget = 0; viewport.colorByComponent = false; isolate = "" }
        if (m === "dissect") { explodeTarget = Math.max(explodeTarget, 0.8); viewport.colorByComponent = true; viewport.frameAll(true) }
        if (m === "build") viewport.frameAll(true)
        if (m === "reverse") { viewport.colorByComponent = true }
        if (m === "showcase") { timeline.stop(); studio.setStep(studio.stepCount - 1); viewport.colorByComponent = false
                                viewport.heroAngle(); viewport.frameAll(true) }
        if (m === "present") { viewport.colorByComponent = false; presenter.start() }
    }
    function toggleHidden(cid) { const h = Object.assign({}, hidden); h[cid] = !h[cid]; hidden = h }
    function playComponent(cid) {
        const steps = studio.ops.filter(o => o.component === cid).map(o => o.index)
        if (!steps.length) return
        isolate = cid
        studio.setStep(steps[0])
        timeline.playlist = steps
        timeline.playDir = 1
    }
    function openPath(path) {
        studio.openFile(path)
        if (studio.mode === "build") timeline.play(1)
    }
    function val(x) { return typeof x === "function" ? x() : x }
    function openContext(shapeId, x, y) {
        studio.select(shapeId)
        ctxMenu.actions = window.pick(part !== "" ? partMenu : sceneMenu)
        ctxMenu.x = Math.min(x, window.width - ctxMenu.implicitWidth - 8)
        ctxMenu.y = Math.min(y, window.height - ctxMenu.actions.length * Theme.row - 16)
        ctxMenu.open()
    }
    readonly property var partMenu: ["part.frame", "part.isolate", "part.hide", "part.play", "-", "part.rework", "part.material",
                                     "-", "part.duplicate", "part.delete", "-", "showAll", "fixIssues"]
    readonly property var sceneMenu: ["frameAll", "showAll", "-", "disp.shaded", "disp.lines", "disp.xray", "-",
                                      "add.tube", "add.nozzle", "add.rotor", "add.grille", "add.box", "add.cylinder", "-", "fixIssues", "blenderOpen"]

    // ------------------------------------------------------------------ the action registry
    readonly property var actions: [
        // file
        { id: "open", group: "File", title: "Open…", keys: "Ctrl+O", icon: "folder", run: () => openDlg.open() },
        { id: "import", group: "File", title: "Import a model to reverse engineer…", keys: "Ctrl+I", icon: "importIn", run: () => importDlg.open() },
        { id: "image3d", group: "File", title: "Image to 3D…", keys: "Ctrl+Shift+I", icon: "image", run: () => image3DDlg.open() },
        { id: "exportGlb", group: "File", title: "Export GLB", icon: "exportOut", enabled: () => !window.empty, run: () => studio.exportAs("glb") },
        { id: "exportStl", group: "File", title: "Export STL for 3D printing", icon: "exportOut", enabled: () => !window.empty, run: () => studio.exportAs("stl") },
        { id: "exportObj", group: "File", title: "Export OBJ", icon: "exportOut", enabled: () => !window.empty, run: () => studio.exportAs("obj") },
        { id: "close", group: "File", title: "Close the build (start screen)", keys: "Ctrl+W", icon: "close", enabled: () => !window.empty, run: () => { timeline.stop(); window.setMode("build"); studio.closeProgram() } },
        // edit
        { id: "undo", group: "Edit", title: "Undo", keys: "Ctrl+Z", icon: "undo", enabled: () => studio.canUndo, run: () => studio.undo() },
        { id: "redo", group: "Edit", title: "Redo", keys: "Ctrl+Shift+Z", icon: "redo", enabled: () => studio.canRedo, run: () => studio.redo() },
        { id: "deselect", group: "Edit", title: "Deselect", keys: "Esc", run: () => { if (window.present) window.setMode("reverse"); else if (window.showcase || window.focusMode) { window.focusMode = false; if (window.showcase) window.setMode("build") } else { studio.select(""); window.isolate = "" } } },
        { id: "fixIssues", group: "Edit", title: "Fix accuracy issues with the agent", icon: "sparkle", enabled: () => window.idle && studio.issues.some(i => i.severity === "fix"), run: () => studio.fixIssues() },
        { id: "showAll", group: "Edit", title: "Show everything", icon: "eye", run: () => { window.hidden = ({}); window.isolate = "" } },
        { id: "commander", group: "Edit", title: "Commander: search every action", keys: "Ctrl+K", icon: "search", run: () => commander.open() },
        { id: "preferences", group: "Edit", title: "Preferences…", keys: "Ctrl+,", icon: "sliders", run: () => preferences.open() },
        // create
        { id: "add.box", group: "Create", title: "Box", icon: "box", run: () => studio.addPrimitive("box") },
        { id: "add.cylinder", group: "Create", title: "Cylinder", icon: "cylinder", run: () => studio.addPrimitive("cylinder") },
        { id: "add.sphere", group: "Create", title: "Sphere", icon: "sphere", run: () => studio.addPrimitive("sphere") },
        { id: "add.torus", group: "Create", title: "Torus", icon: "torus", run: () => studio.addPrimitive("torus") },
        { id: "add.capsule", group: "Create", title: "Capsule", icon: "capsule", run: () => studio.addPrimitive("capsule") },
        { id: "add.gear", group: "Create", title: "Gear", icon: "gear", run: () => studio.addPrimitive("gear") },
        { id: "add.helix", group: "Create", title: "Spring (helix)", icon: "helix", run: () => studio.addPrimitive("helix") },
        { id: "add.pipe", group: "Create", title: "Pipe", icon: "pipe", run: () => studio.addPrimitive("pipe") },
        { id: "add.loft", group: "Create", title: "Loft", icon: "loft", run: () => studio.addPrimitive("loft") },
        { id: "add.tube", group: "Create", title: "Tube (hollow casing)", icon: "cylinder", run: () => studio.addPrimitive("tube") },
        { id: "add.nozzle", group: "Create", title: "Rocket nozzle (bell)", icon: "loft", run: () => studio.addPrimitive("nozzle") },
        { id: "add.rotor", group: "Create", title: "Rotor (fan, turbine, propeller)", icon: "spin", run: () => studio.addPrimitive("rotor") },
        { id: "add.grille", group: "Create", title: "Grille (vent plate)", icon: "grid", run: () => studio.addPrimitive("grille") },
        // the selected part (right-click menu and Commander)
        { id: "part.frame", group: "Part", title: "Frame this part", icon: "target", enabled: () => window.part !== "", run: () => viewport.frameComponent(window.part) },
        { id: "part.isolate", group: "Part", title: "Isolate", icon: "target", checked: () => window.part !== "" && window.isolate === window.part, enabled: () => window.part !== "", run: () => window.isolate = window.isolate === window.part ? "" : window.part },
        { id: "part.hide", group: "Part", title: "Hide", keys: "Ctrl+H", icon: "eyeOff", enabled: () => window.part !== "", run: () => window.toggleHidden(window.part) },
        { id: "part.play", group: "Part", title: "Play how it is made", icon: "play", enabled: () => window.part !== "", run: () => window.playComponent(window.part) },
        { id: "part.rework", group: "Part", title: "Rework with the agent…", keys: "Ctrl+E", icon: "sparkle", enabled: () => window.part !== "" && window.idle, run: () => { agentPrompt.cid = window.part; agentPrompt.label = window.partLabel; agentPrompt.open() } },
        { id: "part.material", group: "Part", title: "Paint a material…", icon: "material", enabled: () => window.part !== "", run: () => { window.showRight = true; window.rightTab = 1 } },
        { id: "part.duplicate", group: "Part", title: "Duplicate", keys: "Ctrl+D", icon: "copy", enabled: () => window.part !== "" && window.idle, run: () => studio.duplicateComponent(window.part) },
        { id: "part.delete", group: "Part", title: "Delete", keys: "Delete", icon: "trash", enabled: () => window.part !== "" && window.idle, run: () => studio.deleteComponent(window.part) },
        // tools
        { id: "tool.select", group: "Tool", title: "Select tool", icon: "cursor", checked: () => viewport.tool === "select", run: () => viewport.tool = "select" },
        { id: "tool.move", group: "Tool", title: "Move tool", keys: "W", icon: "move", checked: () => viewport.tool === "move", run: () => viewport.tool = viewport.tool === "move" ? "select" : "move" },
        // view
        { id: "frameAll", group: "View", title: "Frame everything", keys: "H", icon: "frame", run: () => viewport.frameAll(true) },
        { id: "frameSel", group: "View", title: "Frame the selection", keys: "F", icon: "target", run: () => viewport.frameSelected() },
        { id: "view.persp", group: "View", title: "Perspective view", keys: "F1", run: () => viewport.setView("Perspective") },
        { id: "view.top", group: "View", title: "Top view", keys: "F2", run: () => viewport.setView("Top") },
        { id: "view.right", group: "View", title: "Right view", keys: "F3", run: () => viewport.setView("Right") },
        { id: "view.front", group: "View", title: "Front view", keys: "F4", run: () => viewport.setView("Front") },
        { id: "disp.shaded", group: "View", title: "Display: shaded", icon: "shaded", checked: () => viewport.displayMode === "shaded", run: () => viewport.displayMode = "shaded" },
        { id: "disp.lines", group: "View", title: "Display: shaded with lines", icon: "lines", checked: () => viewport.displayMode === "lines", run: () => viewport.displayMode = "lines" },
        { id: "disp.wire", group: "View", title: "Display: wireframe", icon: "wire", checked: () => viewport.displayMode === "wire", run: () => viewport.displayMode = "wire" },
        { id: "disp.xray", group: "View", title: "Display: x-ray", icon: "xray", checked: () => viewport.displayMode === "xray", run: () => viewport.displayMode = "xray" },
        { id: "colorComp", group: "View", title: "Colour by component", keys: "C", icon: "layers", checked: () => viewport.colorByComponent, run: () => viewport.colorByComponent = !viewport.colorByComponent },
        { id: "grid", group: "View", title: "Floor grid", keys: "G", icon: "grid", checked: () => window.showGrid, run: () => window.showGrid = !window.showGrid },
        { id: "reference", group: "View", title: "Reference images", keys: "R", icon: "reference", checked: () => window.showReference, run: () => window.showReference = !window.showReference },
        { id: "blueprint", group: "View", title: "Blueprint look on / off", keys: "B", icon: "ruler", checked: () => window.blueprint > 0.5, run: () => bpAnim.go(window.blueprint > 0.5 ? 0 : 1) },
        // timeline
        { id: "play", group: "Timeline", title: "Play / pause the build", keys: "Space", icon: "play", run: () => window.present ? presenter.togglePlay() : timeline.playDir !== 0 ? timeline.stop() : timeline.play(1) },
        { id: "disassemble", group: "Timeline", title: "Disassemble (play backward)", keys: "Shift+Space", icon: "playBack", run: () => timeline.play(-1) },
        { id: "stepPrev", group: "Timeline", title: "Previous step", keys: "Left", run: () => { if (window.present) return presenter.prev(); timeline.stop(); studio.setStep(studio.step - 1) } },
        { id: "stepNext", group: "Timeline", title: "Next step", keys: "Right", run: () => { if (window.present) return presenter.next(); timeline.stop(); studio.setStep(studio.step + 1) } },
        // modes
        { id: "mode.build", group: "Mode", title: "Build mode", keys: "1", icon: "build", checked: () => studio.mode === "build", run: () => window.setMode("build") },
        { id: "mode.dissect", group: "Mode", title: "Dissect mode (exploded view)", keys: "2", icon: "dissect", checked: () => studio.mode === "dissect", run: () => window.setMode("dissect") },
        { id: "mode.reverse", group: "Mode", title: "Reverse mode (take a model apart)", keys: "3", icon: "reverse", checked: () => studio.mode === "reverse", run: () => window.setMode("reverse") },
        { id: "mode.showcase", group: "Mode", title: "Showcase mode (product stage)", keys: "4", icon: "showcase", checked: () => studio.mode === "showcase", run: () => window.setMode("showcase") },
        { id: "mode.present", group: "Mode", title: "Present mode (play the explanation)", keys: "5", icon: "present", checked: () => studio.mode === "present", run: () => window.setMode("present") },
        // render
        { id: "render", group: "Render", title: "Render a still (Cycles, CPU)", keys: "Ctrl+R", icon: "render", enabled: () => !window.empty && studio.busy === "", run: () => studio.renderShowcase(viewport.cameraJson()) },
        { id: "blenderOpen", group: "Render", title: "Open in Blender (MCP socket)", icon: "external", enabled: () => !window.empty && studio.busy === "", run: () => studio.openInBlender() },
        { id: "blenderPull", group: "Render", title: "Pull back from Blender", icon: "importIn", enabled: () => studio.busy === "", run: () => studio.pullFromBlender() },
        { id: "nameParts", group: "Reverse", title: "Name the parts with the local model", icon: "sparkle", enabled: () => !window.empty && studio.busy === "", run: () => studio.nameParts() },
        { id: "explain", group: "Reverse", title: "Explain how it works", icon: "book", enabled: () => !window.empty && studio.busy === "", run: () => studio.explain() },
        // window
        { id: "toggleLeft", group: "Window", title: "Tool rail", icon: "panelLeft", checked: () => window.showLeft, run: () => window.showLeft = !window.showLeft },
        { id: "toggleRight", group: "Window", title: "Manager dock", keys: "Ctrl+J", icon: "panelRight", checked: () => window.showRight, run: () => window.showRight = !window.showRight },
        { id: "toggleTimeline", group: "Window", title: "Timeline", keys: "Ctrl+T", icon: "panelBottom", checked: () => window.showTimeline, run: () => window.showTimeline = !window.showTimeline },
        { id: "focus", group: "Window", title: "Focus mode: the viewport alone", keys: "F11", icon: "frame", checked: () => window.focusMode, run: () => window.focusMode = !window.focusMode },
        { id: "tab.attributes", group: "Window", title: "Show attributes", icon: "sliders", run: () => { window.showRight = true; window.rightTab = 0 } },
        { id: "tab.materials", group: "Window", title: "Show the material shelf", keys: "M", icon: "material", run: () => { window.showRight = true; window.rightTab = 1 } },
        { id: "tab.console", group: "Window", title: "Show the console", keys: "`", icon: "terminal", run: () => { window.showRight = true; window.rightTab = 2 } }
    ]
    readonly property var byId: { const m = {}; for (const a of actions) m[a.id] = a; return m }
    function pick(ids) { return ids.map(i => i === "-" ? "-" : byId[i]) }
    readonly property var menus: [
        { title: "File", items: ["open", "import", "image3d", "-", "exportGlb", "exportStl", "exportObj", "-", "close"] },
        { title: "Edit", items: ["undo", "redo", "-", "deselect", "showAll", "-", "fixIssues", "-", "commander", "preferences"] },
        { title: "Create", items: ["add.box", "add.cylinder", "add.sphere", "add.torus", "add.capsule", "-", "add.gear", "add.helix", "add.pipe", "add.loft",
                                   "-", "add.tube", "add.nozzle", "add.rotor", "add.grille"] },
        { title: "Part", items: ["part.frame", "part.isolate", "part.hide", "part.play", "-", "part.rework", "part.material", "-", "part.duplicate", "part.delete"] },
        { title: "View", items: ["frameAll", "frameSel", "-", "view.persp", "view.top", "view.right", "view.front", "-",
                                 "disp.shaded", "disp.lines", "disp.wire", "disp.xray", "-", "colorComp", "blueprint", "grid", "reference"] },
        { title: "Render", items: ["mode.showcase", "render", "-", "blenderOpen", "blenderPull"] },
        { title: "Window", items: ["mode.build", "mode.dissect", "mode.reverse", "mode.showcase", "mode.present", "-", "explain",
                                   "-", "toggleLeft", "toggleRight", "toggleTimeline", "focus", "-", "tab.attributes", "tab.materials", "tab.console"] }
    ]
    Instantiator {
        model: window.actions.filter(a => !!a.keys)
        delegate: Shortcut {
            required property var modelData
            sequence: modelData.keys
            context: Qt.WindowShortcut
            enabled: !commander.visible && !preferences.visible
            onActivated: if (modelData.enabled === undefined || modelData.enabled()) modelData.run()
        }
    }
    NumberAnimation { id: bpAnim; target: window; property: "blueprint"; duration: 600; easing.type: Easing.InOutCubic
                      function go(v) { to = v; restart() } }

    Connections {
        target: studio
        function onProgramChanged() { window.needFrame = true }
        function onShapesChanged() { if (window.needFrame) { window.needFrame = false; viewport.frameAll(false) } }
        function onModeChanged() {
            if (studio.mode === "reverse") { viewport.colorByComponent = true; if (window.explodeTarget < 0.5) window.explodeTarget = 0.6 }
        }
    }

    FileDialog {
        id: openDlg
        title: "Open a BuildProgram or import a model"
        nameFilters: ["Replicator programs and models (*.json " + studio.importPatterns + ")", "BuildProgram (*.json)",
                      "3D models, CAD and gallery bundles (" + studio.importPatterns + ")"]
        onAccepted: window.openPath(selectedFile.toString())
    }
    FileDialog {
        id: importDlg
        title: "Import a model to reverse engineer"
        nameFilters: ["3D models, CAD and gallery bundles (" + studio.importPatterns + ")"]
        onAccepted: studio.importModel(selectedFile.toString())
    }
    FileDialog {
        id: image3DDlg
        title: "Turn a picture into a 3D model (Hunyuan3D)"
        nameFilters: ["Images (*.png *.jpg *.jpeg)"]
        onAccepted: studio.imageTo3D(selectedFile.toString(), false)
    }

    Commander {
        id: commander
        actions: window.actions
        onOpenFile: (path) => window.openPath(path)
    }
    Preferences { id: preferences; workspace: window }
    RMenu { id: ctxMenu; implicitWidth: 250 }
    AgentPrompt { id: agentPrompt; onSubmitted: (cid, text) => studio.rework(cid, text) }

    // ------------------------------------------------------------------ header: brand, menus, modes, Commander, engine
    header: Rectangle {
        height: window.chrome ? 44 : 0
        visible: height > 0
        clip: true
        color: Theme.header
        Behavior on height { NumberAnimation { duration: Theme.med } }
        Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: 1; color: Theme.line }
        RowLayout {
            anchors.fill: parent
            anchors.leftMargin: 12; anchors.rightMargin: 10
            spacing: 2
            Rectangle {   // brand mark
                implicitWidth: 26; implicitHeight: 26; radius: 7
                gradient: Gradient {
                    GradientStop { position: 0; color: Theme.accentHi }
                    GradientStop { position: 1; color: Theme.accent }
                }
                Icon { anchors.centerIn: parent; name: "box"; size: 16; color: Theme.onAccent; stroke: 1.9 }
            }
            Text { text: "REPLICATOR"; color: Theme.text; font.family: Theme.sans; font.weight: Font.Bold; font.letterSpacing: 3.2
                   font.pixelSize: 12; Layout.leftMargin: 8; Layout.rightMargin: 14 }
            Repeater {
                model: window.menus
                delegate: Rectangle {
                    id: hm
                    required property var modelData
                    implicitWidth: hmt.implicitWidth + 18; implicitHeight: 28; radius: Theme.r1
                    color: hmenu.visible ? Theme.press : hmm.containsMouse ? Theme.hover : "transparent"
                    Text { id: hmt; anchors.centerIn: parent; text: hm.modelData.title
                           color: hmenu.visible || hmm.containsMouse ? Theme.text : Theme.dim
                           font.pixelSize: Theme.fs; font.family: Theme.sans }
                    MouseArea { id: hmm; anchors.fill: parent; hoverEnabled: true; onClicked: hmenu.open() }
                    RMenu { id: hmenu; y: parent.height + 5; actions: window.pick(hm.modelData.items) }
                }
            }
            Item { Layout.fillWidth: true }
            Segmented {
                segWidth: 112
                current: studio.mode
                model: [ { key: "build", label: "Build", icon: "build", hint: "1" }, { key: "dissect", label: "Dissect", icon: "dissect", hint: "2" },
                         { key: "reverse", label: "Reverse", icon: "reverse", hint: "3" }, { key: "showcase", label: "Showcase", icon: "showcase", hint: "4" },
                         { key: "present", label: "Present", icon: "present", hint: "5" } ]
                onPick: (k) => window.setMode(k)
            }
            Item { Layout.fillWidth: true }
            Row {   // running job
                visible: studio.busy !== ""
                spacing: 7; Layout.rightMargin: 10
                Icon { name: "spin"; size: 15; color: Theme.accentHi; anchors.verticalCenter: parent.verticalCenter
                       RotationAnimation on rotation { running: studio.busy !== ""; from: 0; to: 360; duration: 1100; loops: Animation.Infinite } }
                Text { text: studio.busy; color: Theme.accentHi; font.pixelSize: Theme.fsSmall; font.family: Theme.sans
                       anchors.verticalCenter: parent.verticalCenter }
            }
            Rectangle {   // Commander entry
                implicitWidth: 214; implicitHeight: 28; radius: 14
                color: cmdMa.containsMouse ? Theme.hover : Theme.field
                border.color: cmdMa.containsMouse ? Theme.accentLine : Theme.line
                Icon { x: 10; anchors.verticalCenter: parent.verticalCenter; name: "search"; size: 14; color: Theme.dim }
                Text { x: 31; anchors.verticalCenter: parent.verticalCenter; text: "Search actions"; color: Theme.faint
                       font.pixelSize: Theme.fsSmall; font.family: Theme.sans }
                Kbd { anchors.right: parent.right; anchors.rightMargin: 7; anchors.verticalCenter: parent.verticalCenter; keys: "Ctrl+K" }
                MouseArea { id: cmdMa; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: commander.open() }
            }
            Text { text: "MODEL"; color: Theme.faint; font.pixelSize: Theme.fsTiny; font.letterSpacing: Theme.caps
                   font.weight: Font.DemiBold; font.family: Theme.sans; Layout.leftMargin: 12; Layout.rightMargin: 4 }
            RCombo {
                model: studio.engines; implicitWidth: 104
                onActivated: studio.setEngine(currentText)
            }
            IconButton { icon: "sliders"; tip: "Preferences"; keys: "Ctrl+,"; onHit: preferences.open(); Layout.leftMargin: 4 }
        }
    }

    // ------------------------------------------------------------------ footer: status bar
    footer: StatusBar {
        height: window.chrome ? implicitHeight : 0
        visible: height > 0
        clip: true
        Behavior on height { NumberAnimation { duration: Theme.med } }
    }

    // ------------------------------------------------------------------ body
    RowLayout {
        anchors.fill: parent
        spacing: 0

        // tool rail
        Rectangle {
            Layout.fillHeight: true
            Layout.preferredWidth: window.chrome && window.showLeft && !window.empty ? 48 : 0
            visible: Layout.preferredWidth > 0
            clip: true
            color: Theme.header
            Behavior on Layout.preferredWidth { NumberAnimation { duration: Theme.med } }
            Rectangle { anchors.right: parent.right; width: 1; height: parent.height; color: Theme.line }
            Column {
                anchors.horizontalCenter: parent.horizontalCenter
                y: 8; spacing: 3
                IconButton { icon: "cursor"; tip: "Select"; on: viewport.tool === "select"; onHit: viewport.tool = "select" }
                IconButton { icon: "move"; tip: "Move  ·  Ctrl snaps 10 mm, Shift is free"; keys: "W"; on: viewport.tool === "move"; onHit: viewport.tool = "move" }
                IconButton { icon: "frame"; tip: "Frame everything"; keys: "H"; onHit: viewport.frameAll(true) }
                Rectangle { width: 26; height: 1; color: Theme.line; anchors.horizontalCenter: parent.horizontalCenter }
                Repeater {
                    model: ["box", "cylinder", "sphere", "torus", "capsule", "gear", "helix", "pipe", "loft"]
                    delegate: IconButton {
                        required property string modelData
                        icon: modelData; tip: "Add " + window.byId["add." + modelData].title.toLowerCase()
                        onHit: studio.addPrimitive(modelData)
                    }
                }
            }
            Column {
                anchors.horizontalCenter: parent.horizontalCenter
                anchors.bottom: parent.bottom; anchors.bottomMargin: 8; spacing: 3
                IconButton { icon: "undo"; tip: "Undo"; keys: "Ctrl+Z"; enabled: studio.canUndo; onHit: studio.undo() }
                IconButton { icon: "redo"; tip: "Redo"; keys: "Ctrl+Shift+Z"; enabled: studio.canRedo; onHit: studio.redo() }
            }
        }

        // centre: viewport + timeline
        ColumnLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 0
            Item {
                id: stage
                Layout.fillWidth: true
                Layout.fillHeight: true
                clip: true
                Rectangle {   // backdrop: the theme's studio gradient; navy for blueprint; a dark stage for Showcase
                    anchors.fill: parent
                    gradient: Gradient {
                        GradientStop { position: 0.0; color: window.present ? "#ffffff" : window.showcase ? Theme.stageTop : Qt.tint(Theme.viewTop, Qt.rgba(0.03, 0.10, 0.22, window.blueprint * 0.85)) }
                        GradientStop { position: 1.0; color: window.present ? "#e6e9ee" : window.showcase ? Theme.stageBottom : Qt.tint(Theme.viewBottom, Qt.rgba(0.01, 0.05, 0.13, window.blueprint * 0.85)) }
                    }
                }
                Shape {   // soft vignette: pulls the eye to the build
                    anchors.fill: parent
                    opacity: window.showcase || window.present ? 0 : Theme.dark ? 0.55 : 0.25
                    ShapePath {
                        strokeColor: "transparent"
                        fillGradient: RadialGradient {
                            centerX: stage.width / 2; centerY: stage.height * 0.52
                            focalX: centerX; focalY: centerY
                            centerRadius: Math.max(stage.width, stage.height) * 0.72
                            GradientStop { position: 0.0; color: "#00000000" }
                            GradientStop { position: 0.55; color: "#00000000" }
                            GradientStop { position: 1.0; color: "#d0000000" }
                        }
                        PathRectangle { x: 0; y: 0; width: stage.width; height: stage.height }
                    }
                }
                Viewport {
                    id: viewport
                    anchors.fill: parent
                    blueprint: window.blueprint
                    explode: window.explode
                    explodeGoal: window.explodeTarget
                    hidden: window.hidden
                    isolate: window.isolate
                    showcase: window.showcase
                    present: window.present
                    gridOn: window.showGrid && !window.empty
                    referenceOn: window.showReference
                    turntable: window.showcase && showcaseBar.spin
                    onPicked: (id) => studio.select(id)
                    onContextRequested: (id, x, y) => window.openContext(id, x, y)
                    onExplodeNudge: (d) => window.explodeTarget = Math.max(0, Math.min(1, window.explodeTarget + d))
                    onUserInteracted: if (studio.renderPath !== "") studio.clearRender()
                }
                Callouts {
                    anchors.fill: parent
                    viewport: viewport
                    explode: window.explode
                    isolate: window.isolate
                    hidden: window.hidden
                    visible: studio.mode === "dissect" || studio.mode === "reverse" || (window.showcase && window.explode > 0.2)
                    onChosen: (cid) => { studio.select(cid); window.isolate = window.isolate === cid ? "" : cid }
                }
                Image {   // path-traced still, cross-faded over the live view until the camera moves
                    anchors.fill: parent
                    source: studio.renderPath !== "" ? "file://" + studio.renderPath : ""
                    fillMode: Image.PreserveAspectCrop
                    opacity: studio.renderPath !== "" ? 1 : 0
                    visible: opacity > 0
                    Behavior on opacity { NumberAnimation { duration: 700 } }
                    Rectangle {
                        anchors.left: parent.left; anchors.bottom: parent.bottom; anchors.margins: 16
                        width: rl.implicitWidth + 18; height: 24; radius: 12; color: "#c0000000"
                        Text { id: rl; anchors.centerIn: parent; text: "CYCLES  ·  PATH TRACED  ·  move the camera to return to live"
                               color: "#e0e0e0"; font.pixelSize: 10; font.letterSpacing: 1; font.family: Theme.sans }
                    }
                }

                // ---- floating viewport bar: view, display, overlays
                Rectangle {
                    id: viewBar
                    visible: !window.showcase && !window.present && !window.empty
                    width: vbRow.implicitWidth + 12; height: 36; radius: 18
                    color: Theme.glass; border.color: Theme.glassLine
                    Row {
                        id: vbRow
                        anchors.centerIn: parent
                        spacing: 4
                        Rectangle {
                            width: vnRow.implicitWidth + 18; height: 28; radius: 14; anchors.verticalCenter: parent.verticalCenter
                            color: viewMenu.visible ? Theme.press : vnMa.containsMouse ? Theme.hover : "transparent"
                            Row {
                                id: vnRow
                                anchors.centerIn: parent; spacing: 5
                                Text { text: viewport.viewName; color: Theme.text; font.pixelSize: Theme.fsSmall; font.family: Theme.sans; font.weight: Font.DemiBold }
                                Icon { name: "chevronDown"; size: 11; color: Theme.dim; anchors.verticalCenter: parent.verticalCenter }
                            }
                            MouseArea { id: vnMa; anchors.fill: parent; hoverEnabled: true; onClicked: viewMenu.open() }
                            RMenu { id: viewMenu; y: parent.height + 8; implicitWidth: 230
                                    actions: window.pick(["view.persp", "view.top", "view.right", "view.front", "-", "frameAll", "frameSel"]) }
                        }
                        Rectangle { width: 1; height: 18; color: Theme.glassLine; anchors.verticalCenter: parent.verticalCenter }
                        Repeater {
                            model: [ ["shaded", "shaded", "Shaded"], ["lines", "lines", "Shaded with lines"], ["wire", "wire", "Wireframe"], ["xray", "xray", "X-ray"] ]
                            delegate: IconButton {
                                required property var modelData
                                size: 28; iconSize: 15; radius: 14; anchors.verticalCenter: parent.verticalCenter
                                icon: modelData[1]; tip: modelData[2]
                                on: viewport.displayMode === modelData[0]; onHit: viewport.displayMode = modelData[0]
                            }
                        }
                        Rectangle { width: 1; height: 18; color: Theme.glassLine; anchors.verticalCenter: parent.verticalCenter }
                        IconButton { size: 28; iconSize: 15; radius: 14; anchors.verticalCenter: parent.verticalCenter
                                     icon: "layers"; tip: "Colour by component"; keys: "C"
                                     on: viewport.colorByComponent; onHit: viewport.colorByComponent = !viewport.colorByComponent }
                        IconButton { size: 28; iconSize: 15; radius: 14; anchors.verticalCenter: parent.verticalCenter
                                     icon: "ruler"; tip: "Blueprint look"; keys: "B"
                                     on: window.blueprint > 0.5; onHit: bpAnim.go(window.blueprint > 0.5 ? 0 : 1) }
                        IconButton { size: 28; iconSize: 15; radius: 14; anchors.verticalCenter: parent.verticalCenter
                                     icon: "grid"; tip: "Floor grid"; keys: "G"; on: window.showGrid; onHit: window.showGrid = !window.showGrid }
                        IconButton { size: 28; iconSize: 15; radius: 14; anchors.verticalCenter: parent.verticalCenter
                                     visible: studio.reference.length > 0
                                     icon: "reference"; tip: "Reference images"; keys: "R"
                                     on: window.showReference; onHit: window.showReference = !window.showReference }
                    }
                }

                // ---- title card
                Column {
                    x: window.showcase ? 48 : 18; y: window.showcase ? 40 : 60
                    visible: !window.empty && !window.present
                    Text {
                        text: studio.title
                        font.family: Theme.sans; font.pixelSize: window.showcase ? 34 : 19; font.weight: Font.DemiBold
                        font.letterSpacing: window.showcase ? 0.6 : 0
                        color: window.blueprint > 0.5 ? Theme.holo : window.showcase ? "#eef2f7" : Theme.viewText
                    }
                    Text {
                        text: studio.summary; width: window.showcase ? 560 : 460; wrapMode: Text.WordWrap
                        color: window.showcase ? "#aab2bd" : Theme.viewDim; font.pixelSize: window.showcase ? 14 : Theme.fs
                        font.family: Theme.sans; lineHeight: 1.25
                        maximumLineCount: window.showcase ? 3 : 2; elide: Text.ElideRight
                        visible: text !== ""
                    }
                    Row {
                        visible: window.showcase
                        spacing: 28; topPadding: 14
                        Repeater {
                            model: [ ["DIMENSIONS", studio.dimensions.length ? studio.dimensions.map(d => Math.round(d)).join(" × ") + " mm" : "—"],
                                     ["COMPONENTS", studio.components.length], ["BUILD STEPS", studio.stepCount] ]
                            delegate: Column {
                                required property var modelData
                                Text { text: modelData[0]; color: "#6f7782"; font.pixelSize: 10; font.letterSpacing: 2; font.family: Theme.sans }
                                Text { text: modelData[1]; color: "#e6e9ee"; font.pixelSize: 16; font.family: Theme.mono }
                            }
                        }
                    }
                }

                IssuesCard {
                    visible: !window.empty && !window.showcase && !window.present && studio.mode !== "reverse"
                    x: 18; y: 118
                    onChosen: (cid) => { studio.select(cid); viewport.frameComponent(cid) }
                }

                // ---- selection read-out (bottom left)
                Rectangle {
                    visible: !window.showcase && !window.present && studio.selected !== "" && viewport.selectedGeo() !== null
                    x: 12; y: parent.height - height - 14
                    width: selRow.implicitWidth + 22; height: 30; radius: 15
                    color: Theme.glass; border.color: Qt.rgba(Theme.amber.r, Theme.amber.g, Theme.amber.b, 0.5)
                    Row {
                        id: selRow
                        anchors.centerIn: parent; spacing: 12
                        readonly property var g: { studio.selected; studio.shapes; return viewport.selectedGeo() }
                        Chip { label: "SELECTED"; value: selRow.g ? selRow.g.label : ""; labelColor: Theme.amber }
                        Chip { label: "TRIS"; value: selRow.g ? selRow.g.triangles.toLocaleString(Qt.locale(), "f", 0) : "" }
                    }
                }

                // ---- start screen
                Welcome {
                    id: welcome
                    anchors.fill: parent
                    visible: opacity > 0
                    opacity: window.empty ? 1 : 0
                    Behavior on opacity { NumberAnimation { duration: Theme.slow } }
                    onOpenFile: (path) => window.openPath(path)
                    onRunAction: (id) => window.byId[id].run()
                }

                // ---- dissect / showcase bar
                Rectangle {
                    id: showcaseBar
                    property bool spin: true
                    anchors.horizontalCenter: parent.horizontalCenter
                    y: (dream.y - height - 10) * (1 - dream.hideT) + (parent.height - height - 26) * dream.hideT
                    visible: studio.mode !== "build" && studio.mode !== "present" && !window.empty
                    width: sbRow.implicitWidth + 28; height: 42; radius: 21
                    color: Theme.glass; border.color: Theme.glassLine
                    RowLayout {
                        id: sbRow
                        anchors.centerIn: parent
                        spacing: 10
                        Text { text: "Assembled"; color: Theme.dim; font.pixelSize: Theme.fsSmall; font.family: Theme.sans }
                        RSlider { implicitWidth: 220; from: 0; to: 1; value: window.explodeTarget; onMoved: window.explodeTarget = value }
                        Text { text: "Exploded"; color: Theme.dim; font.pixelSize: Theme.fsSmall; font.family: Theme.sans }
                        Rectangle { width: 1; height: 20; color: Theme.glassLine }
                        Text { text: "Blueprint"; color: Theme.dim; font.pixelSize: Theme.fsSmall; font.family: Theme.sans; visible: !window.showcase }
                        RSlider { visible: !window.showcase; implicitWidth: 110; from: 0; to: 1; value: window.blueprint; onMoved: window.blueprint = value }
                        Pill { visible: window.showcase; icon: "spin"; text: showcaseBar.spin ? "Turntable on" : "Turntable off"; onHit: showcaseBar.spin = !showcaseBar.spin }
                        Pill {
                            visible: window.showcase; icon: "render"
                            text: studio.busy.indexOf("Render") === 0 ? "Rendering…" : "Render  ·  Cycles"
                            primary: true; enabled: studio.busy === ""
                            onHit: { showcaseBar.spin = false; studio.renderShowcase(viewport.cameraJson()) }
                        }
                        Pill { visible: window.showcase; text: "Exit  Esc"; onHit: window.setMode("build") }
                    }
                }

                // ---- the dream capsule: centred on the start screen, docked at the bottom while you work
                Rectangle {
                    id: dream
                    anchors.horizontalCenter: parent.horizontalCenter
                    // two eased factors instead of a Behavior on y: the dock follows layout changes exactly
                    property real startT: window.empty ? 1 : 0       // 1 = parked in the start screen
                    property real hideT: window.showcase || window.present ? 1 : 0     // 1 = slid out under the stage
                    Behavior on startT { NumberAnimation { duration: Theme.slow; easing.type: Easing.OutCubic } }
                    Behavior on hideT { NumberAnimation { duration: Theme.med } }
                    y: (parent.height - height - 14) * (1 - startT) + welcome.capsuleY * startT + hideT * (height + 40)
                    width: Math.min(parent.width - 40, window.empty ? 760 : 860); height: window.empty ? 54 : 46; radius: height / 2
                    color: Theme.glass
                    border.color: prompt.activeFocus ? Theme.accent : Theme.glassLine
                    border.width: prompt.activeFocus ? 1.5 : 1
                    Rectangle {   // focus glow
                        anchors.fill: parent; anchors.margins: -4; radius: height / 2; z: -1
                        color: "transparent"; border.width: 4
                        border.color: Qt.rgba(Theme.accent.r, Theme.accent.g, Theme.accent.b, prompt.activeFocus ? 0.16 : 0)
                        Behavior on border.color { ColorAnimation { duration: Theme.med } }
                    }
                    RowLayout {
                        anchors.fill: parent; anchors.leftMargin: 8; anchors.rightMargin: 8; spacing: 8
                        Rectangle {
                            id: modeChip
                            property bool editMode: false
                            readonly property bool edit: editMode && !window.empty
                            implicitWidth: mcRow.implicitWidth + 22; implicitHeight: dream.height - 16; radius: height / 2
                            color: edit ? Qt.rgba(Theme.amber.r, Theme.amber.g, Theme.amber.b, 0.16) : Theme.accentSoft
                            Row {
                                id: mcRow
                                anchors.centerIn: parent; spacing: 6
                                Icon { name: modeChip.edit ? "pencil" : "sparkle"; size: 14; color: modeChip.edit ? Theme.amber : Theme.accentHi
                                       anchors.verticalCenter: parent.verticalCenter }
                                Text { text: modeChip.edit ? "EDIT" : "DREAM"; color: modeChip.edit ? Theme.amber : Theme.accentHi
                                       font.pixelSize: Theme.fsSmall; font.weight: Font.Bold; font.letterSpacing: 1.5; font.family: Theme.sans
                                       anchors.verticalCenter: parent.verticalCenter }
                            }
                            MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: modeChip.editMode = !modeChip.editMode }
                            ToolTip.visible: false
                        }
                        TextField {
                            id: prompt
                            Layout.fillWidth: true
                            background: null
                            color: Theme.text; font.pixelSize: window.empty ? 15 : 14; font.family: Theme.sans
                            placeholderTextColor: Theme.faint
                            selectionColor: Theme.accent; selectedTextColor: Theme.onAccent
                            placeholderText: modeChip.edit ? "Change it: \"make the reverser doors longer, add a second intake ring\""
                                                           : "Dream it: \"a rocket engine with a regenerative nozzle and turbopumps\""
                            enabled: studio.busy === ""
                            onAccepted: go()
                            function go() {
                                if (!text.trim()) return
                                if (modeChip.edit) studio.edit(text); else studio.dream(text)
                            }
                        }
                        Pill {
                            primary: true; enabled: studio.busy === ""
                            implicitHeight: dream.height - 14; implicitWidth: 118
                            text: studio.busy !== "" ? "Working…" : modeChip.edit ? "Apply" : "Replicate"
                            onHit: prompt.go()
                        }
                    }
                }
                Presenter {
                    id: presenter
                    anchors.fill: parent
                    window: window
                    viewport: viewport
                }
            }
            Timeline {
                id: timeline
                Layout.fillWidth: true
                Layout.preferredHeight: window.chrome && window.showTimeline && !window.empty ? implicitHeight : 0
                visible: Layout.preferredHeight > 0
                clip: true
                Behavior on Layout.preferredHeight { NumberAnimation { duration: Theme.med } }
            }
        }

        // right: managers / ledger / materials / console
        Rectangle {
            id: rightDock
            Layout.fillHeight: true
            Layout.preferredWidth: window.chrome && window.showRight && !window.empty ? window.rightWidth : 0
            visible: Layout.preferredWidth > 0
            clip: true
            color: Theme.panel
            Behavior on Layout.preferredWidth { enabled: !grip.pressed; NumberAnimation { duration: Theme.med } }
            Rectangle { width: 1; height: parent.height; color: Theme.line }
            MouseArea {   // drag the edge to resize the dock
                id: grip
                width: 6; height: parent.height; x: -3; z: 5
                cursorShape: Qt.SizeHorCursor
                hoverEnabled: true
                property real startX: 0
                property real startW: 0
                onPressed: (m) => { startX = mapToItem(null, m.x, 0).x; startW = window.rightWidth }
                onPositionChanged: (m) => { if (pressed) window.rightWidth = Math.max(300, Math.min(620, startW - (mapToItem(null, m.x, 0).x - startX))) }
                Rectangle { anchors.centerIn: parent; width: 2; height: parent.height; color: Theme.accent; opacity: grip.containsMouse || grip.pressed ? 0.7 : 0 }
            }
            SplitView {
                anchors.fill: parent
                anchors.leftMargin: 1
                orientation: Qt.Vertical
                handle: Rectangle {
                    implicitHeight: 5; color: SplitHandle.hovered || SplitHandle.pressed ? Theme.accentSoft : Theme.header
                    Rectangle { anchors.centerIn: parent; width: 28; height: 2; radius: 1; color: Theme.line }
                }
                ColumnLayout {
                    SplitView.preferredHeight: parent.height * (studio.mode === "reverse" ? 0.56 : 0.42)
                    SplitView.minimumHeight: 120
                    spacing: 0
                    DockHeader {
                        title: studio.mode === "reverse" ? "Reverse engineering" : "Objects"
                        icon: studio.mode === "reverse" ? "reverse" : "layers"
                        count: studio.mode === "reverse" ? "" : (studio.components.length ? String(studio.components.length) : "")
                        IconButton { size: 26; iconSize: 14; icon: "eye"; tip: "Show everything"
                                     visible: studio.mode !== "reverse"; onHit: { window.hidden = ({}); window.isolate = "" } }
                    }
                    HolodeckPanel { Layout.fillWidth: true; visible: studio.mode === "reverse" }
                    ObjectManager {
                        Layout.fillWidth: true; Layout.fillHeight: true
                        visible: studio.mode !== "reverse"
                        hidden: window.hidden; isolate: window.isolate
                        onToggleHidden: (cid) => window.toggleHidden(cid)
                        onIsolateComponent: (cid) => window.isolate = cid
                        onPlayComponent: (cid) => window.playComponent(cid)
                        onContextRequested: (cid, x, y) => window.openContext(cid, x, y)
                    }
                    LedgerPanel {
                        Layout.fillWidth: true; Layout.fillHeight: true
                        visible: studio.mode === "reverse"
                        onImportRequested: importDlg.open()
                        onDisassemble: { window.explodeTarget = 0; timeline.play(-1) }
                    }
                }
                ColumnLayout {
                    SplitView.fillHeight: true
                    spacing: 0
                    Rectangle {
                        Layout.fillWidth: true; implicitHeight: Theme.bar; color: Theme.header
                        Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: 1; color: Theme.line }
                        Row {
                            x: 4; height: parent.height
                            Repeater {
                                model: [ [studio.mode === "reverse" ? "Objects" : "Attributes", studio.mode === "reverse" ? "layers" : "sliders"],
                                         ["Materials", "material"], ["Console", "terminal"] ]
                                delegate: Item {
                                    id: tab
                                    required property var modelData
                                    required property int index
                                    readonly property bool sel: window.rightTab === index
                                    width: tabRow.implicitWidth + 22; height: parent.height
                                    Row {
                                        id: tabRow
                                        anchors.centerIn: parent; spacing: 6
                                        Icon { name: tab.modelData[1]; size: 13; color: tab.sel ? Theme.accentHi : Theme.faint; anchors.verticalCenter: parent.verticalCenter }
                                        Text { text: tab.modelData[0].toUpperCase(); anchors.verticalCenter: parent.verticalCenter
                                               font.pixelSize: Theme.fsTiny; font.weight: Font.DemiBold; font.letterSpacing: Theme.caps; font.family: Theme.sans
                                               color: tab.sel ? Theme.text : tabMa.containsMouse ? Theme.text : Theme.dim }
                                    }
                                    Rectangle { anchors.bottom: parent.bottom; anchors.horizontalCenter: parent.horizontalCenter
                                                width: parent.width - 12; height: 2; radius: 1; color: tab.sel ? Theme.accent : "transparent" }
                                    MouseArea { id: tabMa; anchors.fill: parent; hoverEnabled: true; onClicked: window.rightTab = tab.index }
                                }
                            }
                        }
                    }
                    StackLayout {
                        Layout.fillWidth: true; Layout.fillHeight: true
                        currentIndex: window.rightTab
                        Item {
                            AttributeManager { anchors.fill: parent; visible: studio.mode !== "reverse" }
                            ObjectManager {
                                anchors.fill: parent; visible: studio.mode === "reverse"
                                hidden: window.hidden; isolate: window.isolate
                                onToggleHidden: (cid) => window.toggleHidden(cid)
                                onIsolateComponent: (cid) => window.isolate = cid
                                onPlayComponent: (cid) => window.playComponent(cid)
                                onContextRequested: (cid, x, y) => window.openContext(cid, x, y)
                            }
                        }
                        MaterialShelf {}
                        Rectangle {
                            color: Theme.field
                            ScrollView {
                                anchors.fill: parent
                                TextArea {
                                    readOnly: true; text: studio.log; wrapMode: TextEdit.Wrap
                                    font.family: Theme.mono; font.pixelSize: Theme.fsTiny; color: Theme.dim
                                    selectionColor: Theme.accent; selectedTextColor: Theme.onAccent
                                    background: null
                                    onTextChanged: cursorPosition = length
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
