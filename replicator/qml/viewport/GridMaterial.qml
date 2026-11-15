import QtQuick
import QtQuick3D

CustomMaterial {
    property color lineColor: "#8d9198"
    property color majorColor: "#5f646c"
    property real blueprint: 0.0
    property real fade: 6000
    property real span: 900
    shadingMode: CustomMaterial.Unshaded
    sourceBlend: CustomMaterial.SrcAlpha
    destinationBlend: CustomMaterial.OneMinusSrcAlpha
    cullMode: Material.NoCulling
    vertexShader: "../../shaders/grid.vert"
    fragmentShader: "../../shaders/grid.frag"
}
