import QtQuick
import QtQuick3D

// Feature lines (creases and outlines), unshaded; reveal follows the part's scan plane.
CustomMaterial {
    property color lineColor: "#101114"
    property real reveal: 1.0
    property real minY: 0
    property real maxY: 100
    property real strength: 1.0
    shadingMode: CustomMaterial.Unshaded
    sourceBlend: CustomMaterial.SrcAlpha
    destinationBlend: CustomMaterial.OneMinusSrcAlpha
    vertexShader: "../../shaders/edge.vert"
    fragmentShader: "../../shaders/edge.frag"
}
