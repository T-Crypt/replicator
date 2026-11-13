// Infinite-feel workshop floor: 10 mm minor tiles, 100 mm major lines, 1 m section lines, faded with distance.
// Uniforms from GridMaterial.qml: lineColor, majorColor, blueprint, fade.
VARYING vec3 wpos;
void MAIN()
{
    vec2 p = wpos.xz;
    vec2 d1 = fwidth(p / 10.0);
    vec2 g1 = abs(fract(p / 10.0 - 0.5) - 0.5) / d1;
    float minor = 1.0 - min(min(g1.x, g1.y), 1.0);
    vec2 d2 = fwidth(p / 100.0);
    vec2 g2 = abs(fract(p / 100.0 - 0.5) - 0.5) / d2;
    float major = 1.0 - min(min(g2.x, g2.y), 1.0);
    vec2 d3 = fwidth(p / 1000.0);
    vec2 g3 = abs(fract(p / 1000.0 - 0.5) - 0.5) / (d3 * 1.6);
    float section = 1.0 - min(min(g3.x, g3.y), 1.0);
    // axis lines: X red, Z blue (C4D convention)
    float ax = 1.0 - min(abs(p.y) / fwidth(p.y) / 1.5, 1.0);
    float az = 1.0 - min(abs(p.x) / fwidth(p.x) / 1.5, 1.0);
    float dist = length(wpos - CAMERA_POSITION);
    float f = 1.0 - smoothstep(fade * 0.25, fade, dist);
    // minor tiles vanish when they get denser than a few pixels
    float minorFade = 1.0 - smoothstep(0.15, 0.5, max(d1.x, d1.y));
    vec3 col = lineColor.rgb;
    float a = minor * 0.35 * minorFade;
    col = mix(col, majorColor.rgb, clamp(major + section, 0.0, 1.0));
    a = max(a, major * 0.6);
    a = max(a, section * 0.9);
    vec3 axc = mix(vec3(0.85, 0.25, 0.25), vec3(0.3, 0.9, 1.0), blueprint);
    vec3 azc = mix(vec3(0.25, 0.45, 0.95), vec3(0.3, 0.9, 1.0), blueprint);
    col = mix(col, axc, ax);
    col = mix(col, azc, az * (1.0 - ax));
    a = max(a, max(ax, az) * 0.9);
    FRAGCOLOR = vec4(col, a * f);
}
