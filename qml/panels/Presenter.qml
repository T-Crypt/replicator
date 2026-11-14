import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Replicator.UI

// Present mode: plays the checked explanation, one chapter at a time. A fixed light palette (ink and
// dim on the white stage), not theme tokens. Left / Right move, Space pauses, Esc leaves to Reverse (those keys
// are window Shortcuts; Main.qml routes them here while presenting).
// A sentence is shown as the checker kept it: cited with its source numbers, measured, or concept.
Item {
    id: presenter
    anchors.fill: parent
    visible: window.present

    property var window
    property var viewport
    property int chapter: 0
    property bool playing: true
    property bool ended: false          // true when the timer reached the last chapter
    property bool switching: false      // inside studio.speak(): its own stop/start is not "speech ended"

    readonly property var doc: studio.explanation
    readonly property var chapters: doc.chapters || []
    readonly property var cur: chapters.length ? chapters[chapter] : ({})
    readonly property var sources: doc.sources || []

    readonly property color ink: "#14181f"
    readonly property color dim: "#5b6472"
    readonly property color amber: "#b45309"

    function go(i) {
        if (!chapters.length) return
        ended = false
        const c = Math.max(0, Math.min(i, chapters.length - 1))
        if (c === chapter) show(); else chapter = c          // onChapterChanged calls show()
    }
    function next() {
        if (!chapters.length) return
        if (chapter < chapters.length - 1) go(chapter + 1)
        else { playing = false; ended = true; studio.stopSpeaking() }
    }
    function prev() { if (chapter > 0) go(chapter - 1) }
    function togglePlay() {
        if (!chapters.length) return
        if (!playing && ended) { playing = true; go(0); return }
        playing = !playing
        if (!playing) studio.stopSpeaking(); else show()
    }
    // Entering Present mode, or a new explanation arriving while presenting: start from the first chapter.
    function start() {
        ended = false; playing = true
        if (!chapters.length) { studio.stopSpeaking(); window.isolate = ""; viewport.frameAll(true); return }
        go(0)
    }
    // Put the current chapter on stage: isolate and frame its component, read it aloud, arm the timer.
    function show() {
        if (!chapters.length || !visible) return
        window.isolate = cur.component || ""
        viewport.frameComponent(cur.component || "")
        advance.stop()
        if (playing && studio.services.speak) { switching = true; studio.speak(cur.text || ""); switching = false }
        if (playing && !studio.speaking) advance.start()
    }

    onChapterChanged: show()
    onDocChanged: if (visible) start()
    onVisibleChanged: if (!visible) { advance.stop(); studio.stopSpeaking() }

    Timer {   // advances when no voice is reading; a voice advances on speech end instead
        id: advance
        interval: Math.round((presenter.cur.seconds || 10) * 1000)
        repeat: false
        onTriggered: if (presenter.playing && presenter.visible) presenter.next()
    }
    Connections {
        target: studio
        function onVoiceChanged() {   // `speaking` notifies through voiceChanged
            if (presenter.switching || studio.speaking || !presenter.visible) return
            if (presenter.playing && presenter.chapters.length) presenter.next()
        }
    }

    // ------------------------------------------------- title and concept notice, top left
    Column {
        anchors.left: parent.left; anchors.top: parent.top
        anchors.leftMargin: 30; anchors.topMargin: 26
        spacing: 12
        Text {
            text: presenter.doc.subject || studio.title
            color: presenter.ink; font.family: Theme.sans; font.pixelSize: 30; font.weight: Font.DemiBold
        }
    }
    Rectangle {
        anchors.left: parent.left; anchors.top: parent.top
        anchors.leftMargin: 30; anchors.topMargin: 70
        visible: presenter.doc.concept === true
        width: Math.min(560, parent.width - 120); height: badgeCol.implicitHeight + 20; radius: 10
        color: Qt.rgba(presenter.amber.r, presenter.amber.g, presenter.amber.b, 0.08)
        border.color: Qt.rgba(presenter.amber.r, presenter.amber.g, presenter.amber.b, 0.5)
        Column {
            id: badgeCol
            x: 12; y: 10; width: parent.width - 24; spacing: 4
            Row { spacing: 6
                Icon { name: "alert"; size: 14; color: presenter.amber }
                Text { text: "CONCEPT"; color: presenter.amber; font.pixelSize: 11; font.weight: Font.Bold
                       font.letterSpacing: 1.5; font.family: Theme.sans
                       anchors.verticalCenter: parent.verticalCenter }
            }
            Text { text: presenter.doc.notice || ""; color: presenter.dim; width: parent.width
                   wrapMode: Text.WordWrap; font.pixelSize: 12; font.family: Theme.sans; lineHeight: 1.3 }
        }
    }

    // ------------------------------------------------- sources, right
    Column {
        anchors.right: parent.right; anchors.top: parent.top
        anchors.rightMargin: 30; anchors.topMargin: 26
        visible: presenter.chapters.length > 0 && presenter.sources.length > 0
        width: 300
        Text { text: "SOURCES  ·  " + presenter.sources.length
               color: presenter.dim; font.pixelSize: 10; font.weight: Font.DemiBold; font.letterSpacing: 1.5
               font.family: Theme.sans }
        Flickable {
            width: 300
            height: Math.min(contentHeight, presenter.height - 330)
            contentWidth: 300; contentHeight: srcCol.height
            clip: true
            boundsBehavior: Flickable.StopAtBounds
            Column {
                id: srcCol
                width: 300; spacing: 2
                Repeater {
                    model: presenter.sources
                    delegate: Rectangle {
                        required property var modelData
                        width: 300; height: 34; radius: 8
                        color: srcMa.containsMouse ? Qt.rgba(presenter.dim.r, presenter.dim.g, presenter.dim.b, 0.08) : "transparent"
                        Row {
                            id: srcRow
                            x: 10; y: 6; spacing: 8
                            Text { text: "[" + modelData.n + "]"; color: Theme.accent; font.pixelSize: 12
                                   font.weight: Font.Bold; font.family: Theme.mono }
                            Column {
                                id: srcCol2
                                anchors.verticalCenter: parent.verticalCenter
                                spacing: 1
                                Text { text: modelData.title; color: presenter.ink; font.pixelSize: 12
                                       font.family: Theme.sans; elide: Text.ElideRight
                                       width: Math.min(220, srcCol.width - 46) }
                                Text { text: modelData.domain; color: presenter.dim; font.pixelSize: 10
                                       font.family: Theme.sans; elide: Text.ElideRight
                                       width: Math.min(220, srcCol.width - 46) }
                            }
                        }
                        MouseArea {
                            id: srcMa
                            anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                            onClicked: Qt.openUrlExternally(modelData.url)
                        }
                    }
                }
            }
        }
    }

    // ------------------------------------------------- caption card, bottom centre
    Rectangle {
        id: card
        visible: presenter.chapters.length > 0
        anchors.horizontalCenter: parent.horizontalCenter
        y: parent.height - height - 60
        width: Math.min(940, parent.width - 40)
        // grows with the chapter's sentences up to a cap (then clips); the layout never sets this height
        readonly property real sentH: Math.min(sentCol.implicitHeight, Math.max(80, presenter.height * 0.32))
        height: 22 + 20 + 12 + sentH + 12 + 30 + 22
        radius: 16
        color: "#f2ffffff"
        border.color: "#d5dae1"
        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 22
            spacing: 12
            RowLayout {
                Layout.fillWidth: true
                spacing: 10
                Text { text: presenter.cur.title || ""; color: presenter.ink; font.pixelSize: 15
                       font.weight: Font.Bold; font.family: Theme.sans }
                Item { Layout.fillWidth: true }
                Text { text: (presenter.chapter + 1) + " / " + presenter.chapters.length
                       color: presenter.dim; font.pixelSize: 12; font.family: Theme.mono }
            }
            Item {
                Layout.fillWidth: true
                Layout.preferredHeight: card.sentH
                clip: true
                Column {
                    id: sentCol
                    width: parent.width; spacing: 8
                    Repeater {
                        model: presenter.cur.sentences || []
                        delegate: Column {
                            required property var modelData
                            width: sentCol.width
                            spacing: 5
                            Text {
                                width: parent.width; text: modelData.text
                                color: presenter.ink; font.pixelSize: 14; font.family: Theme.sans
                                wrapMode: Text.WordWrap; lineHeight: 1.35
                            }
                            Row {
                                spacing: 5
                                Repeater {
                                    model: modelData.kind === "cited" ? modelData.cite : []
                                    delegate: Rectangle {
                                        required property int modelData
                                        implicitWidth: t.implicitWidth + 12; implicitHeight: 18; radius: 9
                                        color: Qt.rgba(Theme.accent.r, Theme.accent.g, Theme.accent.b, 0.12)
                                        Text { id: t; anchors.centerIn: parent; text: "[" + modelData + "]"
                                               color: Theme.accent; font.pixelSize: 11; font.weight: Font.Bold
                                               font.family: Theme.mono }
                                    }
                                }
                                Rectangle {
                                    visible: modelData.kind === "measured"
                                    implicitWidth: 14 + 12; implicitHeight: 18; radius: 9
                                    color: Qt.rgba(presenter.dim.r, presenter.dim.g, presenter.dim.b, 0.12)
                                    Icon { anchors.centerIn: parent; name: "ruler"; size: 11; color: presenter.dim }
                                }
                                Rectangle {
                                    visible: modelData.kind === "concept"
                                    implicitWidth: t2.implicitWidth + 12; implicitHeight: 18; radius: 9
                                    color: Qt.rgba(presenter.amber.r, presenter.amber.g, presenter.amber.b, 0.12)
                                    Text { id: t2; anchors.centerIn: parent; text: "concept"
                                           color: presenter.amber; font.pixelSize: 11; font.weight: Font.DemiBold
                                           font.family: Theme.sans }
                                }
                            }
                        }
                    }
                }
            }
            RowLayout {
                Layout.fillWidth: true
                spacing: 14
                Row { spacing: 4; Layout.alignment: Qt.AlignVCenter
                    Repeater {
                        model: presenter.chapters.length
                        delegate: Rectangle {
                            required property int index
                            implicitWidth: 7; implicitHeight: 7; radius: 3.5
                            color: index === presenter.chapter ? presenter.ink : Qt.rgba(presenter.dim.r, presenter.dim.g, presenter.dim.b, 0.35)
                        }
                    }
                }
                Item { Layout.fillWidth: true }
                RowLayout {
                    spacing: 6
                    IconButton {
                        icon: "first"; tip: "Previous chapter  (Left)"
                        onHit: presenter.prev()
                    }
                    IconButton {
                        icon: presenter.playing ? "pause" : "play"; tip: "Play / pause  (Space)"
                        onHit: presenter.togglePlay()
                    }
                    IconButton {
                        icon: "last"; tip: "Next chapter  (Right)"
                        onHit: presenter.next()
                    }
                    IconButton {
                        icon: studio.services.speak ? "speaker" : "speakerOff"
                        tip: studio.services.speak ? "Voice on" : "Voice off"
                        onHit: {
                            studio.setService("speak", JSON.stringify(!studio.services.speak))
                            if (!studio.services.speak) studio.stopSpeaking(); else presenter.show()
                        }
                    }
                }
            }
        }
    }

    // ------------------------------------------------- empty state: no explanation yet
    Rectangle {
        visible: presenter.chapters.length === 0
        anchors.centerIn: parent
        width: Math.min(460, parent.width - 80); height: empCol.implicitHeight + 44; radius: 16
        color: "#f2ffffff"; border.color: "#d5dae1"
        ColumnLayout {
            id: empCol
            anchors.centerIn: parent
            spacing: 12
            Text {
                text: "How it works"
                color: presenter.ink; font.pixelSize: 18; font.weight: Font.DemiBold; font.family: Theme.sans
                Layout.alignment: Qt.AlignHCenter
            }
            Pill {
                primary: true
                icon: "book"; text: "Explain how it works"
                Layout.alignment: Qt.AlignHCenter
                onHit: studio.explain()
            }
            Text {
                text: !studio.services.research
                     ? "Web research is off, so only measurements can be shown. Turn it on in Preferences (Ctrl+,)."
                     : "The local model checks every sentence before it is shown."
                color: presenter.dim; font.pixelSize: 12; font.family: Theme.sans
                wrapMode: Text.WordWrap; horizontalAlignment: Text.AlignHCenter
                Layout.alignment: Qt.AlignHCenter
                Layout.preferredWidth: Math.min(400, presenter.width - 128)
            }
        }
    }
}
