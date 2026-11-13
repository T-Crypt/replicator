VARYING vec3 wpos;
void MAIN()
{
    wpos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
    POSITION = MODELVIEWPROJECTION_MATRIX * vec4(VERTEX, 1.0);
    POSITION.z -= 0.00025 * POSITION.w;       // pull lines just in front of their faces (no z-fighting)
}
