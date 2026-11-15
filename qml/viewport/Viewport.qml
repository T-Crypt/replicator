import QtQuick
import QtQuick3D
import QtQuick3D.Helpers
import Replicator.UI

// The workshop viewport. A custom orbit camera (pivot + yaw/pitch/distance, damped), C4D and Blender bindings,
// zoom to cursor, adaptive clip planes, ortho views, a move gizmo with grid snapping, display modes,
// exploded views (Dissect) and a Showcase look.
Item {
    id: root
    focus: true

    // ---- state from the window
    property real blueprint: 0.0
    property real explode: 0.0               // 0 assembled .. 1 fully exploded
    property real explodeGoal: 0.0           // where explode is heading (framing uses it)
    property string displayMode: "shaded"     // shaded | lines | wire | xray
    property bool colorByComponent: false
    property string isolate: ""               // component id shown alone ("" = all)
    property var hidden: ({})                 // component id -> true
    property string tool: "select"            // select | move | measure
    property var measurePts: []               // measure tool: up to two picked surface points (scene units)
    onToolChanged: measurePts = []
    property bool showcase: false
    property bool present: false
    property bool turntable: false
    property bool gridOn: true
    property bool referenceOn: true
    property real revealMs: 1100
    property alias view: view
    signal picked(string shapeId)
    signal contextRequested(string shapeId, real x, real y)
    signal userInteracted()
    signal explodeNudge(real delta)

    // ---- camera state (current and target, eased every frame)
    property real yaw: 35;    property real tYaw: 35
    property real pitch: 24;  property real tPitch: 24
    property real dist: 900;  property real tDist: 900
    property vector3d pivot: Qt.vector3d(0, 150, 0)
    property vector3d tPivot: Qt.vector3d(0, 150, 0)
    property bool ortho: false
    property string viewName: "Perspective"
    readonly property real fov: 35
    readonly property real gridCell: Math.pow(10, Math.floor(Math.log(Math.max(dist, 1) / 14) / Math.LN10))   // as grid.frag
    property int tick: 0                      // bumps every frame so 2D overlays re-project
    property real idle: 0

    readonly property real minDist: Math.max(studio.radius * 0.03, 2)
    readonly property real maxDist: studio.radius * 60
    // Present: the object stands on the white stage, or levitates with a slow bob when its footprint is
    // too small to stand on (studio.restPose, measured from the geometry)
    property real bobClock: 0
    readonly property real lift: root.present && studio.restPose === "levitate"
                               ? studio.radius * 0.18 + Math.sin(bobClock * Math.PI / 2) * studio.radius * 0.012
                               : 0
    readonly property vector3d camDir: Qt.vector3d(Math.cos(pitch * Math.PI / 180) * Math.sin(yaw * Math.PI / 180),
                                                Math.sin(pitch * Math.PI / 180),
                                                Math.cos(pitch * Math.PI / 180) * Math.cos(yaw * Math.PI / 180))
    readonly property vector3d camRight: Qt.vector3d(Math.cos(yaw * Math.PI / 180), 0, -Math.sin(yaw * Math.PI / 180))
    readonly property vector3d camUp: camDir.crossProduct(camRight).normalized()

    readonly property alias parts: partsRep
    function frameAll(animate) {
        const c = studio.center
        tPivot = Qt.vector3d(c[0], c[1], c[2])
        // 1.18: room for the dream bar and the title over the view; with 1.0 a tall build touched both edges
        tDist = studio.radius * 1.18 * (1.0 + Math.max(explode, explodeGoal) * 1.1) / Math.sin(fov / 2 * Math.PI / 180)
        if (!animate) { pivot = tPivot; dist = tDist }
    }
    function heroAngle() { tYaw = nearestYaw(38); tPitch = 14; ortho = false; viewName = "Perspective" }
    function frameSelected() {
        const g = selectedGeo()
        if (!g) return frameAll(true)
        const o = g.explodeOffset
        tPivot = Qt.vector3d(g.center.x + o.x * explode, g.center.y + studio.ground + o.y * explode,
                             g.center.z + o.z * explode)
        tDist = Math.max(minDist * 2, studio.radius * 0.6 / Math.sin(fov / 2 * Math.PI / 180))
    }
    function frameComponent(cid) {
        for (let i = 0; i < studio.components.length; i++)
            if (studio.components[i].id === cid) {
                const c = studio.components[i]
                tPivot = Qt.vector3d(c.center[0], c.center[1], c.center[2])
                tDist = Math.max(minDist * 2, Math.max(c.size[0], c.size[1], c.size[2]) * 0.6 / Math.sin(fov / 2 * Math.PI / 180))
                return
            }
        frameAll(true)
    }
    function setView(name) {
        viewName = name
        const v = { "Perspective": [35, 24, false], "Top": [0, 89.9, true], "Front": [0, 0, true],
                    "Right": [90, 0, true], "Back": [180, 0, true], "Left": [-90, 0, true],
                    "Bottom": [0, -89.9, true] }[name]
        if (!v) return
        tYaw = nearestYaw(v[0]); tPitch = v[1]; ortho = v[2]
    }
    function nearestYaw(target) {             // turn the short way round
        const d = ((target - tYaw) % 360 + 540) % 360 - 180
        return tYaw + d
    }
    function selectedGeo() {
        for (let i = 0; i < studio.shapes.length; i++)
            if (studio.shapes[i].shapeId === studio.selected) return studio.shapes[i]
        return null
    }
    function project(v) { return view.mapFrom3DScene(v) }
    function cameraJson() {
        const p = cam.position
        return JSON.stringify({ position: [p.x, p.y, p.z], target: [pivot.x, pivot.y, pivot.z], fov: fov,
                                width: Math.round(view.width), height: Math.round(view.height),
                                radius: studio.radius, dof: showcase })
    }

    FrameAnimation {
        running: true
        onTriggered: {
            const k = 1 - Math.exp(-frameTime * 16)
            if (root.present) root.bobClock += frameTime
            if (root.turntable && root.idle > 1.5) root.tYaw -= frameTime * 9
            root.idle += frameTime
            root.yaw += (root.tYaw - root.yaw) * k
            root.pitch += (root.tPitch - root.pitch) * k
            root.dist += (root.tDist - root.dist) * k
            root.pivot = root.pivot.plus(root.tPivot.minus(root.pivot).times(k))
            cam.position = root.pivot.plus(root.camDir.times(root.dist))
            cam.lookAt(root.pivot)
            ocam.position = root.pivot.plus(root.camDir.times(Math.max(root.dist, studio.radius * 4)))
            ocam.lookAt(root.pivot)
            root.tick++
        }
    }

    View3D {
        id: view
        anchors.fill: parent
        camera: root.ortho ? ocam : cam

        environment: ExtendedSceneEnvironment {
            backgroundMode: SceneEnvironment.Transparent
            antialiasingMode: SceneEnvironment.MSAA
            antialiasingQuality: SceneEnvironment.High
            specularAAEnabled: true
            tonemapMode: SceneEnvironment.TonemapModeFilmic
            exposure: root.showcase ? 0.95 : 1.0
            lightProbe: Texture { textureData: studio.envMap; mappingMode: Texture.LightProbe }
            probeExposure: root.showcase ? 1.3 : 0.9
            probeOrientation: Qt.vector3d(0, 30, 0)
            glowEnabled: true
            glowStrength: 1.0
            glowIntensity: 0.7
            glowBloom: root.showcase ? 0.12 : 0.2     // 0.35 haloed every silhouette
            glowHDRMinimumValue: 1.0
            aoEnabled: root.showcase || root.present
            aoStrength: 50
            aoDistance: studio.radius * 0.06
            aoSoftness: 40
            depthOfFieldEnabled: root.showcase && !root.ortho
            depthOfFieldFocusDistance: root.dist
            depthOfFieldFocusRange: studio.radius * 1.6
            depthOfFieldBlurAmount: 1.6
            vignetteEnabled: root.showcase
            vignetteStrength: 12      // 0..15, LOWER is darker (Qt docs); 0.55 blacked out the stage
            vignetteRadius: 0.38
            vignetteColor: "#000000"
            ditheringEnabled: true
            fog: Fog {   // melts the Showcase stage into the backdrop (no hard horizon)
                enabled: root.showcase
                color: Theme.stageTop
                depthEnabled: true
                depthNear: root.dist + studio.radius * 1.4     // starts behind the object, never on it
                depthFar: root.dist + studio.radius * 1.4 + root.dist * 2.2
                depthCurve: 1.0
                density: 1.0
            }
        }

        PerspectiveCamera {
            id: cam
            fieldOfView: root.fov
            clipNear: Math.max(root.dist * 0.004, 0.05)
            clipFar: Math.max(root.dist * 60, studio.radius * 80)
        }
        OrthographicCamera {
            id: ocam
            readonly property real mag: view.height / (2 * root.dist * Math.tan(root.fov / 2 * Math.PI / 180))
            horizontalMagnification: mag
            verticalMagnification: mag
            clipNear: 1
            clipFar: studio.radius * 400
        }

        DirectionalLight {
            eulerRotation: Qt.vector3d(-52, -35, 0)
            brightness: root.showcase ? 2.3 : root.present ? 2.8 : 1.05
            castsShadow: true
            shadowMapQuality: Light.ShadowMapQualityVeryHigh
            shadowFactor: root.showcase ? 75 : root.present ? 100 : 50
            csmNumSplits: 2
            shadowBias: 2
            pcfFactor: root.present ? 6 : 3
        }
        DirectionalLight { eulerRotation: Qt.vector3d(-18, 140, 0); brightness: 0.45; color: "#dfe8ff" }
        DirectionalLight { eulerRotation: Qt.vector3d(12, 205, 0); brightness: root.showcase ? 1.6 : 0.7 }
        DirectionalLight {   // Showcase rim: a cool edge from behind lifts dark parts off the dark stage
            visible: root.showcase
            eulerRotation: Qt.vector3d(-28, root.yaw + 150, 0)
            brightness: 2.4; color: "#bcd8ff"
        }
        SpotLight {   // Showcase top light: a soft pool on the stage
            visible: root.showcase
            position: Qt.vector3d(studio.center[0], studio.radius * 4, studio.center[2])
            eulerRotation.x: -90
            brightness: 4.5
            coneAngle: 50; innerConeAngle: 20
            constantFade: 1; linearFade: 0; quadraticFade: 0
        }

        Model {   // workshop floor grid
            visible: !root.showcase && !root.present && root.gridOn
            source: "#Rectangle"
            eulerRotation.x: -90
            scale: Qt.vector3d(1200, 1200, 1)
            materials: GridMaterial {
                blueprint: root.blueprint
                fade: Math.max(root.dist * 6, studio.radius * 8)
                span: root.dist
                lineColor: Qt.tint(Theme.gridMinor, Qt.rgba(0.2, 0.55, 0.85, root.blueprint))
                majorColor: Qt.tint(Theme.gridMajor, Qt.rgba(0.3, 0.8, 1.0, root.blueprint))
            }
        }
        Model {   // shadow catcher in the workshop; a glossy stage in Showcase; a white matte stage in Present
            source: "#Rectangle"
            eulerRotation.x: -90
            y: -0.3
            scale: Qt.vector3d(root.present ? 50000 : 1200, root.present ? 50000 : 1200, 1)
            receivesShadows: true
            castsShadows: false
            opacity: root.showcase ? 1.0 : root.present ? 1.0 : (Theme.dark ? 0.5 : 0.4) * (1 - root.blueprint)
            materials: PrincipledMaterial {
                baseColor: root.showcase ? "#0d0e11" : root.present ? "#ffffff" : Theme.dark ? Theme.raised : "#8a929c"
                roughness: root.showcase ? 0.5 : 1
                metalness: 0
                specularAmount: root.showcase ? 0.12 : 0   // a glossy floor mirrored the probe into grey haze
            }
        }

        // ---- reference images (image to 3D keeps the views it was built from): one plane per view, standing on
        //      the floor behind the model on its own axis, the way a DCC places blueprints. Front looks down -Z.
        Node {
            id: refs
            visible: root.referenceOn && !root.showcase && !root.present && studio.reference.length > 0
            readonly property real h: studio.dimensions.length === 3 ? studio.dimensions[1] : 100
            readonly property real away: studio.radius * 1.15
            readonly property var place: ({ front: [Qt.vector3d(0, 0, -1), 0], back: [Qt.vector3d(0, 0, 1), 180],
                                            left: [Qt.vector3d(-1, 0, 0), 90], right: [Qt.vector3d(1, 0, 0), -90] })
            Repeater3D {
                model: studio.reference
                delegate: Model {
                    required property var modelData
                    readonly property var pl: refs.place[modelData.key] || refs.place.front
                    readonly property real side: refs.h / modelData.fill     // the figure in the picture is as tall as the model
                    source: "#Rectangle"
                    position: Qt.vector3d(studio.center[0] + pl[0].x * refs.away, refs.h / 2 + (modelData.cy - 0.5) * side,
                                          studio.center[2] + pl[0].z * refs.away)
                    eulerRotation.y: pl[1]
                    scale: Qt.vector3d(side / 100, side / 100, 1)
                    castsShadows: false; receivesShadows: false
                    pickable: false
                    materials: ReferenceMaterial {
                        tex: TextureInput { texture: Texture { source: "file://" + modelData.path } }
                    }
                }
            }
        }

        Node {
            id: build
            y: studio.ground + root.lift
            Repeater3D {
                id: partsRep
                model: studio.shapes
                delegate: Node {
                    id: part
                    required property var modelData
                    readonly property string shapeId: modelData.shapeId
                    readonly property bool isSel: studio.selected === shapeId || studio.selected === modelData.component
                    readonly property bool hiddenComp: root.hidden[modelData.component] === true
                    readonly property bool dimmed: root.isolate !== "" && root.isolate !== modelData.component
                    readonly property vector3d boom: modelData.explodeOffset.times(root.explode)
                    property real reveal: modelData.phase === 1 ? 0.0 : 1.0
                    position: boom.plus(studio.selected === shapeId && gizmo.dragging ? gizmo.offset : Qt.vector3d(0, 0, 0))
                    visible: !hiddenComp && reveal > 0.001
                    opacity: dimmed ? 0.07 : 1.0
                    Behavior on opacity { NumberAnimation { duration: 280 } }

                    Model {
                        property string shapeId: part.shapeId
                        geometry: part.modelData
                        pickable: !part.dimmed
                        castsShadows: true
                        receivesShadows: true
                        visible: root.displayMode !== "wire"
                        opacity: root.displayMode === "xray" ? 0.18 : 1.0
                        materials: HoloMaterial {
                            alpha: part.modelData.opacity
                            baseColor: part.modelData.baseColor
                            emissiveColor: part.modelData.emissive
                            tint: part.modelData.componentColor
                            tintAmount: root.colorByComponent ? 0.75 : 0.0
                            metal: part.modelData.metalness
                            rough: part.modelData.roughness
                            minY: part.modelData.minY + studio.ground + part.boom.y
                            maxY: part.modelData.maxY + studio.ground + part.boom.y
                            reveal: part.reveal
                            blueprint: root.blueprint
                            selected: part.isSel ? 1.0 : 0.0
                            xray: root.displayMode === "xray" ? 1.0 : 0.0
                        }
                    }
                    Model {
                        geometry: part.modelData.edges
                        visible: root.displayMode !== "shaded" || root.blueprint > 0.3 || part.isSel
                        materials: EdgeMaterial {
                            lineColor: part.isSel ? Theme.amber
                                     : root.blueprint > 0.3 ? Qt.rgba(0.55, 0.9, 1.0, 1)
                                     : (root.displayMode === "wire" || root.displayMode === "xray") ? part.modelData.componentColor
                                     : "#0c0d10"
                            strength: root.displayMode === "lines" ? 0.85 : 1.0
                            minY: part.modelData.minY + studio.ground + part.boom.y
                            maxY: part.modelData.maxY + studio.ground + part.boom.y
                            reveal: part.reveal
                        }
                    }
                    NumberAnimation on reveal {
                        running: part.modelData.phase === 1
                        from: 0; to: 1; duration: root.revealMs; easing.type: Easing.InOutCubic
                    }
                    NumberAnimation on reveal {
                        running: part.modelData.phase === 2
                        from: 1; to: 0; duration: root.revealMs * 0.8; easing.type: Easing.InOutCubic
                    }
                }
            }
        }

        // ---- move gizmo (X red, Y green, Z blue), always drawn on top
        Node {
            id: gizmo
            property bool dragging: false
            property int axis: -1
            property vector3d offset: Qt.vector3d(0, 0, 0)
            property var geo: root.tool === "move" && !root.showcase ? root.selectedGeo() : null
            visible: geo !== null
            readonly property real s: root.dist * 0.0011
            position: geo ? Qt.vector3d(geo.center.x, geo.center.y + studio.ground, geo.center.z)
                            .plus(geo.explodeOffset.times(root.explode)).plus(offset) : Qt.vector3d(0, 0, 0)
            Repeater3D {
                model: [ { a: 0, c: "#e5484d", r: Qt.vector3d(0, 0, -90) },
                         { a: 1, c: "#7bd88f", r: Qt.vector3d(0, 0, 0) },
                         { a: 2, c: "#3d8ee6", r: Qt.vector3d(90, 0, 0) } ]
                delegate: Node {
                    id: arrow
                    required property var modelData
                    eulerRotation: modelData.r
                    scale: Qt.vector3d(gizmo.s, gizmo.s, gizmo.s)
                    Model {
                        property int gizmoAxis: arrow.modelData.a
                        source: "#Cylinder"; pickable: true
                        y: 50; scale: Qt.vector3d(0.045, 1.0, 0.045)
                        depthBias: -100000
                        materials: DefaultMaterial {
                            lighting: DefaultMaterial.NoLighting
                            diffuseColor: gizmo.axis === arrow.modelData.a ? "#ffffff" : arrow.modelData.c
                        }
                    }
                    Model {
                        property int gizmoAxis: arrow.modelData.a
                        source: "#Cone"; pickable: true
                        y: 100; scale: Qt.vector3d(0.16, 0.3, 0.16)
                        depthBias: -100000
                        materials: DefaultMaterial {
                            lighting: DefaultMaterial.NoLighting
                            diffuseColor: gizmo.axis === arrow.modelData.a ? "#ffffff" : arrow.modelData.c
                        }
                    }
                }
            }
        }
    }

    // ---- input: C4D (Alt+L orbit, Alt+M pan, Alt+R dolly) and plain (L orbit, M or Shift+L pan, R dolly)
    MouseArea {
        id: mouse
        anchors.fill: parent
        acceptedButtons: Qt.AllButtons
        hoverEnabled: true
        property real lx: 0
        property real ly: 0
        property real px: 0
        property real py: 0
        property string act: ""
        property bool moved: false
        property vector2d gDir: Qt.vector2d(1, 0)
        property real gUnits: 1

        function pickGizmo(x, y) {
            if (!gizmo.visible) return -1
            const hits = view.pickAll(x, y)
            for (let i = 0; i < hits.length; i++) {
                const o = hits[i].objectHit
                if (o && o.gizmoAxis !== undefined) return o.gizmoAxis
            }
            return -1
        }
        onPressed: (m) => {
            root.forceActiveFocus()
            root.idle = 0
            root.userInteracted()
            lx = px = m.x; ly = py = m.y; moved = false
            const alt = m.modifiers & Qt.AltModifier
            const shift = m.modifiers & Qt.ShiftModifier
            if (m.button === Qt.LeftButton && !alt) {
                const ax = pickGizmo(m.x, m.y)
                if (ax >= 0) {
                    act = "gizmo"; gizmo.axis = ax; gizmo.offset = Qt.vector3d(0, 0, 0); gizmo.dragging = true
                    const c = gizmo.position
                    const L = studio.radius * 0.2
                    const a = ax === 0 ? Qt.vector3d(L, 0, 0) : ax === 1 ? Qt.vector3d(0, L, 0) : Qt.vector3d(0, 0, L)
                    const p0 = view.mapFrom3DScene(c), p1 = view.mapFrom3DScene(c.plus(a))
                    const d = Qt.vector2d(p1.x - p0.x, p1.y - p0.y)
                    gDir = d.normalized(); gUnits = L / Math.max(d.length(), 0.001)
                    return
                }
            }
            if (m.button === Qt.MiddleButton) act = "pan"
            else if (m.button === Qt.RightButton) act = "dolly"
            else if (shift) act = "pan"
            else if (m.modifiers & Qt.ControlModifier) act = "dolly"     // one-button mice and trackpads
            else act = "orbit"
        }
        onPositionChanged: (m) => {
            if (!pressed) return
            const dx = m.x - lx, dy = m.y - ly
            lx = m.x; ly = m.y
            if (Math.abs(m.x - px) + Math.abs(m.y - py) > 4) moved = true
            if (!moved) return
            root.idle = 0
            if (act === "orbit") {
                if (root.ortho) { root.ortho = false; root.viewName = "Perspective" }
                root.tYaw -= dx * 0.32
                root.tPitch = Math.max(-89, Math.min(89, root.tPitch + dy * 0.32))
            } else if (act === "pan") {
                const s = 2 * root.dist * Math.tan(root.fov / 2 * Math.PI / 180) / view.height
                root.tPivot = root.tPivot.minus(root.camRight.times(dx * s)).plus(root.camUp.times(dy * s))
            } else if (act === "dolly") {
                root.tDist = Math.max(root.minDist, Math.min(root.maxDist, root.tDist * Math.exp(dy * 0.006)))
            } else if (act === "gizmo") {
                const t = (m.x - px) * gDir.x + (m.y - py) * gDir.y
                let v = t * gUnits
                if (m.modifiers & Qt.ControlModifier) v = Math.round(v / 10) * 10      // 10 mm snap
                else if (!(m.modifiers & Qt.ShiftModifier)) v = Math.round(v)        // Shift = free
                gizmo.offset = gizmo.axis === 0 ? Qt.vector3d(v, 0, 0)
                             : gizmo.axis === 1 ? Qt.vector3d(0, v, 0) : Qt.vector3d(0, 0, v)
            }
        }
        onReleased: (m) => {
            if (act === "gizmo") {
                const o = gizmo.offset
                gizmo.dragging = false; gizmo.axis = -1
                gizmo.offset = Qt.vector3d(0, 0, 0)
                if (o.length() > 0.001) studio.nudge(studio.selected, o.x, o.y, o.z)
            } else if (!moved && m.button === Qt.LeftButton && root.tool === "measure") {
                const r = view.pick(m.x, m.y)
                if (r.objectHit) {
                    const pts = root.measurePts.length >= 2 ? [] : root.measurePts.slice()
                    pts.push(r.scenePosition)
                    root.measurePts = pts
                }
            } else if (!moved && (m.button === Qt.LeftButton || m.button === Qt.RightButton)) {
                const r = view.pick(m.x, m.y)
                const id = r.objectHit && r.objectHit.shapeId !== undefined ? r.objectHit.shapeId : ""
                if (m.button === Qt.LeftButton) root.picked(id)
                else { const p = mouse.mapToItem(null, m.x, m.y); root.contextRequested(id, p.x, p.y) }
            }
            act = ""
        }
        onDoubleClicked: (m) => {               // re-centre the orbit on the point under the cursor
            const r = view.pick(m.x, m.y)
            if (r.objectHit) root.tPivot = r.scenePosition
        }
        onWheel: (w) => {
            root.idle = 0
            root.userInteracted()
            if (w.modifiers & Qt.AltModifier) { root.explodeNudge(w.angleDelta.y / 1200); return }
            const f = Math.exp(-w.angleDelta.y / 120 * 0.14)
            const nd = Math.max(root.minDist, Math.min(root.maxDist, root.tDist * f))
            const r = view.pick(w.x, w.y)           // zoom toward what is under the cursor
            if (r.objectHit && nd < root.tDist)
                root.tPivot = root.tPivot.plus(r.scenePosition.minus(root.tPivot).times(1 - nd / root.tDist))
            root.tDist = nd
        }
    }

    PinchHandler {   // touchpad pinch: explode in Dissect, zoom elsewhere
        target: null
        onScaleChanged: (delta) => {
            if (studio.mode === "dissect") root.explodeNudge((delta - 1) * 1.5)
            else root.tDist = Math.max(root.minDist, Math.min(root.maxDist, root.tDist / delta))
        }
    }

    // ---- measure overlay: picked points, the line between them and the distance with its X, Y, Z parts
    Item {
        id: measure
        anchors.fill: parent
        visible: root.tool === "measure" && root.measurePts.length > 0
        readonly property var pts: {
            root.tick
            return root.measurePts.map(p => root.project(p))
        }
        readonly property var d: root.measurePts.length === 2 ? root.measurePts[1].minus(root.measurePts[0]) : null
        function fmt(v) { return Math.abs(v) >= 100 ? v.toFixed(1) : Math.abs(v) >= 1 ? v.toFixed(2) : v.toFixed(3) }
        Rectangle {
            visible: measure.pts.length === 2
            readonly property var a: measure.pts.length > 0 ? measure.pts[0] : Qt.point(0, 0)
            readonly property var b: measure.pts.length === 2 ? measure.pts[1] : a
            x: a.x; y: a.y - 1; height: 2; color: Theme.accent; antialiasing: true
            width: Math.hypot(b.x - a.x, b.y - a.y)
            transformOrigin: Item.Left
            rotation: Math.atan2(b.y - a.y, b.x - a.x) * 180 / Math.PI
        }
        Repeater {
            model: measure.pts
            delegate: Rectangle {
                required property var modelData
                x: modelData.x - 5; y: modelData.y - 5; width: 10; height: 10; radius: 5
                color: Theme.bg; border.color: Theme.accent; border.width: 2
            }
        }
        Rectangle {
            visible: measure.d !== null
            x: measure.pts.length === 2 ? (measure.pts[0].x + measure.pts[1].x) / 2 + 12 : 0
            y: measure.pts.length === 2 ? (measure.pts[0].y + measure.pts[1].y) / 2 - height - 8 : 0
            width: mLabel.implicitWidth + 16; height: mLabel.implicitHeight + 10; radius: 6
            color: Theme.panel; border.color: Theme.line
            Text {
                id: mLabel
                anchors.centerIn: parent
                color: Theme.text; font.family: Theme.mono; font.pixelSize: Theme.fsSmall
                text: !measure.d ? "" : measure.fmt(measure.d.length()) + " " + studio.units
                      + "\nΔX " + measure.fmt(measure.d.x) + "   ΔY " + measure.fmt(measure.d.y) + "   ΔZ " + measure.fmt(measure.d.z)
            }
        }
    }
    Text {
        anchors.horizontalCenter: parent.horizontalCenter; anchors.top: parent.top; anchors.topMargin: 14
        visible: root.tool === "measure"
        text: root.measurePts.length === 1 ? "Click a second point" : "Measure: click two points on the model  ·  Esc leaves"
        color: Theme.viewDim; font.pixelSize: Theme.fsTiny; font.family: Theme.sans
    }

    // ---- HUD: view name, axis triad (click an axis to look down it)
    Text {   // camera read-out, bottom right
        anchors.right: parent.right; anchors.bottom: parent.bottom; anchors.margins: 14
        visible: !root.showcase && !root.present && studio.stepCount > 0
        text: "GRID " + (root.gridCell >= 1000 ? root.gridCell / 1000 + " m" : root.gridCell + " mm") + "    "
              + (root.ortho ? "ORTHO" : "PERSP " + root.fov + "°") + "    " + Math.round(root.dist) + " mm"
              + (root.tool === "move" ? "    MOVE" : root.tool === "measure" ? "    MEASURE" : "")
        color: Theme.viewDim
        font.pixelSize: Theme.fsTiny; font.family: Theme.mono
    }
    NavGizmo {
        anchors.right: parent.right; anchors.top: parent.top; anchors.margins: 10
        visible: !root.showcase && !root.present && studio.stepCount > 0
        yaw: root.yaw; pitch: root.pitch
        onSnap: (name) => root.setView(name)
    }
}
