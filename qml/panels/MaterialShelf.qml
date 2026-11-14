import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Replicator.UI

// The material shelf: the materials this build already uses, then the library by family. Click a ball to paint
// the selected part (or every part of the selected component). The edit is one undo step.
Rectangle {
    id: ms
    color: Theme.panel
    readonly property bool canPaint: studio.selected !== ""
    readonly property var groups: {
        const out = []
        const mine = studio.programMaterials
        if (mine.length) out.push({ name: "In this build", rows: mine })
        const by = {}
        for (const m of studio.materialLibrary) { (by[m.group] = by[m.group] || []).push(m) }
        for (const g of ["Metal", "Polymer", "Paint", "Glow"]) if (by[g]) out.push({ name: g, rows: by[g] })
        return out
    }

    Flickable {
        anchors.fill: parent
        contentHeight: col.implicitHeight + 20
        clip: true
        boundsBehavior: Flickable.StopAtBounds
        ScrollBar.vertical: ScrollBar {}
        ColumnLayout {
            id: col
            x: Theme.pad; y: 10
            width: ms.width - Theme.pad * 2
            spacing: 8
            Rectangle {
                Layout.fillWidth: true; implicitHeight: 30; radius: Theme.r2
                color: ms.canPaint ? Theme.accentSoft : Theme.panel2
                Row {
                    x: 10; anchors.verticalCenter: parent.verticalCenter; spacing: 7
                    Icon { name: ms.canPaint ? "material" : "cursor"; size: 14; color: ms.canPaint ? Theme.accentHi : Theme.faint
                           anchors.verticalCenter: parent.verticalCenter }
                    Text { anchors.verticalCenter: parent.verticalCenter
                           text: ms.canPaint ? "Painting  " + studio.selected + (studio.selectedMaterial ? "   ·   now " + studio.selectedMaterial.replace(/_/g, " ") : "")
                                             : "Select a part or a component, then pick a material"
                           color: ms.canPaint ? Theme.text : Theme.dim; font.pixelSize: Theme.fsSmall; font.family: Theme.sans }
                }
            }
            Repeater {
                model: ms.groups
                delegate: ColumnLayout {
                    id: grp
                    required property var modelData
                    Layout.fillWidth: true
                    spacing: 6
                    Text { text: grp.modelData.name.toUpperCase(); color: Theme.faint; Layout.topMargin: 6
                           font.pixelSize: Theme.fsTiny; font.family: Theme.sans; font.weight: Font.DemiBold; font.letterSpacing: Theme.caps }
                    Flow {
                        Layout.fillWidth: true
                        spacing: 4
                        Repeater {
                            model: grp.modelData.rows
                            delegate: Rectangle {
                                id: cell
                                required property var modelData
                                readonly property bool cur: studio.selectedMaterial === modelData.id && ms.canPaint
                                width: 66; height: 68; radius: Theme.r2
                                color: cell.cur ? Theme.accentSoft : cMa.containsMouse ? Theme.hover : "transparent"
                                border.width: cell.cur ? 1 : 0; border.color: Theme.accentLine
                                opacity: ms.canPaint ? 1 : 0.55
                                Swatch {
                                    anchors.horizontalCenter: parent.horizontalCenter; y: 6; size: 36
                                    base: cell.modelData.color; metal: cell.modelData.metalness; rough: cell.modelData.roughness
                                    glow: cell.modelData.emissive
                                }
                                Text {
                                    anchors.horizontalCenter: parent.horizontalCenter; y: 47; width: parent.width - 6
                                    text: cell.modelData.label; color: cell.cur ? Theme.text : Theme.dim; elide: Text.ElideRight
                                    horizontalAlignment: Text.AlignHCenter; font.pixelSize: 9; font.family: Theme.sans
                                }
                                MouseArea { id: cMa; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                                            onClicked: if (ms.canPaint) studio.applyMaterial(cell.modelData.id) }
                                ToolTip.visible: cMa.containsMouse; ToolTip.delay: 500
                                ToolTip.text: cell.modelData.label + "   metal " + cell.modelData.metalness.toFixed(2) + "  rough " + cell.modelData.roughness.toFixed(2)
                            }
                        }
                    }
                }
            }
        }
    }
}
