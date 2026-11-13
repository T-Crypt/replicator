// Replicator part material: PBR when built, a holo scan while it materializes, cyan line-work in blueprint mode.
// Uniforms come from HoloMaterial.qml properties: baseColor, emissiveColor, metal, rough, reveal, minY, maxY,
// blueprint, selected, time.
void MAIN()
{
    vec3 wp = VAR_WORLD_POSITION;
    float span = max(maxY - minY, 1.0);
    float scan = mix(minY - span * 0.05, maxY + span * 0.05, reveal);   // the build plane rises with reveal
    if (wp.y > scan)
        discard;                                                         // not built yet

    vec3 cyan = vec3(0.25, 0.85, 1.0);
    float below = scan - wp.y;
    float edge = 1.0 - smoothstep(0.0, span * 0.02, below);              // bright seam at the scan plane
    float band = (1.0 - smoothstep(0.0, span * 0.22, below)) * step(reveal, 0.999);   // freshly built zone

    // voxel lattice in the fresh zone, world space so it reads as one field across parts
    float cell = max(span / 28.0, 1.5);
    vec3 g = abs(fract(wp / cell) - 0.5);
    float lattice = smoothstep(0.42, 0.5, max(g.x, max(g.y, g.z)));

    // blueprint: contour lines every 1/40 of the height plus a fresnel rim
    vec3 n = normalize(VAR_WORLD_NORMAL);
    float rim = pow(1.0 - clamp(abs(dot(n, normalize(VIEW_VECTOR))), 0.0, 1.0), 2.5);
    float cy = abs(fract(wp.y / (span / 40.0)) - 0.5);
    float contour = 1.0 - smoothstep(0.0, 0.06, cy);

    vec3 navy = vec3(0.03, 0.10, 0.22);
    vec3 albedo = mix(baseColor.rgb, tint.rgb * 0.85, tintAmount);   // colour by component (Dissect)
    albedo = mix(albedo, navy, blueprint);
    albedo = mix(albedo, albedo * 0.25, band);                           // fresh zone is darker under the glow
    BASE_COLOR = vec4(albedo, 1.0);
    METALNESS = mix(metal, 0.0, blueprint);
    ROUGHNESS = mix(rough, 0.9, blueprint);
    vec3 em = emissiveColor.rgb;
    em += cyan * (edge * 3.0 + band * lattice * 1.6 + band * 0.15);
    em += cyan * blueprint * (rim * 1.4 + contour * 0.35);
    em += vec3(1.0, 0.62, 0.15) * selected * (0.25 + rim * 1.2);         // amber when selected
    em += tint.rgb * xray * (0.15 + rim * 1.5);                         // x-ray ghost for isolated views
    EMISSIVE_COLOR = em;
}
