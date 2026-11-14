// Reference image plane: a sheet of frosted glass. The paper white of the view is almost keyed out (enough is
// left that a dark figure still reads against a dark stage), the figure stays solid, a thin frame marks the sheet.
// Uniforms from ReferenceMaterial.qml: tex, strength, paper.
VARYING vec2 uv;
void MAIN()
{
    vec4 c = texture(tex, uv);
    float white = min(c.r, min(c.g, c.b));
    float ink = 1.0 - smoothstep(0.80, 0.97, white);
    vec2 e = min(uv, 1.0 - uv);
    float frame = 1.0 - smoothstep(0.0, 0.005, min(e.x, e.y));
    vec3 col = mix(c.rgb, vec3(0.45, 0.8, 1.0), frame);
    float a = mix(paper, strength, ink);
    FRAGCOLOR = vec4(col, max(a, frame * 0.45));
}
