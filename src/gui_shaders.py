# ------------------------------ Rectangle Shader ------------------------------
RECT_VERTEX_SHADER = """
#version 330 core
layout(location = 0) in vec2 aPos;
uniform vec2 uOffset;
uniform vec2 uScale;
uniform vec2 uScreenSize;
void main() {
    vec2 pos = (aPos * uScale + uOffset) / uScreenSize * 2.0 - 1.0;
    gl_Position = vec4(pos, 0.0, 1.0);
}
"""

RECT_FRAGMENT_SHADER = """
#version 330 core
uniform vec4 uColor;
out vec4 FragColor;
void main() {
    FragColor = uColor;
}
"""

# ------------------------------ Text Shader (flip only vertical) ------------------------------
TEXT_VERTEX_SHADER = """
#version 330 core
layout(location = 0) in vec2 aPos;
layout(location = 1) in vec2 aTexCoord;
uniform vec2 uOffset;
uniform vec2 uScale;
uniform vec2 uScreenSize;
uniform vec4 uTexRect; // (x, y, w, h) in texture coordinates
out vec2 vTexCoord;
void main() {
    vec2 pos = (aPos * uScale + uOffset) / uScreenSize * 2.0 - 1.0;
    gl_Position = vec4(pos, 0.0, 1.0);
    // Flip only vertical (OpenGL texture origin is bottom-left, font image origin is top-left)
    vTexCoord = uTexRect.xy + vec2(aTexCoord.x, 1.0 - aTexCoord.y) * uTexRect.zw;
}
"""

TEXT_FRAGMENT_SHADER = """
#version 330 core
uniform sampler2D uFontTexture;
uniform vec3 uColor;
in vec2 vTexCoord;
out vec4 FragColor;
void main() {
    float alpha = texture(uFontTexture, vTexCoord).r;
    FragColor = vec4(uColor, alpha);
}
"""