import QtQuick
import QtQuick.Controls

// A themed combo box: flat field, chevron, a rounded popup list.
ComboBox {
    id: cb
    implicitHeight: Theme.ctl
    implicitWidth: 110
    font.pixelSize: Theme.fsSmall
    font.family: Theme.sans
    leftPadding: 9; rightPadding: 24
    background: Rectangle {
        radius: Theme.r1; color: Theme.field
        border.color: cb.popup.visible ? Theme.accent : cb.hovered ? Theme.accentLine : Theme.line
    }
    contentItem: Text {
        text: cb.displayText; color: Theme.text; font: cb.font
        verticalAlignment: Text.AlignVCenter; elide: Text.ElideRight
    }
    indicator: Icon {
        x: cb.width - width - 7; y: (cb.height - height) / 2
        name: "chevronDown"; size: 12; color: Theme.dim
    }
    delegate: ItemDelegate {
        id: del
        required property var modelData
        required property int index
        width: ListView.view ? ListView.view.width : cb.width
        height: Theme.ctl + 2
        contentItem: Text {
            text: cb.textRole ? del.modelData[cb.textRole] : del.modelData
            color: cb.currentIndex === del.index ? Theme.accentHi : Theme.text
            font: cb.font; verticalAlignment: Text.AlignVCenter; elide: Text.ElideRight
        }
        background: Rectangle { radius: Theme.r1; color: del.hovered || del.highlighted ? Theme.hover : "transparent" }
    }
    popup: Popup {
        y: cb.height + 3
        width: Math.max(cb.width, 120)
        padding: 4
        implicitHeight: Math.min(contentItem.implicitHeight + 8, 320)
        contentItem: ListView {
            clip: true
            implicitHeight: contentHeight
            model: cb.popup.visible ? cb.delegateModel : null
            currentIndex: cb.highlightedIndex
            ScrollBar.vertical: ScrollBar {}
        }
        background: Rectangle { radius: Theme.r2; color: Theme.raised; border.color: Theme.line }
    }
}
