import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Dialogs

ApplicationWindow {
    id: win
    width: 1720
    height: 1000
    visible: true
    title: "Replicator — " + studio.title
    color: theme.bg

    QtObject {
        id: theme
        readonly property color bg: "#e4e6ea"
        readonly property color panel: "#f3f4f6"
        readonly property color line: "#c9ccd2"
        readonly property color text: "#22252b"
        readonly property color dim: "#6b707a"
        readonly property color accent: "#1f8fd6"
        readonly property color holo: "#33c6ff"
        readonly property string mono: "JetBrains Mono"
    }

    property bool playing: false

    Timer {   // Play build: one step per reveal, like the Holodeck's arrival
        id: player
        interval: viewport.revealMs + 250
        repeat: true
        running: win.playing
        onTriggered: {
            if (studio.step >= studio.stepCount - 1) { win.playing = false; return }
            studio.setStep(studio.step + 1)
        }
    }

    property bool needFrame: false
    Connections {   // frame once the new build's bounds are known (shapes rebuild after the program changes)
        target: studio
        function onProgramChanged() { win.needFrame = true }
        function onShapesChanged() { if (win.needFrame) { win.needFrame = false; viewport.frame() } }
    }

    FileDialog {
        id: openDlg
        title: "Open a BuildProgram"
        nameFilters: ["BuildProgram (*.json)"]
        onAccepted: { studio.openFile(selectedFile.toString()); win.playing = true }
    }

    header: ToolBar {
        background: Rectangle { color: theme.panel; Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: 1; color: theme.line } }
        RowLayout {
            anchors.fill: parent
            anchors.leftMargin: 12
            anchors.rightMargin: 12
            spacing: 10
            Label {
                text: "REPLICATOR"
                font.letterSpacing: 4
                font.bold: true
                color: theme.text
            }
            Label { text: "you dream it, you build it"; color: theme.dim; font.italic: true }
            ToolSeparator {}
            ToolButton { text: "Open"; onClicked: openDlg.open() }
            ToolButton { text: "Undo"; onClicked: studio.undo() }
            ToolSeparator {}
            ToolButton {
                text: win.playing ? "Pause" : "Play build"
                enabled: studio.stepCount > 0
                onClicked: {
                    if (!win.playing && studio.step >= studio.stepCount - 1) studio.setStep(0)
                    win.playing = !win.playing
                }
            }
            Slider {
                id: stepSlider
                Layout.preferredWidth: 260
                from: 0; to: Math.max(studio.stepCount - 1, 0); stepSize: 1
                value: studio.step
                enabled: studio.stepCount > 1
                onMoved: { win.playing = false; studio.setStep(value) }
            }
            Label { text: studio.stepCount ? ("step " + (studio.step + 1) + " / " + studio.stepCount) : "no build"; color: theme.dim }
            Item { Layout.fillWidth: true }
            Label { text: "Real"; color: theme.dim }
            Slider {
                id: bpSlider
                objectName: "bpSlider"
                Layout.preferredWidth: 160
                from: 0; to: 1; value: 0
            }
            Label { text: "Blueprint"; color: theme.dim }
            ToolSeparator {}
            ToolButton { text: "Export GLB"; enabled: studio.stepCount > 0; onClicked: studio.exportAs("glb") }
            ToolButton { text: "Export STL"; enabled: studio.stepCount > 0; onClicked: studio.exportAs("stl") }
        }
    }

    SplitView {
        anchors.fill: parent
        orientation: Qt.Horizontal

        // ---------- left dock: outliner + build steps ----------
        Pane {
            SplitView.preferredWidth: 300
            SplitView.minimumWidth: 200
            background: Rectangle { color: theme.panel }
            padding: 0
            ColumnLayout {
                anchors.fill: parent
                spacing: 0
                DockHeader { text: "Build steps" }
                ListView {
                    id: stepList
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    clip: true
                    model: studio.ops
                    currentIndex: studio.step
                    delegate: ItemDelegate {
                        required property var modelData
                        required property int index
                        width: ListView.view.width
                        height: 34
                        highlighted: index === studio.step
                        onClicked: { win.playing = false; studio.setStep(index); studio.select(modelData.id) }
                        contentItem: RowLayout {
                            spacing: 8
                            Rectangle {
                                width: 22; height: 22; radius: 11
                                color: index <= studio.step ? theme.holo : "transparent"
                                border.color: index <= studio.step ? theme.holo : theme.line
                                Label { anchors.centerIn: parent; text: index + 1; font.pixelSize: 10; color: index <= studio.step ? "white" : theme.dim }
                            }
                            ColumnLayout {
                                spacing: 0
                                Layout.fillWidth: true
                                Label {
                                    text: modelData.label
                                    color: theme.text
                                    elide: Text.ElideRight
                                    Layout.fillWidth: true
                                    font.strikeout: modelData.consumedAt >= 0 && modelData.consumedAt <= studio.step
                                }
                                Label { text: modelData.op + (modelData.part ? " · " + modelData.part : ""); color: theme.dim; font.pixelSize: 10 }
                            }
                        }
                    }
                }
            }
        }

        // ---------- center: viewport + dream bar ----------
        ColumnLayout {
            SplitView.fillWidth: true
            spacing: 0
            Viewport {
                id: viewport
                Layout.fillWidth: true
                Layout.fillHeight: true
                blueprint: bpSlider.value
                onPicked: (id) => studio.select(id)

                Column {   // title card, top left
                    x: 18; y: 14
                    spacing: 2
                    Label { text: studio.title; font.pixelSize: 20; font.bold: true; color: bpSlider.value > 0.5 ? theme.holo : theme.text }
                    Label { text: studio.summary; width: 520; wrapMode: Text.WordWrap; color: bpSlider.value > 0.5 ? "#9fd8f0" : theme.dim }
                }
                Label {
                    anchors.right: parent.right; anchors.bottom: parent.bottom; anchors.margins: 12
                    text: "drag orbit · right-drag pan · wheel zoom · click select"
                    color: bpSlider.value > 0.5 ? "#6fb8d8" : theme.dim
                    font.pixelSize: 11
                }
            }
            Pane {
                Layout.fillWidth: true
                padding: 10
                background: Rectangle { color: theme.panel; Rectangle { width: parent.width; height: 1; color: theme.line } }
                ColumnLayout {
                    anchors.fill: parent
                    spacing: 6
                    RowLayout {
                        spacing: 8
                        ComboBox {
                            id: mode
                            model: ["Dream", "Edit"]
                            Layout.preferredWidth: 100
                        }
                        TextField {
                            id: prompt
                            Layout.fillWidth: true
                            placeholderText: mode.currentIndex === 0
                                ? "Dream it: \"a jet engine with reverse thrusters, non-conventional style\""
                                : "Change it: \"make the reverser doors longer and add a second intake ring\""
                            enabled: studio.busy === ""
                            onAccepted: go()
                            function go() {
                                if (!text.trim()) return
                                if (mode.currentIndex === 0) studio.dream(text); else studio.edit(text)
                            }
                        }
                        ComboBox {
                            id: engine
                            model: studio.engines
                            Layout.preferredWidth: 110
                            onActivated: studio.setEngine(currentText)
                        }
                        Button {
                            text: studio.busy !== "" ? "Working…" : (mode.currentIndex === 0 ? "Replicate" : "Apply")
                            enabled: studio.busy === ""
                            highlighted: true
                            onClicked: prompt.go()
                        }
                    }
                    RowLayout {
                        BusyIndicator { running: studio.busy !== ""; visible: running; Layout.preferredWidth: 22; Layout.preferredHeight: 22 }
                        Label {
                            Layout.fillWidth: true
                            text: (studio.busy !== "" ? studio.busy + " · " : "") + studio.lastLog
                            color: theme.dim
                            font.family: theme.mono
                            font.pixelSize: 11
                            elide: Text.ElideRight
                        }
                    }
                }
            }
        }

        // ---------- right dock: properties + console ----------
        Pane {
            SplitView.preferredWidth: 360
            SplitView.minimumWidth: 240
            background: Rectangle { color: theme.panel }
            padding: 0
            ColumnLayout {
                anchors.fill: parent
                spacing: 0
                DockHeader { text: studio.selected ? "Properties · " + studio.selected : "Properties" }
                ScrollView {
                    Layout.fillWidth: true
                    Layout.preferredHeight: parent.height * 0.55
                    TextArea {
                        id: opEdit
                        text: studio.selectedJson
                        font.family: theme.mono
                        font.pixelSize: 11
                        wrapMode: TextEdit.NoWrap
                        placeholderText: "Select a part or a build step"
                        selectByMouse: true
                    }
                }
                RowLayout {
                    Layout.margins: 6
                    Button { text: "Apply"; enabled: studio.selected !== ""; onClicked: studio.applyOpJson(opEdit.text) }
                    Button { text: "Revert"; enabled: studio.selected !== ""; onClicked: opEdit.text = studio.selectedJson }
                }
                DockHeader { text: "Console" }
                ScrollView {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    TextArea {
                        readOnly: true
                        text: studio.log
                        font.family: theme.mono
                        font.pixelSize: 10
                        color: theme.dim
                        wrapMode: TextEdit.Wrap
                        onTextChanged: cursorPosition = length
                    }
                }
            }
        }
    }

    component DockHeader: Rectangle {
        property alias text: lbl.text
        Layout.fillWidth: true
        height: 30
        color: "#e9ebee"
        Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: 1; color: theme.line }
        Label { id: lbl; anchors.verticalCenter: parent.verticalCenter; x: 10; font.bold: true; font.pixelSize: 11; font.letterSpacing: 1.5; color: theme.text }
    }
}
