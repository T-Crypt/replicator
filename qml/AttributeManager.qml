import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// Attribute Manager: the selected step's parameters as real fields. Drag a number to scrub it.
Rectangle {
    id: am
    color: Theme.panel
    function commit(key, value) { studio.setParam(studio.selected, key, JSON.stringify(value)) }

    Flickable {
        anchors.fill: parent
        contentHeight: col.implicitHeight + 16
        clip: true
        boundsBehavior: Flickable.StopAtBounds
        ScrollBar.vertical: ScrollBar {}
        ColumnLayout {
            id: col
            x: 10; y: 8
            width: am.width - 20
            spacing: 6
            Text {
                text: studio.selectedOpKind ? studio.selectedOpKind.toUpperCase() + "  ·  " + studio.selected
                      : studio.selectedComponent ? "Component  ·  " + studio.selectedComponent : "Nothing selected"
                color: studio.selectedOpKind ? Theme.holo : Theme.faint
                font.pixelSize: Theme.fsSmall; font.bold: true; font.letterSpacing: 1.2
            }
            Repeater {
                model: studio.selectedParams
                delegate: ColumnLayout {
                    id: rowc
                    required property var modelData
                    required property int index
                    Layout.fillWidth: true
                    spacing: 3
                    Text {
                        visible: rowc.modelData.group === "Coordinates" && rowc.modelData.key === "translate"
                        text: "COORDINATES"; color: Theme.faint; font.pixelSize: 10; font.letterSpacing: 1.5
                        Layout.topMargin: 6
                    }
                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 6
                        Text {
                            text: rowc.modelData.key.replace(/_/g, " ")
                            color: Theme.dim; font.pixelSize: Theme.fsSmall
                            Layout.preferredWidth: 78; elide: Text.ElideRight
                        }
                        Loader {
                            Layout.fillWidth: true
                            sourceComponent: ({ number: numC, vec3: vecC, enum: enumC, bool: boolC, text: textC,
                                                json: jsonC })[rowc.modelData.kind]
                            property var row: rowc.modelData
                        }
                    }
                }
            }
            Text {
                visible: studio.selectedOpKind !== ""
                Layout.topMargin: 8
                text: "Drag a number to scrub (Shift fine, Ctrl coarse). Enter to type. Edits rebuild instantly; Undo walks back."
                color: Theme.faint; font.pixelSize: 10; wrapMode: Text.WordWrap; Layout.fillWidth: true
            }
        }
    }
    Component {
        id: numC
        NumField {
            property var row: parent ? parent.row : ({})
            value: row.value
            stepSize: Math.max(Math.abs(row.value) * 0.01, 0.1)
            decimals: Math.abs(row.value) >= 100 ? 1 : 2
            onCommitted: (v) => am.commit(row.key, row.key === "count" || row.key === "teeth" || row.key === "turns"
                                                     || row.key === "segments" || row.key === "levels" ? Math.round(v) : v)
        }
    }
    Component {
        id: vecC
        RowLayout {
            id: vecRoot
            property var row: parent ? parent.row : ({})
            spacing: 4
            Repeater {
                model: 3
                NumField {
                    required property int index
                    Layout.fillWidth: true
                    label: ["X", "Y", "Z"][index]
                    labelColor: [Theme.axisX, Theme.axisY, Theme.axisZ][index]
                    value: vecRoot.row.value[index]
                    stepSize: vecRoot.row.key === "rotate" ? 1 : vecRoot.row.key === "scale" ? 0.01 : Math.max(studio.radius * 0.002, 0.1)
                    decimals: vecRoot.row.key === "scale" ? 3 : 1
                    onCommitted: (v) => { const a = vecRoot.row.value.slice(); a[index] = v; am.commit(vecRoot.row.key, a) }
                }
            }
        }
    }
    Component {
        id: enumC
        ComboBox {
            property var row: parent ? parent.row : ({})
            implicitHeight: 24
            model: row.options
            currentIndex: Math.max(0, row.options.indexOf(row.value))
            onActivated: am.commit(row.key, row.options[currentIndex])
        }
    }
    Component {
        id: boolC
        Switch { property var row: parent ? parent.row : ({}); checked: row.value; onToggled: am.commit(row.key, checked) }
    }
    Component {
        id: textC
        TextField {
            property var row: parent ? parent.row : ({})
            implicitHeight: 24; text: row.value; font.pixelSize: Theme.fs; color: Theme.text
            background: Rectangle { color: Theme.field; radius: 3; border.color: parent.activeFocus ? Theme.accent : Theme.line }
            onEditingFinished: if (text !== row.value) am.commit(row.key, text)
        }
    }
    Component {
        id: jsonC
        TextArea {
            property var row: parent ? parent.row : ({})
            text: row.value; wrapMode: TextEdit.WrapAnywhere; font.family: Theme.mono; font.pixelSize: 10
            color: Theme.text; implicitHeight: Math.min(110, contentHeight + 12)
            background: Rectangle { color: Theme.field; radius: 3; border.color: parent.activeFocus ? Theme.accent : Theme.line }
            onEditingFinished: { try { am.commit(row.key, JSON.parse(text)) } catch (e) { } }
        }
    }
}
