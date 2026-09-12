"use client";

import React, { useEffect, useRef, useSyncExternalStore } from "react";
import { Renderer, Program, Mesh, Triangle, type OGLRenderingContext } from "ogl";
import "./Grainient.css";

export interface GrainientProps {
  className?: string;
  style?: React.CSSProperties;
  color1?: string;
  color2?: string;
  color3?: string;
  timeSpeed?: number;
  colorBalance?: number;
  warpStrength?: number;
  warpFrequency?: number;
  warpSpeed?: number;
  warpAmplitude?: number;
  blendAngle?: number;
  blendSoftness?: number;
  rotationAmount?: number;
  noiseScale?: number;
  grainAmount?: number;
  grainScale?: number;
  grainAnimated?: boolean;
  contrast?: number;
  gamma?: number;
  saturation?: number;
  lightMode?: boolean;
  centerX?: number;
  centerY?: number;
  zoom?: number;
}

function hexToRgb(hex: string): [number, number, number] {
  const clean = hex.replace("#", "");
  const bigint = parseInt(clean, 16);
  if (isNaN(bigint)) return [0.05, 0.2, 0.35];
  const r = ((bigint >> 16) & 255) / 255;
  const g = ((bigint >> 8) & 255) / 255;
  const b = (bigint & 255) / 255;
  return [r, g, b];
}

const subscribeMotion = (callback: () => void) => {
  if (typeof window === "undefined") return () => {};
  const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
  mq.addEventListener("change", callback);
  return () => mq.removeEventListener("change", callback);
};

const getMotionSnapshot = () => {
  if (typeof window === "undefined") return false;
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
};

const getMotionServerSnapshot = () => false;

const vertexShader = `
attribute vec2 position;
attribute vec2 uv;
varying vec2 vUv;
void main() {
  vUv = uv;
  gl_Position = vec4(position, 0.0, 1.0);
}
`;

const fragmentShader = `
precision highp float;
varying vec2 vUv;

uniform vec3 uColor1;
uniform vec3 uColor2;
uniform vec3 uColor3;
uniform float uTime;
uniform float uColorBalance;
uniform float uWarpStrength;
uniform float uWarpFrequency;
uniform float uWarpAmplitude;
uniform float uBlendAngle;
uniform float uBlendSoftness;
uniform float uRotationAmount;
uniform float uNoiseScale;
uniform float uGrainAmount;
uniform float uGrainScale;
uniform float uContrast;
uniform float uGamma;
uniform float uSaturation;
uniform float uLightMode;
uniform vec2 uCenter;
uniform float uZoom;

float hash(vec2 p) {
  return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453123);
}

vec2 rotate(vec2 uv, float angle) {
  float s = sin(angle);
  float c = cos(angle);
  return mat2(c, -s, s, c) * uv;
}

void main() {
  vec2 uv = (vUv - 0.5 + uCenter) / max(0.01, uZoom);
  uv = rotate(uv, radians(uRotationAmount));

  float angleRad = radians(uBlendAngle);
  vec2 dir = vec2(cos(angleRad), sin(angleRad));

  float wave = sin(dot(uv, dir) * uWarpFrequency + uTime) * (uWarpAmplitude / 100.0);
  vec2 warpedUv = uv + dir * wave * uWarpStrength;

  float t = dot(warpedUv, dir) * 0.5 + 0.5 + uColorBalance;
  t = clamp(t, 0.0, 1.0);

  vec3 color;
  float mid = 0.5;
  float softness = max(0.01, uBlendSoftness);
  if (t < mid) {
    float f = smoothstep(0.0, mid + softness * 0.5, t);
    color = mix(uColor3, uColor1, f);
  } else {
    float f = smoothstep(mid - softness * 0.5, 1.0, t);
    color = mix(uColor1, uColor2, f);
  }

  // Subtle film grain
  float grain = (hash(vUv * uGrainScale * 500.0) - 0.5) * uGrainAmount;
  color += grain;

  // Contrast & Gamma
  color = (color - 0.5) * uContrast + 0.5;
  color = pow(max(color, vec3(0.0)), vec3(1.0 / max(0.01, uGamma)));

  // Saturation
  float luma = dot(color, vec3(0.299, 0.587, 0.114));
  color = mix(vec3(luma), color, uSaturation);

  if (uLightMode > 0.5) {
    float energy = max(max(color.r, color.g), color.b);
    vec3 hue = color / max(energy, 0.001);
    float chroma = length(color - vec3(dot(color, vec3(0.333333))));
    float coverage = clamp(0.12 + chroma * 1.15 + energy * 0.18, 0.0, 0.88);
    color = mix(vec3(1.0), clamp(hue * 0.58 + color * 0.18, 0.0, 1.0), coverage);
  }

  gl_FragColor = vec4(clamp(color, 0.0, 1.0), 1.0);
}
`;

export const Grainient: React.FC<GrainientProps> = ({
  className = "landing-hero__grainient",
  style,
  color1 = "#0B3157",
  color2 = "#0B6E86",
  color3 = "#07111F",
  timeSpeed = 0.07,
  colorBalance = -0.18,
  warpStrength = 0.28,
  warpFrequency = 2.4,
  warpSpeed = 0.35,
  warpAmplitude = 80,
  blendAngle = 18,
  blendSoftness = 0.16,
  rotationAmount = 95,
  noiseScale = 1.1,
  grainAmount = 0.025,
  grainScale = 1.5,
  grainAnimated = false,
  contrast = 1.08,
  gamma = 1.0,
  saturation = 0.72,
  lightMode = false,
  centerX = 0.0,
  centerY = 0.0,
  zoom = 1.05,
}) => {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const reducedMotion = useSyncExternalStore(
    subscribeMotion,
    getMotionSnapshot,
    getMotionServerSnapshot
  );

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    let renderer: Renderer | null = null;
    let gl: OGLRenderingContext | null = null;
    let program: Program | null = null;
    let mesh: Mesh | null = null;
    let rafId: number | null = null;
    let isVisible = true;
    let isTabActive = true;

    try {
      renderer = new Renderer({
        alpha: true,
        antialias: false,
        powerPreference: "low-power",
        dpr: Math.min(typeof window !== "undefined" ? window.devicePixelRatio : 1, 1.5),
      });

      gl = renderer.gl;
      if (!gl) return;

      gl.clearColor(0, 0, 0, 0);

      const geometry = new Triangle(gl);
      program = new Program(gl, {
        vertex: vertexShader,
        fragment: fragmentShader,
        uniforms: {
          uColor1: { value: hexToRgb(color1) },
          uColor2: { value: hexToRgb(color2) },
          uColor3: { value: hexToRgb(color3) },
          uTime: { value: 0 },
          uColorBalance: { value: colorBalance },
          uWarpStrength: { value: warpStrength },
          uWarpFrequency: { value: warpFrequency },
          uWarpAmplitude: { value: warpAmplitude },
          uBlendAngle: { value: blendAngle },
          uBlendSoftness: { value: blendSoftness },
          uRotationAmount: { value: rotationAmount },
          uNoiseScale: { value: noiseScale },
          uGrainAmount: { value: grainAmount },
          uGrainScale: { value: grainScale },
          uContrast: { value: contrast },
          uGamma: { value: gamma },
          uSaturation: { value: saturation },
          uLightMode: { value: lightMode ? 1.0 : 0.0 },
          uCenter: { value: [centerX, centerY] },
          uZoom: { value: zoom },
        },
      });

      mesh = new Mesh(gl, { geometry, program });

      const canvas = gl.canvas as HTMLCanvasElement;
      canvas.style.display = "block";
      canvas.style.width = "100%";
      canvas.style.height = "100%";
      container.appendChild(canvas);

      const resize = () => {
        if (!container || !renderer) return;
        const width = container.clientWidth || 300;
        const height = container.clientHeight || 300;
        renderer.setSize(width, height);
      };

      resize();
      const ro = new ResizeObserver(resize);
      ro.observe(container);

      // IntersectionObserver to pause when offscreen
      const io = new IntersectionObserver((entries) => {
        if (entries[0]) {
          isVisible = entries[0].isIntersecting;
        }
      }, { threshold: 0.05 });
      io.observe(container);

      // Visibility change to pause when tab hidden
      const handleVisibilityChange = () => {
        isTabActive = !document.hidden;
      };
      document.addEventListener("visibilitychange", handleVisibilityChange);

      let lastTime = performance.now();
      let accumulatedTime = 0;

      // Render single frame for reduced-motion
      if (reducedMotion) {
        program.uniforms.uTime.value = 1.0;
        renderer.render({ scene: mesh });
      } else {
        const update = (now: number) => {
          const dt = (now - lastTime) / 1000;
          lastTime = now;

          if (isVisible && isTabActive) {
            accumulatedTime += dt * timeSpeed * (warpSpeed || 1.0);
            if (program) {
              program.uniforms.uTime.value = accumulatedTime;
            }
            if (renderer && mesh) {
              renderer.render({ scene: mesh });
            }
          }

          rafId = requestAnimationFrame(update);
        };

        rafId = requestAnimationFrame(update);
      }

      return () => {
        if (rafId) cancelAnimationFrame(rafId);
        ro.disconnect();
        io.disconnect();
        document.removeEventListener("visibilitychange", handleVisibilityChange);

        if (canvas && canvas.parentElement === container) {
          container.removeChild(canvas);
        }

        if (gl) {
          gl.getExtension("WEBGL_lose_context")?.loseContext();
        }
      };
    } catch {
      // Intentional static CSS fallback remains on container
    }
  }, [
    color1,
    color2,
    color3,
    timeSpeed,
    colorBalance,
    warpStrength,
    warpFrequency,
    warpSpeed,
    warpAmplitude,
    blendAngle,
    blendSoftness,
    rotationAmount,
    noiseScale,
    grainAmount,
    grainScale,
    grainAnimated,
    contrast,
    gamma,
    saturation,
    lightMode,
    centerX,
    centerY,
    zoom,
    reducedMotion,
  ]);

  const staticFallbackStyle: React.CSSProperties = {
    background: `radial-gradient(ellipse at 50% 30%, ${color2} 0%, ${color1} 45%, ${color3} 100%)`,
    ...style,
  };

  return (
    <div
      ref={containerRef}
      aria-hidden="true"
      data-grainient-mode={lightMode ? "light" : "dark"}
      className={className}
      style={staticFallbackStyle}
    />
  );
};

export default Grainient;
