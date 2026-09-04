"use client";
import { useMemo, useRef, useState } from "react";
import { Canvas } from "@react-three/fiber";
import { OrbitControls, Line } from "@react-three/drei";
import * as THREE from "three";
import { DNA_COLORS, DNA_COMPLEMENT, BASE_NAME, DnaWindow } from "@/lib/dna";

function strandPoints(n: number, phase: number, radius = 2.6, rise = 0.62, turn = 0.5) {
  const pts: THREE.Vector3[] = [];
  const yOff = ((n - 1) * rise) / 2;
  for (let i = 0; i < n; i++) {
    const a = i * turn + phase;
    pts.push(new THREE.Vector3(radius * Math.cos(a), i * rise - yOff, radius * Math.sin(a)));
  }
  return pts;
}

function Tube({ points, color }: { points: THREE.Vector3[]; color: string }) {
  const geo = useMemo(() => {
    const c = new THREE.CatmullRomCurve3(points);
    return new THREE.TubeGeometry(c, Math.max(8, points.length * 5), 0.1, 8, false);
  }, [points]);
  return <mesh geometry={geo}><meshStandardMaterial color={color} roughness={0.55} /></mesh>;
}

function BaseSphere({ pos, base, inGuide, inPam, onOver, onOut }: any) {
  return (
    <mesh position={pos} scale={inPam ? 1.35 : inGuide ? 1.2 : 1}
      onPointerOver={(e: any) => { e.stopPropagation(); onOver?.(); }}
      onPointerOut={() => onOut?.()}>
      <sphereGeometry args={[0.36, 20, 20]} />
      <meshStandardMaterial color={DNA_COLORS[base] || "#9ca3af"}
        emissive={inPam ? "#f5c542" : inGuide ? DNA_COLORS[base] || "#fff" : "#000"}
        emissiveIntensity={inPam ? 0.8 : inGuide ? 0.45 : 0} roughness={0.3} />
    </mesh>
  );
}

export function DnaHelix3D({ win, onHover }: { win: DnaWindow; onHover?: (i: number | null) => void }) {
  const seq = win.seq;
  const n = seq.length;
  const top = useMemo(() => strandPoints(n, 0), [n]);
  const bot = useMemo(() => strandPoints(n, Math.PI), [n]);
  const [auto, setAuto] = useState(true);
  const controls = useRef<any>(null);
  const wrap = useRef<HTMLDivElement>(null);

  const inGuide = (i: number) => i >= win.guideStart && i < win.guideEnd;
  const inPam = (i: number) => win.pamStart >= 0 && i >= win.pamStart && i < win.pamEnd;

  return (
    <div ref={wrap} className="relative rounded-xl overflow-hidden bg-[#0e0a16] h-[420px]">
      <Canvas camera={{ position: [0, 0, 16], fov: 52 }} gl={{ antialias: true }}>
        <ambientLight intensity={0.7} />
        <directionalLight position={[6, 8, 6]} intensity={1.1} />
        <directionalLight position={[-6, -4, -6]} intensity={0.4} color="#c49ae0" />
        <Tube points={top} color="#7A33A6" />
        <Tube points={bot} color="#4F7E91" />
        {seq.split("").map((b, i) => (
          <group key={i}>
            <Line points={[top[i], bot[i]]} color={inPam(i) ? "#f5c542" : inGuide(i) ? "#c49ae0" : "#555"} lineWidth={inGuide(i) ? 2.5 : 1.2} />
            <BaseSphere pos={top[i]} base={b} inGuide={inGuide(i)} inPam={inPam(i)} onOver={() => onHover?.(i)} onOut={() => onHover?.(null)} />
            <BaseSphere pos={bot[i]} base={DNA_COMPLEMENT[b] || "N"} inGuide={inGuide(i)} inPam={inPam(i)} />
          </group>
        ))}
        <OrbitControls ref={controls} enablePan autoRotate={auto} autoRotateSpeed={0.9} enableDamping />
      </Canvas>

      <div className="absolute top-2 right-2 flex gap-1">
        <button title="Auto-rotate" onClick={() => setAuto((a) => !a)} className="w-8 h-8 rounded-lg bg-white/10 hover:bg-white/20 text-white text-sm backdrop-blur">⟳</button>
        <button title="Reset" onClick={() => controls.current?.reset()} className="w-8 h-8 rounded-lg bg-white/10 hover:bg-white/20 text-white text-sm backdrop-blur">⌖</button>
        <button title="Fullscreen" onClick={() => wrap.current?.requestFullscreen?.()} className="w-8 h-8 rounded-lg bg-white/10 hover:bg-white/20 text-white text-sm backdrop-blur">⤢</button>
      </div>
      <div className="absolute bottom-2 left-2 flex flex-wrap gap-2 text-[10px] text-white/80">
        {Object.entries(DNA_COLORS).filter(([k]) => k !== "N").map(([b, c]) => (
          <span key={b} className="flex items-center gap-1"><span className="w-2.5 h-2.5 rounded-full inline-block" style={{ background: c }} />{b}</span>
        ))}
        <span className="flex items-center gap-1"><span className="w-2.5 h-2.5 rounded-full inline-block" style={{ background: "#c49ae0" }} />guide</span>
        <span className="flex items-center gap-1"><span className="w-2.5 h-2.5 rounded-full inline-block" style={{ background: "#f5c542" }} />PAM</span>
      </div>
    </div>
  );
}
