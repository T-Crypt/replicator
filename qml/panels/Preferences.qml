import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Replicator.UI

// Preferences (Ctrl+,): theme, accent, density and motion, plus the workspace toggles. Every change applies at
// once and is saved; there is no OK button.
Popup {
    id: pf
    property var workspace          // the main window (layout toggles live there)

    parent: Overlay.overlay
    x: Math.round((parent.width - width) / 2)
    y: Math.round((parent.height - height) / 2)
    width: 640
    padding: 22
    modal: true
    focus: true
    closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
    Overlay.modal: Rectangle { color: Theme.scrim }
    background: Rectangle { radius: 16; color: Theme.raised; border.color: Theme.glassLine }
    enter: Transition {
        NumberAnimation { property: "opacity"; from: 0; to: 1; duration: Theme.fast }
        NumberAnimation { property: "scale"; from: 0.97; to: 1; duration: Theme.med; easing.type: Easing.OutCubic }
    }

    component Label: Text {
        color: Theme.dim; font.pixelSize: Theme.fsTiny; font.family: Theme.sans; font.weight: Font.DemiBold; font.letterSpacing: Theme.caps
    }
    component Toggle: Rectangle {
        id: tg
        property string text
        property bool on: false
        signal flip()
        implicitWidth: tgRow.implicitWidth + 24; implicitHeight: Theme.ctl + 4; radius: height / 2
        color: on ? Theme.accentSoft : tgMa.containsMouse ? Theme.hover : "transparent"
        border.color: on ? Theme.accentLine : Theme.line
        Row {
            id: tgRow
            anchors.centerIn: parent; spacing: 6
            Icon { name: tg.on ? "check" : "close"; size: 12; color: tg.on ? Theme.accentHi : Theme.faint; anchors.verticalCenter: parent.verticalCenter }
            Text { text: tg.text; color: tg.on ? Theme.text : Theme.dim; font.pixelSize: Theme.fs; font.family: Theme.sans; anchors.verticalCenter: parent.verticalCenter }
        }
        MouseArea { id: tgMa; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: tg.flip() }
    }

    // one service setting: a label and a field saved when editing ends (Enter or focus leaves)
    component ServiceField: RowLayout {
        id: sf
        property string key
        property string label
        property string hint
        spacing: 10
        Text { text: sf.label; color: Theme.dim; font.pixelSize: Theme.fs; font.family: Theme.sans; Layout.preferredWidth: 150 }
        TextField {
            Layout.fillWidth: true
            implicitHeight: Theme.ctl + 2
            text: studio.services[sf.key] || ""
            placeholderText: sf.hint
            placeholderTextColor: Theme.faint
            color: Theme.text; font.pixelSize: Theme.fsSmall; font.family: Theme.mono
            selectByMouse: true
            background: Rectangle { radius: Theme.r2; color: Theme.field; border.color: parent.activeFocus ? Theme.accentLine : Theme.line }
            onEditingFinished: if (text.trim() !== (studio.services[sf.key] || "")) studio.setService(sf.key, JSON.stringify(text.trim()))
        }
    }

    contentItem: ColumnLayout {
        spacing: 12
        RowLayout {
            Layout.fillWidth: true
            Icon { name: "sliders"; size: 18; color: Theme.accentHi }
            Text { text: "Preferences"; color: Theme.text; font.pixelSize: 18; font.family: Theme.sans; font.weight: Font.DemiBold; Layout.leftMargin: 4 }
            Item { Layout.fillWidth: true }
            IconButton { icon: "close"; tip: "Close"; keys: "Esc"; onHit: pf.close() }
        }

        Label { text: "THEME"; Layout.topMargin: 4 }
        RowLayout {
            Layout.fillWidth: true
            spacing: 10
            Repeater {
                model: Object.keys(Theme.themes)
                delegate: Rectangle {
                    id: tc
                    required property string modelData
                    readonly property var th: Theme.themes[modelData]
                    readonly property bool sel: Theme.themeName === modelData
                    Layout.fillWidth: true
                    implicitHeight: 116; radius: Theme.r3
                    color: th.bg
                    border.width: sel ? 2 : 1
                    border.color: sel ? Theme.accent : tcMa.containsMouse ? Theme.accentLine : Theme.line
                    // a miniature of the workspace in this theme
                    Rectangle { x: 8; y: 8; width: parent.width - 16; height: 10; radius: 3; color: tc.th.header }
                    Rectangle { x: 8; y: 21; width: 9; height: 46; radius: 3; color: tc.th.header }
                    Rectangle {
                        x: 20; y: 21; width: parent.width - 28 - 40; height: 46; radius: 3
                        gradient: Gradient { GradientStop { position: 0; color: tc.th.viewTop } GradientStop { position: 1; color: tc.th.viewBottom } }
                        Rectangle { anchors.centerIn: parent; width: 22; height: 22; radius: 5; color: Theme.accent; opacity: 0.9 }
                    }
                    Rectangle { x: parent.width - 45; y: 21; width: 37; height: 46; radius: 3; color: tc.th.panel
                        Column { x: 4; y: 5; spacing: 4
                            Repeater { model: 4; Rectangle { width: 29 - index * 4; height: 3; radius: 1.5; color: index === 1 ? Theme.accent : tc.th.dim; opacity: 0.8 } } } }
                    Text { x: 10; y: 76; text: tc.th.label; color: tc.th.text; font.pixelSize: Theme.fs; font.family: Theme.sans; font.weight: Font.DemiBold }
                    Text { x: 10; y: 93; width: parent.width - 20; text: tc.th.note; color: tc.th.dim; font.pixelSize: 9; font.family: Theme.sans; elide: Text.ElideRight }
                    MouseArea { id: tcMa; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: Theme.themeName = tc.modelData }
                }
            }
        }

        Label { text: "ACCENT"; Layout.topMargin: 6 }
        RowLayout {
            spacing: 8
            Repeater {
                model: Object.keys(Theme.accents)
                delegate: Rectangle {
                    id: ac
                    required property string modelData
                    readonly property bool sel: Theme.accentName === modelData
                    implicitWidth: acRow.implicitWidth + 22; implicitHeight: Theme.ctl + 4; radius: height / 2
                    color: sel ? Theme.accentSoft : acMa.containsMouse ? Theme.hover : "transparent"
                    border.color: sel ? Theme.accentLine : Theme.line
                    Row {
                        id: acRow
                        anchors.centerIn: parent; spacing: 7
                        Rectangle { width: 12; height: 12; radius: 6; color: Theme.accents[ac.modelData].base; anchors.verticalCenter: parent.verticalCenter }
                        Text { text: Theme.accents[ac.modelData].label; color: ac.sel ? Theme.text : Theme.dim
                               font.pixelSize: Theme.fs; font.family: Theme.sans; anchors.verticalCenter: parent.verticalCenter }
                    }
                    MouseArea { id: acMa; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: Theme.accentName = ac.modelData }
                }
            }
        }

        RowLayout {
            Layout.topMargin: 6
            spacing: 28
            ColumnLayout {
                spacing: 8
                Label { text: "DENSITY" }
                Segmented {
                    segWidth: 84
                    current: Theme.density
                    model: [ { key: "compact", label: "Compact" }, { key: "cozy", label: "Cozy" }, { key: "roomy", label: "Roomy" } ]
                    onPick: (k) => Theme.density = k
                }
            }
            ColumnLayout {
                spacing: 8
                Label { text: "MOTION" }
                Toggle { text: "Animate the interface"; on: Theme.motion; onFlip: Theme.motion = !Theme.motion }
            }
        }

        Label { text: "WORKSPACE"; Layout.topMargin: 6 }
        Flow {
            Layout.fillWidth: true
            spacing: 8
            Toggle { text: "Tool rail"; on: pf.workspace.showLeft; onFlip: pf.workspace.showLeft = !pf.workspace.showLeft }
            Toggle { text: "Manager dock"; on: pf.workspace.showRight; onFlip: pf.workspace.showRight = !pf.workspace.showRight }
            Toggle { text: "Timeline"; on: pf.workspace.showTimeline; onFlip: pf.workspace.showTimeline = !pf.workspace.showTimeline }
            Toggle { text: "Floor grid"; on: pf.workspace.showGrid; onFlip: pf.workspace.showGrid = !pf.workspace.showGrid }
            Toggle { text: "Reference images"; on: pf.workspace.showReference; onFlip: pf.workspace.showReference = !pf.workspace.showReference }
        }
        Label { text: "RESEARCH AND VOICE"; Layout.topMargin: 6 }
        Flow {
            Layout.fillWidth: true
            spacing: 8
            Toggle { text: "Web research for Explain and specify"; on: studio.services.research === true; onFlip: studio.setService("research", JSON.stringify(!on)) }
            Toggle { text: "Read explanations aloud"; on: studio.services.speak === true; onFlip: studio.setService("speak", JSON.stringify(!on)) }
        }
        ServiceField { Layout.fillWidth: true; key: "search_url"; label: "SearXNG"; hint: "empty = Wikipedia only  ·  http://host:8888 or a {query} template" }
        ServiceField { Layout.fillWidth: true; key: "tts_url"; label: "Speech server"; hint: "empty = espeak-ng  ·  Kokoro: http://127.0.0.1:8880" }
        ServiceField { Layout.fillWidth: true; key: "tts_cmd"; label: "or a speech command"; hint: "…/tts.py {text} -o {wav} --voice {voice}  (CPU)" }
        ServiceField { Layout.fillWidth: true; key: "tts_voice"; label: "Voice"; hint: "af_heart" }
        ServiceField { Layout.fillWidth: true; key: "stt_url"; label: "Transcription server"; hint: "OpenAI-compatible, e.g. http://127.0.0.1:8890" }
        ServiceField { Layout.fillWidth: true; key: "stt_cmd"; label: "or a command"; hint: "whisper-cli -m model.bin -f {wav} -nt" }
        Text {
            Layout.fillWidth: true
            readonly property var st: studio.services.status || {}
            text: "Speech: " + (st.tts || "none") + "   ·   Dictation: " + (st.stt || "not set up")
                  + (st.record === false ? "   ·   no microphone recorder" : "")
            color: Theme.dim; font.pixelSize: Theme.fsTiny; font.family: Theme.sans; wrapMode: Text.WordWrap
        }
        Text {
            Layout.fillWidth: true
            text: "Research sends only search words, never your build. Voice runs on the CPU. Saved in services.json (mode 600) in the Replicator config folder."
            color: Theme.faint; font.pixelSize: Theme.fsTiny; font.family: Theme.sans; wrapMode: Text.WordWrap
        }
        Text {
            Layout.fillWidth: true; Layout.topMargin: 4
            text: "Saved in Replicator.conf in the Replicator config folder. The viewport draws on: " + studio.drawsOn + " (REPLICATOR_GPU=auto, igpu or any)."
            color: Theme.faint; font.pixelSize: Theme.fsTiny; font.family: Theme.sans; wrapMode: Text.WordWrap
        }
    }
}
