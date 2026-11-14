import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Replicator.UI

// Attribute Manager: the selected step's parameters as real fields. Drag a number to scrub it.
Rectangle {
    id: am
    color: Theme.panel
    function commit(key, value) { studio.setParam(studio.selected, key, JSON.stringify(value)) }

    Column {
        anchors.centerIn: parent; visible: studio.selectedOpKind === "" && studio.selectedComponent === ""; spacing: 8
        Icon { name: "sliders"; size: 26; color: Theme.faint; anchors.horizontalCenter: parent.horizontalCenter }
        Text {
            text: "Nothing selected.\nClick a part in the viewport\nor a row in Objects."
            horizontalAlignment: Text.AlignHCenter; color: Theme.faint; font.pixelSize: Theme.fs; font.family: Theme.sans; lineHeight: 1.3
        }
    }

    Flickable {
        anchors.fill: parent
        contentHeight: col.implicitHeight + 20
        clip: true
        boundsBehavior: Flickable.StopAtBounds
        ScrollBar.vertical: ScrollBar {}
        visible: studio.selectedOpKind !== "" || studio.selectedComponent !== ""
        ColumnLayout {
            id: col
            x: Theme.pad; y: 10
            width: am.width - Theme.pad * 2
            spacing: 7
            RowLayout {
                spacing: 8
                Rectangle {
                    implicitWidth: kind.implicitWidth + 14; implicitHeight: 20; radius: 10
                    color: Theme.accentSoft
                    Text { id: kind; anchors.centerIn: parent
                           text: studio.selectedOpKind ? studio.selectedOpKind.toUpperCase() : "COMPONENT"
                           color: Theme.accentHi; font.pixelSize: Theme.fsTiny; font.family: Theme.sans; font.weight: Font.Bold; font.letterSpacing: 1.2 }
                }
                Text { text: studio.selectedOpKind ? studio.selected : studio.selectedComponent
                       color: Theme.text; font.pixelSize: Theme.fs; font.family: Theme.mono; elide: Text.ElideRight; Layout.fillWidth: true }
            }
            Text {
                visible: studio.selectedOpKind === ""
                text: "A component groups parts. Pick one of its parts to edit parameters, or use the Materials tab to paint the whole component."
                color: Theme.dim; font.pixelSize: Theme.fsSmall; font.family: Theme.sans; wrapMode: Text.WordWrap; Layout.fillWidth: true
            }
            Repeater {
                model: studio.selectedParams
                delegate: ColumnLayout {
                    id: rowc
                    required property var modelData
                    required property int index
                    Layout.fillWidth: true
                    spacing: 4
                    RowLayout {
                        visible: rowc.modelData.group === "Coordinates" && rowc.modelData.key === "translate"
                        Layout.topMargin: 8; spacing: 8
                        Text { text: "COORDINATES"; color: Theme.faint; font.pixelSize: Theme.fsTiny; font.family: Theme.sans
                               font.weight: Font.DemiBold; font.letterSpacing: Theme.caps }
                        Rectangle { Layout.fillWidth: true; height: 1; color: Theme.lineSoft }
                    }
                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 6
                        Text {
                            text: rowc.modelData.key.replace(/_/g, " ")
                            color: Theme.dim; font.pixelSize: Theme.fsSmall; font.family: Theme.sans
                            Layout.preferredWidth: 84; elide: Text.ElideRight
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
                text: "Drag a number to scrub (Shift fine, Ctrl coarse). Click to type. Edits rebuild at once; Undo walks back."
                color: Theme.faint; font.pixelSize: Theme.fsTiny; font.family: Theme.sans; wrapMode: Text.WordWrap; Layout.fillWidth: true
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
        RCombo {
            property var row: parent ? parent.row : ({})
            implicitHeight: Theme.ctl - 2
            model: row.options
            currentIndex: Math.max(0, row.options.indexOf(row.value))
            displayText: currentText === "" ? "inherit" : currentText
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
            implicitHeight: Theme.ctl - 2; text: row.value; font.pixelSize: Theme.fsSmall; font.family: Theme.sans; color: Theme.text
            leftPadding: 8; selectionColor: Theme.accent; selectedTextColor: Theme.onAccent
            background: Rectangle { color: Theme.field; radius: Theme.r1; border.color: parent.activeFocus ? Theme.accent : Theme.line }
            onEditingFinished: if (text !== row.value) am.commit(row.key, text)
        }
    }
    Component {
        id: jsonC
        TextArea {
            property var row: parent ? parent.row : ({})
            text: row.value; wrapMode: TextEdit.WrapAnywhere; font.family: Theme.mono; font.pixelSize: Theme.fsTiny
            color: Theme.text; implicitHeight: Math.min(110, contentHeight + 12)
            selectionColor: Theme.accent; selectedTextColor: Theme.onAccent
            background: Rectangle { color: Theme.field; radius: Theme.r1; border.color: parent.activeFocus ? Theme.accent : Theme.line }
            onEditingFinished: { try { am.commit(row.key, JSON.parse(text)) } catch (e) { } }
        }
    }
}
