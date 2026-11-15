VARYING vec3 wpos;
void MAIN()
{
    float span = max(maxY - minY, 1.0);
    float scan = mix(minY - span * 0.05, maxY + span * 0.05, reveal);
    if (wpos.y > scan)
        discard;
    FRAGCOLOR = vec4(lineColor.rgb, lineColor.a * strength);
}
