"use client";
import { useMemo, useRef, useState } from "react";
import { Canvas, useThree } from "@react-three/fiber";
import { OrbitControls, Html } from "@react-three/drei";
import * as THREE from "three";
import { RNA_COLORS, BASE_NAME } from "@/lib/dna";

function helixPoints(n: number, radius = 2.3, rise = 0.78, turn = 0.62) {
  const pts: THREE.Vector3[] = [];
  const yOff = ((n - 1) * rise) / 2;
  for (let i = 0; i < n; i++) {
    const a = i * turn;
    pts.push(new THREE.Vector3(radius * Math.cos(a), i * rise - yOff, radius * Math.sin(a)));
  }
  return pts;
}

function Backbone({ points }: { points: THREE.Vector3[] }) {
  const geo = useMemo(() => {
    const curve = new THREE.CatmullRomCurve3(points);
    return new THREE.TubeGeometry(curve, Math.max(8, points.length * 6), 0.11, 10, false);
  }, [points]);
  return (
    <mesh geometry={geo}>
      <meshStandardMaterial color="#7A33A6" roughness={0.5} metalness={0.1} />
    </mesh>
  );
}

function Bases({ seq, points, hovered, selected, setHovered, onSelect }: any) {
  return (
    <group>
      {seq.split("").map((b: string, i: number) => {
        const active = hovered === i || selected === i;
        return (
          <mesh
            key={i}
            position={points[i]}
            scale={active ? 1.45 : 1}
            onPointerOver={(e: any) => { e.stopPropagation(); setHovered(i); }}
            onPointerOut={() => setHovered(null)}
            onClick={(e: any) => { e.stopPropagation(); onSelect(i); }}
          >
            <sphereGeometry args={[0.52, 28, 28]} />
            <meshStandardMaterial
              color={RNA_COLORS[b] || "#9ca3af"}
              emissive={selected === i ? RNA_COLORS[b] || "#fff" : "#000"}
              emissiveIntensity={selected === i ? 0.6 : 0}
              roughness={0.3}
              metalness={0.15}
            />
            {hovered === i && (
              <Html distanceFactor={10} center>
                <div style={{ background: "#2C1A3D", color: "#fff", padding: "2px 8px", borderRadius: 8, fontSize: 12, fontWeight: 700, whiteSpace: "nowrap", transform: "translateY(-26px)" }}>
                  {b} · {i + 1}
                </div>
              </Html>
            )}
          </mesh>
        );
      })}
    </group>
  );
}

function CaptureGL({ glRef }: any) {
  const { gl } = useThree();
  glRef.current = gl;
  return null;
}

export function GuideRna3D({ sequence, selected, onSelect, onHover }: {
  sequence: string; selected: number | null; onSelect: (i: number) => void; onHover?: (i: number | null) => void;
}) {
  const seq = (sequence || "").toUpperCase();
  const points = useMemo(() => helixPoints(seq.length), [seq]);
  const [hovered, setHov] = useState<number | null>(null);
  const [auto, setAuto] = useState(true);
  const controls = useRef<any>(null);
  const glRef = useRef<any>(null);
  const wrap = useRef<HTMLDivElement>(null);

  const setHovered = (i: number | null) => { setHov(i); onHover?.(i); };

  function screenshot() {
    const gl = glRef.current; if (!gl) return;
    const url = gl.domElement.toDataURL("image/png");
    const a = document.createElement("a"); a.href = url; a.download = "guide-rna-3d.png"; a.click();
  }
  function fullscreen() { wrap.current?.requestFullscreen?.(); }

  return (
    <div ref={wrap} className="relative rounded-xl overflow-hidden bg-[#0e0a16] h-[420px]">
      <Canvas camera={{ position: [0, 0, 14], fov: 50 }} gl={{ preserveDrawingBuffer: true, antialias: true }}>
        <CaptureGL glRef={glRef} />
        <ambientLight intensity={0.7} />
        <directionalLight position={[6, 8, 6]} intensity={1.1} />
        <directionalLight position={[-6, -4, -6]} intensity={0.4} color="#c49ae0" />
        <Backbone points={points} />
        <Bases seq={seq} points={points} hovered={hovered} selected={selected} setHovered={setHovered} onSelect={onSelect} />
        <OrbitControls ref={controls} enablePan autoRotate={auto} autoRotateSpeed={1.1} enableDamping />
      </Canvas>

      <div className="absolute top-2 right-2 flex gap-1">
        {[
          ["⟳", () => setAuto((a) => !a), auto ? "Pause rotation" : "Auto-rotate"],
          ["⌖", () => controls.current?.reset(), "Reset view"],
          ["⤢", fullscreen, "Fullscreen"],
          ["📷", screenshot, "Screenshot"],
        ].map(([icon, fn, title]: any, i) => (
          <button key={i} title={title} onClick={fn}
            className="w-8 h-8 rounded-lg bg-white/10 hover:bg-white/20 text-white text-sm backdrop-blur">{icon}</button>
        ))}
      </div>
      <div className="absolute bottom-2 left-2 flex gap-2 text-[10px] text-white/80">
        {Object.entries(RNA_COLORS).filter(([k]) => k !== "N").map(([b, c]) => (
          <span key={b} className="flex items-center gap-1"><span className="w-2.5 h-2.5 rounded-full inline-block" style={{ background: c }} />{b}={BASE_NAME[b]}</span>
        ))}
      </div>
    </div>
  );
}
