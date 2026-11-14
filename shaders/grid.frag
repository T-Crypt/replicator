// Workshop floor: an adaptive decimal grid. `span` is the camera distance; the cell size follows it in powers of
// ten (10 mm tiles up close, 100 mm at a metre or two, 1 m for a building), and the finest level cross-fades out
// as you pull back, so the line count on screen stays about the same at every zoom. The floor also fades with
// distance and at grazing angles, so it stays a quiet reference under the build and never shimmers at the horizon.
// Uniforms from GridMaterial.qml: lineColor, majorColor, blueprint, fade, span.
VARYING vec3 wpos;

float gridLine(vec2 p, float cell, float width, out float density)
{
    vec2 c = p / cell;
    vec2 d = fwidth(c);
    vec2 g = abs(fract(c - 0.5) - 0.5) / (d * width);
    density = max(d.x, d.y);
    return 1.0 - min(min(g.x, g.y), 1.0);
}

void MAIN()
{
    vec2 p = wpos.xz;
    float lg = log(max(span, 1.0) / 14.0) / log(10.0);
    float cell = pow(10.0, floor(lg));
    float t = fract(lg);                       // 0 = this level just appeared, 1 = about to hand over
    float d1, d2, d3;
    float minor = gridLine(p, cell, 1.0, d1) * (1.0 - smoothstep(0.35, 1.0, t));
    float major = gridLine(p, cell * 10.0, 1.1, d2);
    float section = gridLine(p, cell * 100.0, 1.4, d3);
    minor *= 1.0 - smoothstep(0.10, 0.34, d1);
    major *= 1.0 - smoothstep(0.12, 0.42, d2);
    section *= 1.0 - smoothstep(0.20, 0.60, d3);

    // axis lines: X red, Z blue
    float ax = 1.0 - min(abs(p.y) / fwidth(p.y) / 1.4, 1.0);
    float az = 1.0 - min(abs(p.x) / fwidth(p.x) / 1.4, 1.0);

    vec3 toCam = CAMERA_POSITION - wpos;
    float dist = length(toCam);
    float f = 1.0 - smoothstep(fade * 0.18, fade * 0.85, dist);
    float graze = smoothstep(0.02, 0.22, abs(toCam.y) / max(dist, 0.001));
    f *= graze;

    float boost = 1.0 + blueprint * 0.35;
    vec3 col = mix(lineColor.rgb, majorColor.rgb, clamp(major + section, 0.0, 1.0));
    float a = minor * 0.10 * boost;
    a = max(a, major * 0.22 * boost);
    a = max(a, section * 0.36 * boost);
    vec3 axc = mix(vec3(0.90, 0.28, 0.30), vec3(0.3, 0.9, 1.0), blueprint);
    vec3 azc = mix(vec3(0.24, 0.52, 0.96), vec3(0.3, 0.9, 1.0), blueprint);
    col = mix(col, axc, ax);
    col = mix(col, azc, az * (1.0 - ax));
    a = max(a, max(ax, az) * 0.62);
    FRAGCOLOR = vec4(col, a * f);
}
