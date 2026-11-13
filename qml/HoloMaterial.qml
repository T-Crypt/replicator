import QtQuick
import QtQuick3D

CustomMaterial {
    property color baseColor: "#b8bbc2"
    property color emissiveColor: "black"
    property real metal: 0.0
    property real rough: 0.5
    property real reveal: 1.0
    property real minY: 0
    property real maxY: 100
    property real blueprint: 0.0
    property real selected: 0.0
    shadingMode: CustomMaterial.Shaded
    cullMode: Material.NoCulling
    fragmentShader: "../shaders/holo.frag"
}
