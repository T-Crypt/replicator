import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Dialogs

// Replicator: a Cinema 4D-style workspace. Menus and mode tabs on top, tool palette on the left, the viewport in
// the middle with the dream capsule, Object + Attribute managers (or the evidence ledger) on the right, the build
// timeline along the bottom. Modes: Build, Dissect (exploded views), Reverse (take a model apart), Showcase.
ApplicationWindow {
    id: window
    width: 1760
    height: 1020
    visible: true
    title: "Replicator — " + studio.title
    color: Theme.bg

    property real blueprint: 0.0
    property real explodeTarget: 0.0
    property real explode: explodeTarget
    Behavior on explode { NumberAnimation { duration: 650; easing.type: Easing.OutCubic } }
    property var hidden: ({})
    property string isolate: ""
    readonly property bool showcase: studio.mode === "showcase"
    property bool needFrame: true

    function setMode(m) {
        studio.setMode(m)
        if (m === "build") { explodeTarget = 0; viewport.colorByComponent = false; isolate = "" }
        if (m === "dissect") { explodeTarget = Math.max(explodeTarget, 0.8); viewport.colorByComponent = true; viewport.frameAll(true) }
        if (m === "build") viewport.frameAll(true)
        if (m === "reverse") { viewport.colorByComponent = true }
        if (m === "showcase") { timeline.stop(); studio.setStep(studio.stepCount - 1); viewport.colorByComponent = false
                                viewport.heroAngle(); viewport.frameAll(true) }
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
        nameFilters: ["Replicator programs and models (*.json *.glb *.gltf *.obj *.stl *.ply)", "BuildProgram (*.json)",
                      "3D models (*.glb *.gltf *.obj *.stl *.ply)"]
        onAccepted: { studio.openFile(selectedFile.toString()); if (studio.mode === "build") timeline.play(1) }
    }
    FileDialog {
        id: importDlg
        title: "Import a model to reverse engineer"
        nameFilters: ["3D models (*.glb *.gltf *.obj *.stl *.ply)"]
        onAccepted: studio.importModel(selectedFile.toString())
    }

    Shortcut { sequences: [StandardKey.Undo]; onActivated: studio.undo() }
    Shortcut { sequence: "Ctrl+O"; onActivated: openDlg.open() }
    Shortcut { sequence: "Ctrl+I"; onActivated: importDlg.open() }
    Shortcut { sequence: "Space"; onActivated: timeline.playDir !== 0 ? timeline.stop() : timeline.play(1) }
    Shortcut { sequence: "1"; onActivated: window.setMode("build") }
    Shortcut { sequence: "2"; onActivated: window.setMode("dissect") }
    Shortcut { sequence: "3"; onActivated: window.setMode("reverse") }
    Shortcut { sequence: "4"; onActivated: window.setMode("showcase") }
    Shortcut { sequence: "Esc"; enabled: window.showcase; onActivated: window.setMode("build") }

    // ------------------------------------------------------------------ header: menus, mode tabs, engine
    header: Rectangle {
        height: window.showcase ? 0 : 40
        visible: height > 0
        color: Theme.header
        Behavior on height { NumberAnimation { duration: 250 } }
        Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: 1; color: Theme.line }
        RowLayout {
            anchors.fill: parent
            anchors.leftMargin: 12; anchors.rightMargin: 12
            spacing: 4
            Text { text: "REPLICATOR"; color: Theme.text; font.bold: true; font.letterSpacing: 4; font.pixelSize: 13 }
            Item { width: 14 }
            HeaderMenu {
                text: "File"
                items: [ ["Open…  (Ctrl+O)", () => openDlg.open()], ["Import model to reverse engineer…  (Ctrl+I)", () => importDlg.open()],
                         ["Export GLB", () => studio.exportAs("glb")], ["Export STL (3D print)", () => studio.exportAs("stl")],
                         ["Export OBJ", () => studio.exportAs("obj")] ]
            }
            HeaderMenu {
                text: "Edit"
                items: [ ["Undo  (Ctrl+Z)", () => studio.undo()], ["Deselect  (Esc)", () => studio.select("")] ]
            }
            HeaderMenu {
                text: "Create"
                items: ["box", "cylinder", "sphere", "torus", "capsule", "gear", "helix", "loft", "pipe"]
                       .map(k => [k.charAt(0).toUpperCase() + k.slice(1), () => studio.addPrimitive(k)])
            }
            HeaderMenu {
                text: "View"
                items: [ ["Frame all  (H)", () => viewport.frameAll(true)], ["Frame selected  (F)", () => viewport.frameSelected()],
                         ["Perspective  (F1)", () => viewport.setView("Perspective")], ["Top  (F2)", () => viewport.setView("Top")],
                         ["Right  (F3)", () => viewport.setView("Right")], ["Front  (F4)", () => viewport.setView("Front")],
                         ["Shaded", () => viewport.displayMode = "shaded"], ["Shaded + lines", () => viewport.displayMode = "lines"],
                         ["Wireframe", () => viewport.displayMode = "wire"], ["X-ray", () => viewport.displayMode = "xray"] ]
            }
            HeaderMenu {
                text: "Render"
                items: [ ["Showcase  (4)", () => window.setMode("showcase")],
                         ["Render still (Cycles, CPU)", () => studio.renderShowcase(viewport.cameraJson())] ]
            }
            Item { Layout.fillWidth: true }
            Row {   // mode tabs
                spacing: 2
                Repeater {
                    model: [ ["build", "Build", "1"], ["dissect", "Dissect", "2"], ["reverse", "Reverse", "3"], ["showcase", "Showcase", "4"] ]
                    delegate: Rectangle {
                        required property var modelData
                        width: 104; height: 28; radius: 5
                        color: studio.mode === modelData[0] ? Theme.accent : tabMa.containsMouse ? Theme.panel2 : Theme.panel
                        Text {
                            anchors.centerIn: parent
                            text: parent.modelData[1]
                            color: studio.mode === parent.modelData[0] ? "white" : Theme.text
                            font.pixelSize: Theme.fs; font.bold: studio.mode === parent.modelData[0]
                        }
                        Text { anchors.right: parent.right; anchors.rightMargin: 6; anchors.verticalCenter: parent.verticalCenter
                               text: parent.modelData[2]; color: "#80ffffff"; font.pixelSize: 9 }
                        MouseArea { id: tabMa; anchors.fill: parent; hoverEnabled: true; onClicked: window.setMode(parent.modelData[0]) }
                    }
                }
            }
            Item { Layout.fillWidth: true }
            BusyIndicator { running: studio.busy !== ""; visible: running; implicitWidth: 22; implicitHeight: 22 }
            Text { text: studio.busy; color: Theme.holo; font.pixelSize: Theme.fsSmall; visible: studio.busy !== "" }
            Text { text: "model"; color: Theme.dim; font.pixelSize: Theme.fsSmall; Layout.leftMargin: 8 }
            ComboBox {
                model: studio.engines; implicitWidth: 96; implicitHeight: 26
                onActivated: studio.setEngine(currentText)
            }
        }
    }

    // ------------------------------------------------------------------ body
    RowLayout {
        anchors.fill: parent
        spacing: 0

        // tool palette (C4D left strip)
        Rectangle {
            Layout.fillHeight: true
            Layout.preferredWidth: window.showcase ? 0 : 46
            visible: Layout.preferredWidth > 0
            color: Theme.header
            Behavior on Layout.preferredWidth { NumberAnimation { duration: 250 } }
            Rectangle { anchors.right: parent.right; width: 1; height: parent.height; color: Theme.line }
            Column {
                anchors.horizontalCenter: parent.horizontalCenter
                y: 8; spacing: 4
                ToolGlyph { glyph: "↖"; tip: "Select"; on: viewport.tool === "select"; onHit: viewport.tool = "select" }
                ToolGlyph { glyph: "✥"; tip: "Move gizmo (W)  ·  Ctrl snaps 10 mm"; on: viewport.tool === "move"; onHit: viewport.tool = "move" }
                ToolGlyph { glyph: "⌖"; tip: "Frame all (H)"; onHit: viewport.frameAll(true) }
                Rectangle { width: 30; height: 1; color: Theme.line }
                ToolGlyph { glyph: "■"; tip: "Shaded"; on: viewport.displayMode === "shaded"; onHit: viewport.displayMode = "shaded" }
                ToolGlyph { glyph: "▣"; tip: "Shaded + lines"; on: viewport.displayMode === "lines"; onHit: viewport.displayMode = "lines" }
                ToolGlyph { glyph: "▢"; tip: "Wireframe"; on: viewport.displayMode === "wire"; onHit: viewport.displayMode = "wire" }
                ToolGlyph { glyph: "◌"; tip: "X-ray"; on: viewport.displayMode === "xray"; onHit: viewport.displayMode = "xray" }
                ToolGlyph { glyph: "◐"; tip: "Colour by component"; on: viewport.colorByComponent; onHit: viewport.colorByComponent = !viewport.colorByComponent }
                Rectangle { width: 30; height: 1; color: Theme.line }
                ToolGlyph { glyph: "⬚"; tip: "Add box"; onHit: studio.addPrimitive("box") }
                ToolGlyph { glyph: "⬭"; tip: "Add cylinder"; onHit: studio.addPrimitive("cylinder") }
                ToolGlyph { glyph: "●"; tip: "Add sphere"; onHit: studio.addPrimitive("sphere") }
                ToolGlyph { glyph: "⚙"; tip: "Add gear"; onHit: studio.addPrimitive("gear") }
                ToolGlyph { glyph: "➰"; tip: "Add spring (helix)"; onHit: studio.addPrimitive("helix") }
                ToolGlyph { glyph: "⌒"; tip: "Add pipe"; onHit: studio.addPrimitive("pipe") }
                ToolGlyph { glyph: "⧖"; tip: "Add loft"; onHit: studio.addPrimitive("loft") }
            }
        }

        // centre: viewport + timeline
        ColumnLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 0
            Item {
                Layout.fillWidth: true
                Layout.fillHeight: true
                clip: true
                Rectangle {   // backdrop: C4D grey gradient; navy for blueprint; a dark stage for Showcase
                    anchors.fill: parent
                    gradient: Gradient {
                        GradientStop { position: 0.0; color: window.showcase ? "#14161a" : Qt.tint(Theme.viewportBg, Qt.rgba(0.04, 0.1, 0.2, window.blueprint)) }
                        GradientStop { position: 1.0; color: window.showcase ? "#050506" : Qt.tint(Theme.viewportBg2, Qt.rgba(0.02, 0.07, 0.16, window.blueprint)) }
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
                    turntable: window.showcase && showcaseBar.spin
                    onPicked: (id) => studio.select(id)
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
                        width: rl.implicitWidth + 16; height: 22; radius: 4; color: "#c0000000"
                        Text { id: rl; anchors.centerIn: parent; text: "CYCLES · PATH TRACED · move to return to live"; color: "#e0e0e0"; font.pixelSize: 10; font.letterSpacing: 1 }
                    }
                }

                // title card (top left)
                Column {
                    x: window.showcase ? 48 : 16; y: window.showcase ? 40 : 30
                    spacing: 4
                    visible: studio.stepCount > 0
                    Text {
                        text: studio.title
                        font.pixelSize: window.showcase ? 34 : 18; font.bold: true; font.letterSpacing: window.showcase ? 1 : 0
                        color: window.blueprint > 0.5 ? Theme.holo : "#eef1f5"
                    }
                    Text {
                        text: studio.summary; width: window.showcase ? 560 : 480; wrapMode: Text.WordWrap
                        color: window.showcase ? "#aab2bd" : Theme.dim; font.pixelSize: window.showcase ? 14 : 12
                        maximumLineCount: 3; elide: Text.ElideRight
                    }
                    Row {
                        visible: window.showcase
                        spacing: 28; topPadding: 14
                        Repeater {
                            model: [ ["DIMENSIONS", studio.dimensions.length ? studio.dimensions.map(d => Math.round(d)).join(" × ") + " mm" : "—"],
                                     ["COMPONENTS", studio.components.length], ["BUILD STEPS", studio.stepCount] ]
                            delegate: Column {
                                required property var modelData
                                Text { text: modelData[0]; color: "#6f7782"; font.pixelSize: 10; font.letterSpacing: 2 }
                                Text { text: modelData[1]; color: "#e6e9ee"; font.pixelSize: 16; font.family: Theme.mono }
                            }
                        }
                    }
                }

                // dissect / showcase bar (bottom centre)
                Rectangle {
                    id: showcaseBar
                    property bool spin: true
                    anchors.horizontalCenter: parent.horizontalCenter
                    y: window.showcase ? parent.height - height - 26 : dream.y - height - 10
                    Behavior on y { NumberAnimation { duration: 250 } }
                    visible: studio.mode !== "build" && studio.stepCount > 0
                    width: sbRow.implicitWidth + 24; height: 40; radius: 20
                    color: "#d01c1e22"; border.color: Theme.line
                    RowLayout {
                        id: sbRow
                        anchors.centerIn: parent
                        spacing: 10
                        Text { text: "Assembled"; color: Theme.dim; font.pixelSize: Theme.fsSmall }
                        Slider {
                            implicitWidth: 220
                            from: 0; to: 1; value: window.explodeTarget
                            onMoved: window.explodeTarget = value
                        }
                        Text { text: "Exploded"; color: Theme.dim; font.pixelSize: Theme.fsSmall }
                        Rectangle { width: 1; height: 20; color: Theme.line }
                        Text { text: "Blueprint"; color: Theme.dim; font.pixelSize: Theme.fsSmall; visible: !window.showcase }
                        Slider {
                            visible: !window.showcase
                            implicitWidth: 110; from: 0; to: 1; value: window.blueprint
                            onMoved: window.blueprint = value
                        }
                        Pill { visible: window.showcase; text: showcaseBar.spin ? "Turntable ●" : "Turntable ○"; onHit: showcaseBar.spin = !showcaseBar.spin }
                        Pill {
                            visible: window.showcase; text: studio.busy.indexOf("Render") === 0 ? "Rendering…" : "Render  ·  Cycles"
                            primary: true; enabled: studio.busy === ""
                            onHit: { showcaseBar.spin = false; studio.renderShowcase(viewport.cameraJson()) }
                        }
                        Pill { visible: window.showcase; text: "Exit  Esc"; onHit: window.setMode("build") }
                    }
                }

                // the dream capsule (bottom)
                Rectangle {
                    id: dream
                    anchors.horizontalCenter: parent.horizontalCenter
                    anchors.bottom: parent.bottom; anchors.bottomMargin: window.showcase ? -height - 20 : 14
                    Behavior on anchors.bottomMargin { NumberAnimation { duration: 250 } }
                    width: Math.min(parent.width - 40, 860); height: 46; radius: 23
                    color: "#e81c1e22"; border.color: prompt.activeFocus ? Theme.holo : Theme.line
                    RowLayout {
                        anchors.fill: parent; anchors.leftMargin: 8; anchors.rightMargin: 8; spacing: 8
                        Rectangle {
                            implicitWidth: modeTxt.implicitWidth + 20; implicitHeight: 30; radius: 15
                            color: editMode ? "#3d3220" : "#1d3346"
                            property bool editMode: false
                            id: modeChip
                            Text { id: modeTxt; anchors.centerIn: parent; text: modeChip.editMode ? "EDIT" : "DREAM"
                                   color: modeChip.editMode ? Theme.inferred : Theme.holo; font.pixelSize: 11; font.bold: true; font.letterSpacing: 1.5 }
                            MouseArea { anchors.fill: parent; onClicked: modeChip.editMode = !modeChip.editMode }
                        }
                        TextField {
                            id: prompt
                            Layout.fillWidth: true
                            background: null
                            color: Theme.text; font.pixelSize: 14
                            placeholderTextColor: Theme.faint
                            placeholderText: modeChip.editMode ? "Change it: \"make the reverser doors longer, add a second intake ring\""
                                                               : "Dream it: \"a rocket engine with a regenerative nozzle and turbopumps\""
                            enabled: studio.busy === ""
                            onAccepted: go()
                            function go() {
                                if (!text.trim()) return
                                if (modeChip.editMode) studio.edit(text); else studio.dream(text)
                            }
                        }
                        Rectangle {
                            implicitWidth: 112; implicitHeight: 32; radius: 16
                            color: studio.busy !== "" ? Theme.panel2 : goMa.containsMouse ? Theme.accentHi : Theme.accent
                            Text { anchors.centerIn: parent; text: studio.busy !== "" ? "Working…" : modeChip.editMode ? "Apply" : "Replicate"
                                   color: "white"; font.pixelSize: 13; font.bold: true }
                            MouseArea { id: goMa; anchors.fill: parent; hoverEnabled: true; enabled: studio.busy === ""; onClicked: prompt.go() }
                        }
                    }
                }
                Text {   // last log line under the capsule
                    anchors.horizontalCenter: dream.horizontalCenter
                    anchors.top: dream.bottom; anchors.topMargin: 1
                    visible: !window.showcase
                    text: studio.lastLog; color: Theme.faint; font.pixelSize: 10; font.family: Theme.mono
                    width: dream.width; elide: Text.ElideRight; horizontalAlignment: Text.AlignHCenter
                }
            }
            Timeline {
                id: timeline
                Layout.fillWidth: true
                Layout.preferredHeight: window.showcase ? 0 : 92
                visible: Layout.preferredHeight > 0
                Behavior on Layout.preferredHeight { NumberAnimation { duration: 250 } }
                onPlayDirChanged: if (playDir === 0 && playlist.length === 0) window.isolate = window.isolate
            }
        }

        // right: managers / ledger / console
        Rectangle {
            Layout.fillHeight: true
            Layout.preferredWidth: window.showcase ? 0 : 380
            visible: Layout.preferredWidth > 0
            color: Theme.panel
            Behavior on Layout.preferredWidth { NumberAnimation { duration: 250 } }
            Rectangle { width: 1; height: parent.height; color: Theme.line }
            SplitView {
                anchors.fill: parent
                anchors.leftMargin: 1
                orientation: Qt.Vertical
                ColumnLayout {
                    SplitView.preferredHeight: parent.height * 0.42
                    SplitView.minimumHeight: 120
                    spacing: 0
                    DockHeader { title: studio.mode === "reverse" ? "Reverse engineering" : "Objects" }
                    ObjectManager {
                        Layout.fillWidth: true; Layout.fillHeight: true
                        visible: studio.mode !== "reverse"
                        hidden: window.hidden; isolate: window.isolate
                        onToggleHidden: (cid) => window.toggleHidden(cid)
                        onIsolateComponent: (cid) => window.isolate = cid
                        onPlayComponent: (cid) => window.playComponent(cid)
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
                        Layout.fillWidth: true; implicitHeight: 28; color: Theme.header
                        property int currentIndex: 0
                        id: rightTabs
                        Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: 1; color: Theme.line }
                        Row {
                            Repeater {
                                model: [studio.mode === "reverse" ? "OBJECTS" : "ATTRIBUTES", "CONSOLE"]
                                delegate: Rectangle {
                                    required property var modelData
                                    required property int index
                                    width: 120; height: 28
                                    color: rightTabs.currentIndex === index ? Theme.panel : "transparent"
                                    Text { anchors.centerIn: parent; text: parent.modelData; font.pixelSize: 10; font.bold: true
                                           font.letterSpacing: 1.6; color: rightTabs.currentIndex === parent.index ? Theme.text : Theme.dim }
                                    Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: 2
                                                color: rightTabs.currentIndex === parent.index ? Theme.accent : "transparent" }
                                    MouseArea { anchors.fill: parent; onClicked: rightTabs.currentIndex = parent.index }
                                }
                            }
                        }
                    }
                    StackLayout {
                        Layout.fillWidth: true; Layout.fillHeight: true
                        currentIndex: rightTabs.currentIndex
                        Item {
                            AttributeManager { anchors.fill: parent; visible: studio.mode !== "reverse" }
                            ObjectManager {
                                anchors.fill: parent; visible: studio.mode === "reverse"
                                hidden: window.hidden; isolate: window.isolate
                                onToggleHidden: (cid) => window.toggleHidden(cid)
                                onIsolateComponent: (cid) => window.isolate = cid
                                onPlayComponent: (cid) => window.playComponent(cid)
                            }
                        }
                        ScrollView {
                            TextArea {
                                readOnly: true; text: studio.log; wrapMode: TextEdit.Wrap
                                font.family: Theme.mono; font.pixelSize: 10; color: Theme.dim
                                background: Rectangle { color: Theme.field }
                                onTextChanged: cursorPosition = length
                            }
                        }
                    }
                }
            }
        }
    }

    component DockHeader: Rectangle {
        property string title
        Layout.fillWidth: true
        implicitHeight: 28
        color: Theme.header
        Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: 1; color: Theme.line }
        Text { anchors.verticalCenter: parent.verticalCenter; x: 10; text: parent.title.toUpperCase()
               color: Theme.dim; font.pixelSize: 10; font.bold: true; font.letterSpacing: 1.6 }
    }
    component ToolGlyph: Rectangle {
        property string glyph
        property string tip
        property bool on: false
        signal hit()
        width: 34; height: 32; radius: 5
        color: on ? Theme.accent : tgMa.containsMouse ? Theme.panel2 : "transparent"
        Text { anchors.centerIn: parent; text: parent.glyph; color: parent.on ? "white" : Theme.text; font.pixelSize: 15 }
        MouseArea { id: tgMa; anchors.fill: parent; hoverEnabled: true; onClicked: parent.hit() }
        ToolTip.visible: tgMa.containsMouse; ToolTip.text: tip; ToolTip.delay: 400
    }
    component HeaderMenu: ToolButton {
        id: hm
        property var items: []
        contentItem: Text { text: hm.text; color: Theme.text; font.pixelSize: Theme.fs; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter }
        background: Rectangle { color: hm.hovered || menu.visible ? Theme.panel2 : "transparent"; radius: 4 }
        onClicked: menu.popup(0, height)
        Menu {
            id: menu
            Repeater {
                model: hm.items
                delegate: MenuItem {
                    required property var modelData
                    text: modelData[0]
                    onTriggered: modelData[1]()
                }
            }
        }
    }
}
