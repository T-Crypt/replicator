import QtQuick
import QtQuick.Controls
import Replicator.UI

// The Commander (Ctrl+K): one search box over everything Replicator can do. It lists the action registry, the
// examples and recent builds, the themes and the material library, and whatever you typed can be sent straight
// to the model as a dream or an edit. Up/Down to move, Enter to run, Esc to close.
Popup {
    id: cmd
    property var actions: []
    signal openFile(string path)

    parent: Overlay.overlay
    // (a hidden window, as --shot uses, has a zero-size overlay at the window centre: centre on it then)
    x: Math.round((parent.width - width) / 2)
    y: parent.height > 0 ? Math.round(parent.height * 0.14) : -Math.round(height / 2)
    width: 680
    padding: 0
    modal: true
    focus: true
    closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
    Overlay.modal: Rectangle { color: Theme.scrim }
    background: Rectangle { radius: 16; color: Theme.raised; border.color: Theme.glassLine }
    enter: Transition {
        NumberAnimation { property: "opacity"; from: 0; to: 1; duration: Theme.fast }
        NumberAnimation { property: "scale"; from: 0.97; to: 1; duration: Theme.med; easing.type: Easing.OutCubic }
    }
    onOpened: { query.text = ""; list.currentIndex = 0; query.forceActiveFocus() }

    function ok(a) { return a.enabled === undefined || a.enabled() }
    function match(hay, words) { hay = hay.toLowerCase(); for (const w of words) if (hay.indexOf(w) < 0) return false; return true }
    readonly property var results: {
        const q = query.text.trim()
        const words = q.toLowerCase().split(/\s+/).filter(s => s.length)
        const out = []
        for (const a of actions)
            if (match(a.group + " " + a.title, words))
                out.push({ group: a.group, title: a.title, icon: a.icon || "", keys: a.keys || "", ok: ok(a), run: a.run })
        if (studio.selected !== "")
            for (const m of studio.materialLibrary)
                if (words.length && match("material " + m.group + " " + m.label, words))
                    out.push({ group: "Material", title: m.label, icon: "material", keys: "", ok: true, run: () => studio.applyMaterial(m.id) })
        for (const k in Theme.themes)
            if (match("theme " + Theme.themes[k].label, words))
                out.push({ group: "Theme", title: Theme.themes[k].label + "  ·  " + Theme.themes[k].note, icon: "sun", keys: "", ok: true, run: () => Theme.themeName = k })
        for (const k in Theme.accents)
            if (words.length && match("accent colour color " + Theme.accents[k].label, words))
                out.push({ group: "Accent", title: Theme.accents[k].label, icon: "dot", keys: "", ok: true, tint: Theme.accents[k].base, run: () => Theme.accentName = k })
        for (const f of studio.examples.concat(studio.recents))
            if (match("open " + f.kind + " " + f.name, words))
                out.push({ group: f.kind === "example" ? "Example" : "Recent", title: f.name, icon: "folder", keys: f.steps + " steps", ok: true, run: () => cmd.openFile(f.path) })
        if (q.length > 3) {
            out.push({ group: "Specify", title: "Specify it: “" + q + "”", icon: "sparkle", keys: studio.busy === "" ? "" : "busy", ok: studio.busy === "", run: () => studio.dream(q) })
            if (studio.stepCount > 0)
                out.push({ group: "Edit", title: "Change this build: “" + q + "”", icon: "pencil", keys: "", ok: studio.busy === "", run: () => studio.edit(q) })
        }
        return out
    }
    function runAt(i) {
        const r = results[i]
        if (!r || !r.ok) return
        cmd.close()
        r.run()
    }

    contentItem: Column {
        spacing: 0
        Item {
            width: parent.width; height: 54
            Icon { x: 18; anchors.verticalCenter: parent.verticalCenter; name: "search"; size: 18; color: Theme.dim }
            TextField {
                id: query
                anchors.fill: parent; anchors.leftMargin: 46; anchors.rightMargin: 60
                background: null
                color: Theme.text; font.pixelSize: 16; font.family: Theme.sans
                selectionColor: Theme.accent; selectedTextColor: Theme.onAccent
                placeholderText: "Search actions, builds, materials and themes, or describe something to build"
                placeholderTextColor: Theme.faint
                verticalAlignment: TextInput.AlignVCenter
                onTextChanged: list.currentIndex = 0
                Keys.onDownPressed: list.currentIndex = Math.min(list.count - 1, list.currentIndex + 1)
                Keys.onUpPressed: list.currentIndex = Math.max(0, list.currentIndex - 1)
                onAccepted: cmd.runAt(list.currentIndex)
            }
            Kbd { anchors.right: parent.right; anchors.rightMargin: 16; anchors.verticalCenter: parent.verticalCenter; keys: "Esc" }
        }
        Rectangle { width: parent.width; height: 1; color: Theme.line }
        ListView {
            id: list
            width: parent.width
            height: Math.min(contentHeight + 12, 420)
            topMargin: 6; bottomMargin: 6
            clip: true
            model: cmd.results
            boundsBehavior: Flickable.StopAtBounds
            highlightMoveDuration: 0
            ScrollBar.vertical: ScrollBar {}
            delegate: Item {
                id: row
                required property var modelData
                required property int index
                width: list.width; height: 36
                Rectangle {
                    anchors.fill: parent; anchors.leftMargin: 6; anchors.rightMargin: 6; radius: Theme.r2
                    color: list.currentIndex === row.index ? Theme.accentSoft : "transparent"
                }
                Icon { x: 18; anchors.verticalCenter: parent.verticalCenter; name: row.modelData.icon; size: 16
                       color: row.modelData.tint || (list.currentIndex === row.index ? Theme.accentHi : Theme.dim); opacity: row.modelData.ok ? 1 : 0.4 }
                Text { x: 46; width: parent.width - 240; anchors.verticalCenter: parent.verticalCenter; elide: Text.ElideRight
                       text: row.modelData.title; color: Theme.text; opacity: row.modelData.ok ? 1 : 0.4
                       font.pixelSize: Theme.fsLarge - 1; font.family: Theme.sans }
                Row {
                    anchors.right: parent.right; anchors.rightMargin: 18; anchors.verticalCenter: parent.verticalCenter; spacing: 10
                    Text { text: row.modelData.keys; visible: row.modelData.keys !== "" && row.modelData.keys.indexOf(" ") > 0
                           color: Theme.faint; font.pixelSize: Theme.fsTiny; font.family: Theme.mono; anchors.verticalCenter: parent.verticalCenter }
                    Kbd { keys: row.modelData.keys.indexOf(" ") > 0 ? "" : row.modelData.keys; anchors.verticalCenter: parent.verticalCenter }
                    Text { text: row.modelData.group.toUpperCase(); color: Theme.faint; width: 62; horizontalAlignment: Text.AlignRight
                           font.pixelSize: 9; font.family: Theme.sans; font.weight: Font.DemiBold; font.letterSpacing: 1.1
                           anchors.verticalCenter: parent.verticalCenter }
                }
                MouseArea { anchors.fill: parent; hoverEnabled: true; onEntered: list.currentIndex = row.index; onClicked: cmd.runAt(row.index) }
            }
        }
        Rectangle { width: parent.width; height: 1; color: Theme.line }
        Item {
            width: parent.width; height: 32
            Row {
                x: 16; anchors.verticalCenter: parent.verticalCenter; spacing: 14
                Row { spacing: 5; Kbd { keys: "↑" } Kbd { keys: "↓" } Text { text: "move"; color: Theme.faint; font.pixelSize: Theme.fsTiny; font.family: Theme.sans; anchors.verticalCenter: parent.verticalCenter } }
                Row { spacing: 5; Kbd { keys: "Enter" } Text { text: "run"; color: Theme.faint; font.pixelSize: Theme.fsTiny; font.family: Theme.sans; anchors.verticalCenter: parent.verticalCenter } }
            }
            Text { anchors.right: parent.right; anchors.rightMargin: 16; anchors.verticalCenter: parent.verticalCenter
                   text: cmd.results.length + " results"; color: Theme.faint; font.pixelSize: Theme.fsTiny; font.family: Theme.mono }
        }
    }
}
