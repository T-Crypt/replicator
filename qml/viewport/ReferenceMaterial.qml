import QtQuick
import QtQuick3D

// A reference image standing in the scene. The views are drawn on white, so the white is almost keyed out: the
// figure shows on a sheet of frosted glass, and the plane never hides the build or the floor behind it.
CustomMaterial {
    property TextureInput tex: TextureInput { texture: Texture {} }
    property real strength: 0.92
    property real paper: 0.09
    shadingMode: CustomMaterial.Unshaded
    sourceBlend: CustomMaterial.SrcAlpha
    destinationBlend: CustomMaterial.OneMinusSrcAlpha
    cullMode: Material.BackFaceCulling      // a sheet shows only from the model's side, so it never covers the build
    depthDrawMode: Material.NeverDepthDraw
    vertexShader: "../../shaders/reference.vert"
    fragmentShader: "../../shaders/reference.frag"
}
