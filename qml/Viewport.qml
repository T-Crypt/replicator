import QtQuick
import QtQuick3D
import QtQuick3D.Helpers

// The workshop floor. Parts sit on the grid (the root is lifted by studio.ground), the camera orbits the build.
Item {
    id: root
    property real blueprint: 0.0          // 0 = real, 1 = blueprint
    property real revealMs: 1400
    property alias view: view
    signal picked(string shapeId)
    // the bounding sphere fits the vertical field of view with a 15% margin
    readonly property real frameDistance: studio.radius * 1.15 / Math.sin(19 * Math.PI / 180)

    readonly property color realBg: "#c4c7cc"
    readonly property color bpBg: "#0a1a33"

    View3D {
        id: view
        anchors.fill: parent
        camera: cam

        environment: ExtendedSceneEnvironment {
            backgroundMode: SceneEnvironment.Color
            clearColor: Qt.tint(root.realBg, Qt.rgba(root.bpBg.r, root.bpBg.g, root.bpBg.b, root.blueprint))
            antialiasingMode: SceneEnvironment.MSAA
            antialiasingQuality: SceneEnvironment.High
            tonemapMode: SceneEnvironment.TonemapModeFilmic
            glowEnabled: true
            glowStrength: 1.1
            glowIntensity: 0.7
            glowBloom: 0.25
            glowHDRMinimumValue: 1.0
            exposure: 1.0
            lightProbe: Texture { textureData: studio.envMap; mappingMode: Texture.LightProbe }
            probeExposure: 0.9
            probeOrientation: Qt.vector3d(0, 30, 0)
        }

        Node {
            id: orbit
            position: Qt.vector3d(0, studio.centerY, 0)
            eulerRotation: Qt.vector3d(-22, 35, 0)
            PerspectiveCamera {
                id: cam
                z: root.frameDistance
                clipNear: 1
                clipFar: 200000
                fieldOfView: 38
            }
        }

        DirectionalLight {   // key / sun
            eulerRotation: Qt.vector3d(-50, -35, 0)
            brightness: 1.1
            castsShadow: true
            shadowMapQuality: Light.ShadowMapQualityHigh
            shadowFactor: 55
            csmNumSplits: 2
            shadowBias: 2
        }
        DirectionalLight { eulerRotation: Qt.vector3d(-20, 140, 0); brightness: 0.55; color: "#dfe8ff" }  // fill
        DirectionalLight { eulerRotation: Qt.vector3d(15, 200, 0); brightness: 0.8; color: "#ffffff" }    // rim
        PointLight { y: studio.radius * 1.5; brightness: 0.4; quadraticFade: 0; linearFade: 0 }

        Model {   // workshop floor
            source: "#Rectangle"
            eulerRotation.x: -90
            scale: Qt.vector3d(800, 800, 1)
            receivesShadows: true
            materials: GridMaterial {
                blueprint: root.blueprint
                fade: Math.max(studio.radius * 9, 3000)
                lineColor: Qt.tint("#8d9198", Qt.rgba(0.2, 0.55, 0.85, root.blueprint))
                majorColor: Qt.tint("#5f646c", Qt.rgba(0.3, 0.8, 1.0, root.blueprint))
            }
        }
        Model {   // shadow catcher just under the grid lines
            source: "#Rectangle"
            eulerRotation.x: -90
            y: -0.2
            scale: Qt.vector3d(800, 800, 1)
            receivesShadows: true
            castsShadows: false
            opacity: 1.0 - root.blueprint
            materials: PrincipledMaterial { baseColor: "#6d7178"; roughness: 1; metalness: 0; specularAmount: 0 }
        }

        Node {
            id: build
            y: studio.ground
            Repeater3D {
                model: studio.shapes
                delegate: Model {
                    id: part
                    required property var modelData
                    property string shapeId: modelData.shapeId
                    geometry: modelData
                    pickable: true
                    castsShadows: true
                    receivesShadows: true
                    property real reveal: modelData.fresh ? 0.0 : 1.0
                    materials: HoloMaterial {
                        baseColor: part.modelData.baseColor
                        emissiveColor: part.modelData.emissive
                        metal: part.modelData.metalness
                        rough: part.modelData.roughness
                        minY: part.modelData.minY + studio.ground
                        maxY: part.modelData.maxY + studio.ground
                        reveal: part.reveal
                        blueprint: root.blueprint
                        selected: studio.selected === part.shapeId ? 1.0 : 0.0
                    }
                    NumberAnimation on reveal {
                        running: part.modelData.fresh
                        from: 0; to: 1
                        duration: root.revealMs
                        easing.type: Easing.InOutCubic
                    }
                }
            }
        }
    }

    OrbitCameraController {
        anchors.fill: parent
        origin: orbit
        camera: cam
        panEnabled: true
    }

    TapHandler {
        onTapped: (ev) => {
            const r = view.pick(ev.position.x, ev.position.y)
            root.picked(r.objectHit ? r.objectHit.shapeId : "")
        }
    }

    function frame() {
        orbit.position = Qt.vector3d(0, studio.centerY, 0)
        orbit.eulerRotation = Qt.vector3d(-22, 35, 0)
        cam.position = Qt.vector3d(0, 0, root.frameDistance)
    }
}
