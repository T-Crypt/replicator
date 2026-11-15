import QtQuick
import QtQuick3D

CustomMaterial {
    property color baseColor: "#b8bbc2"
    property color emissiveColor: "black"
    property color tint: "#33c6ff"
    property real tintAmount: 0.0
    property real metal: 0.0
    property real rough: 0.5
    property real reveal: 1.0
    property real minY: 0
    property real maxY: 100
    property real blueprint: 0.0
    property real selected: 0.0
    property real xray: 0.0
    property real alpha: 1.0          // glass and clear plastics: blended with SrcAlpha so reflections fade with it too
    sourceBlend: alpha < 0.999 ? CustomMaterial.SrcAlpha : CustomMaterial.NoBlend
    destinationBlend: alpha < 0.999 ? CustomMaterial.OneMinusSrcAlpha : CustomMaterial.NoBlend
    shadingMode: CustomMaterial.Shaded
    cullMode: Material.NoCulling
    fragmentShader: "../../shaders/holo.frag"
}
