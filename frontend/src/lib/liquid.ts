/**
 * The moving backdrop: slow, dark, flowing light drawn by one fragment shader.
 *
 * It is decoration, so it is built to cost little and to get out of the way:
 * it draws a capped number of pixels at most 30 times a second, stops while the
 * tab is hidden or the light theme is on, and draws a single still frame when
 * the system asks for reduced motion. If WebGL is not available nothing is
 * drawn and the page keeps its plain CSS backdrop.
 */

const VERTEX = `
attribute vec2 corner;
void main() {
  gl_Position = vec4(corner, 0.0, 1.0);
}`;

// Noise warped by itself twice gives the folded, liquid look. The result is
// treated as the height of a surface and lit from its slope, which is what
// makes it read as thick liquid and not as fog. Large areas stay dark and keep
// to deep blue, violet and magenta; the bright cyan is spent on thin highlights
// only. Text sits on glass above this, and amber is kept for marks.
const FRAGMENT = `
#extension GL_OES_standard_derivatives : enable
#ifdef GL_FRAGMENT_PRECISION_HIGH
precision highp float;
#else
precision mediump float;
#endif

uniform vec2 size;
uniform float time;
uniform vec2 pointer;

const vec3 DEEP = vec3(0.012, 0.016, 0.05);
const vec3 BLUE = vec3(0.1, 0.22, 0.95);
const vec3 VIOLET = vec3(0.5, 0.26, 1.0);
const vec3 MAGENTA = vec3(0.95, 0.18, 0.8);
const vec3 CYAN = vec3(0.1, 0.82, 1.0);

float hash(vec2 p) {
  p = fract(p * vec2(123.34, 456.21));
  p += dot(p, p + 45.32);
  return fract(p.x * p.y);
}

float noise(vec2 p) {
  vec2 cell = floor(p);
  vec2 f = fract(p);
  vec2 u = f * f * (3.0 - 2.0 * f);
  return mix(
    mix(hash(cell), hash(cell + vec2(1.0, 0.0)), u.x),
    mix(hash(cell + vec2(0.0, 1.0)), hash(cell + vec2(1.0, 1.0)), u.x),
    u.y
  );
}

float fbm(vec2 p) {
  float value = 0.0;
  float gain = 0.5;
  mat2 turn = mat2(1.6, 1.2, -1.2, 1.6);
  for (int octave = 0; octave < 3; octave++) {
    value += gain * noise(p);
    p = turn * p;
    gain *= 0.5;
  }
  return value;
}

// Blue to violet to magenta and back: the body colour of the liquid.
vec3 body(float s) {
  s = fract(s);
  vec3 colour = mix(BLUE, VIOLET, smoothstep(0.0, 0.3, s));
  colour = mix(colour, MAGENTA, smoothstep(0.3, 0.55, s));
  colour = mix(colour, VIOLET, smoothstep(0.55, 0.8, s));
  return mix(colour, BLUE, smoothstep(0.8, 1.0, s));
}

void main() {
  vec2 uv = gl_FragCoord.xy / size;
  vec2 p = (gl_FragCoord.xy - 0.5 * size) / size.y;
  float t = time * 0.03;

  // The surface bulges gently under the pointer, like glass over liquid.
  vec2 lens = (pointer - 0.5) * vec2(size.x / size.y, 1.0);
  float reach = length(p - lens);
  p += (p - lens) * 0.16 * exp(-reach * reach * 5.0);

  vec2 q = vec2(fbm(p * 0.9 + vec2(0.0, t)), fbm(p * 0.9 + vec2(5.2, -t * 1.3)));
  vec2 r = vec2(
    fbm(p * 1.05 + 2.4 * q + vec2(1.7, 9.2) + t * 0.9),
    fbm(p * 1.05 + 2.4 * q + vec2(8.3, 2.8) - t * 0.7)
  );
  float height = fbm(p * 0.9 + 2.6 * r) + 0.3 * length(r);

  // Light the surface from its slope.
  vec2 slope = vec2(dFdx(height), dFdy(height)) * size.y;
  vec3 normal = normalize(vec3(-slope * 0.5, 1.0));
  vec3 light = normalize(vec3(-0.5, 0.62, 0.6));
  float lit = max(dot(normal, light), 0.0);
  float gloss = pow(max(dot(normal, normalize(light + vec3(0.0, 0.0, 1.0))), 0.0), 70.0);
  float edge = pow(1.0 - normal.z, 1.8);

  float pool = smoothstep(0.34, 0.92, height);
  vec3 tint = body(height * 0.85 + q.x * 0.4 + t * 0.5);
  vec3 colour = DEEP;
  colour += tint * (0.1 + 0.8 * pool) * (0.36 + 0.95 * lit);
  // The deepest pools glow from inside.
  colour += tint * pool * pool * 0.22;
  colour += mix(VIOLET, CYAN, pool) * edge * 0.34;
  colour += mix(CYAN, vec3(1.0), 0.4) * gloss * 0.85;

  // Thin bright lines where the flow folds over itself: the neon.
  float fold = pow(1.0 - abs(sin(height * 7.0)), 30.0);
  colour += fold * mix(CYAN, MAGENTA, smoothstep(0.35, 0.75, r.x)) * (0.1 + 0.32 * pool);

  // A little more light towards the top, where the page begins.
  colour *= 0.8 + 0.35 * uv.y;

  gl_FragColor = vec4(colour, 1.0);
}`;

/** The most pixels the canvas may have. A larger window is drawn at a lower scale. */
const PIXEL_BUDGET = 900_000;
const FRAME_MS = 1000 / 30;
/** Where the still frame is taken from, and where the animation starts. */
const START_SECONDS = 48;

function compile(gl: WebGLRenderingContext, type: number, source: string): WebGLShader | null {
  const shader = gl.createShader(type);
  if (!shader) return null;
  gl.shaderSource(shader, source);
  gl.compileShader(shader);
  if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
    gl.deleteShader(shader);
    return null;
  }
  return shader;
}

function link(gl: WebGLRenderingContext): WebGLProgram | null {
  const vertex = compile(gl, gl.VERTEX_SHADER, VERTEX);
  const fragment = compile(gl, gl.FRAGMENT_SHADER, FRAGMENT);
  const program = gl.createProgram();
  if (!vertex || !fragment || !program) return null;
  gl.attachShader(program, vertex);
  gl.attachShader(program, fragment);
  gl.linkProgram(program);
  return gl.getProgramParameter(program, gl.LINK_STATUS) ? program : null;
}

/** Start drawing on a canvas. Returns a function that stops it. */
export function startLiquid(canvas: HTMLCanvasElement): () => void {
  const gl = canvas.getContext("webgl", {
    alpha: false,
    antialias: false,
    depth: false,
    stencil: false,
    powerPreference: "low-power",
  });
  if (!gl) return () => undefined;
  // The shader lights its surface from screen-space slopes, which WebGL 1
  // offers as an extension. Without it the shader would not compile.
  if (!gl.getExtension("OES_standard_derivatives")) return () => undefined;
  const program = link(gl);
  if (!program) return () => undefined;

  gl.useProgram(program);
  const corners = gl.createBuffer();
  gl.bindBuffer(gl.ARRAY_BUFFER, corners);
  // One triangle that covers the whole canvas.
  gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 3, -1, -1, 3]), gl.STATIC_DRAW);
  const corner = gl.getAttribLocation(program, "corner");
  gl.enableVertexAttribArray(corner);
  gl.vertexAttribPointer(corner, 2, gl.FLOAT, false, 0, 0);

  const size = gl.getUniformLocation(program, "size");
  const time = gl.getUniformLocation(program, "time");
  const pointer = gl.getUniformLocation(program, "pointer");

  const still = window.matchMedia("(prefers-reduced-motion: reduce)");
  const target = { x: 0.5, y: 0.62 };
  const eased = { x: 0.5, y: 0.62 };
  const began = performance.now();
  let lastFrame = 0;
  let request = 0;

  const draw = (seconds: number) => {
    gl.uniform2f(size, canvas.width, canvas.height);
    gl.uniform1f(time, seconds);
    gl.uniform2f(pointer, eased.x, eased.y);
    gl.drawArrays(gl.TRIANGLES, 0, 3);
  };

  const resize = () => {
    const area = Math.max(1, canvas.clientWidth * canvas.clientHeight);
    const scale = Math.min(1, Math.sqrt(PIXEL_BUDGET / area));
    const width = Math.max(1, Math.round(canvas.clientWidth * scale));
    const height = Math.max(1, Math.round(canvas.clientHeight * scale));
    if (canvas.width !== width || canvas.height !== height) {
      canvas.width = width;
      canvas.height = height;
      gl.viewport(0, 0, width, height);
    }
    if (still.matches) draw(START_SECONDS);
  };

  const frame = (now: number) => {
    request = window.requestAnimationFrame(frame);
    if (document.hidden || document.documentElement.dataset.theme === "light") return;
    if (now - lastFrame < FRAME_MS) return;
    lastFrame = now;
    eased.x += (target.x - eased.x) * 0.05;
    eased.y += (target.y - eased.y) * 0.05;
    draw(START_SECONDS + (now - began) / 1000);
  };

  const run = () => {
    window.cancelAnimationFrame(request);
    if (still.matches) {
      eased.x = 0.5;
      eased.y = 0.62;
      draw(START_SECONDS);
    } else {
      request = window.requestAnimationFrame(frame);
    }
  };

  const follow = (event: PointerEvent) => {
    target.x = event.clientX / window.innerWidth;
    target.y = 1 - event.clientY / window.innerHeight;
  };

  resize();
  run();
  canvas.dataset.live = "true";
  window.addEventListener("resize", resize);
  window.addEventListener("pointermove", follow, { passive: true });
  still.addEventListener("change", run);

  return () => {
    window.cancelAnimationFrame(request);
    window.removeEventListener("resize", resize);
    window.removeEventListener("pointermove", follow);
    still.removeEventListener("change", run);
    delete canvas.dataset.live;
    // The context is left alone: a canvas hands back the same one when asked
    // again, and React mounts twice in development, so a lost context would
    // leave the second mount with nothing to draw on.
  };
}

/**
 * Let the sheen on a pane of glass follow the pointer. The position is handed
 * to CSS as two custom properties on the pane under the pointer.
 */
export function trackSheen(): () => void {
  const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const canHover = window.matchMedia("(hover: hover)").matches;
  if (reduced || !canHover) return () => undefined;

  let request = 0;
  let latest: PointerEvent | null = null;

  const apply = () => {
    request = 0;
    const origin = latest?.target;
    if (!latest || !(origin instanceof Element)) return;
    const pane = origin.closest<HTMLElement>(".card, .ask-field");
    if (!pane) return;
    const box = pane.getBoundingClientRect();
    pane.style.setProperty("--mx", `${Math.round(latest.clientX - box.left)}px`);
    pane.style.setProperty("--my", `${Math.round(latest.clientY - box.top)}px`);
  };

  const move = (event: PointerEvent) => {
    latest = event;
    if (!request) request = window.requestAnimationFrame(apply);
  };

  document.addEventListener("pointermove", move, { passive: true });
  return () => {
    document.removeEventListener("pointermove", move);
    window.cancelAnimationFrame(request);
  };
}
