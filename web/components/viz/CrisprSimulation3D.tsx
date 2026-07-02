"use client";
// Animated, stylized simulation of the CRISPR–Cas9 mechanism for a selected guide.
// Stages: scan -> PAM recognition -> R-loop formation -> cleavage -> double-strand
// break -> edit (excised DNA released, gRNA/edit strand slots into the gap).
// This is an *educational / illustrative* animation of the canonical Cas9 mechanism —
// it is not a physics/structural simulation. Geometry is stylized for clarity.
import { memo, useEffect, useMemo, useRef, useState } from "react";
import type { CSSProperties, MutableRefObject, RefObject } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import { OrbitControls, Line, Html } from "@react-three/drei";
import * as THREE from "three";
import { DNA_COLORS, DNA_COMPLEMENT, RNA_COLORS, DnaWindow } from "@/lib/dna";

// ---- stage model -----------------------------------------------------------
export interface SimStage {
  key: string;
  label: string;
  desc: string;
  start: number; // progress at which this stage begins (0..1)
}
export const STAGES: SimStage[] = [
  { key: "scan", label: "1 · Scanning", start: 0.0,
    desc: "The Cas9–gRNA ribonucleoprotein slides along the DNA, probing for a PAM (protospacer-adjacent motif) next to a matching target." },
  { key: "pam", label: "2 · PAM recognition", start: 0.2,
    desc: "Cas9 recognises and clamps onto the PAM. PAM binding licenses local unwinding of the adjacent DNA." },
  { key: "rloop", label: "3 · R-loop formation", start: 0.34,
    desc: "The duplex melts and the gRNA spacer base-pairs with the target strand, displacing the non-target strand to form an R-loop." },
  { key: "cut", label: "4 · Cleavage", start: 0.54,
    desc: "A complete R-loop activates the nuclease lobes: HNH cleaves the target strand and RuvC cleaves the non-target strand ~3 bp upstream of the PAM." },
  { key: "dsb", label: "5 · Double-strand break", start: 0.64,
    desc: "A blunt double-strand break is produced and the two DNA ends separate." },
  { key: "edit", label: "6 · Edit · gRNA replaces cut DNA", start: 0.8,
    desc: "The excised DNA segment is released and the highlighted guide/edit strand slides into the gap, re-forming an edited duplex. Illustrative: in a real knock-in the new sequence is supplied by a donor template that Cas9/gRNA direct to the cut site." },
];

export function stageForProgress(p: number): number {
  let s = 0;
  for (let i = 0; i < STAGES.length; i++) if (p >= STAGES[i].start) s = i;
  return s;
}

// ---- math helpers ----------------------------------------------------------
const clamp01 = (x: number) => Math.max(0, Math.min(1, x));
const ramp = (p: number, a: number, b: number) => clamp01((p - a) / (b - a));
const smooth = (x: number) => x * x * (3 - 2 * x);

// Shared, mutable control channel between the HTML controls and the 3D scene.
interface Control {
  playing: boolean;
  speed: number;
  seek: number | null; // when set, the scene jumps here (then clears it)
  loop: boolean;
}

// ---- geometry for a horizontal B-DNA-ish duplex ----------------------------
const RISE = 0.86;   // spacing between bases along X
const RAD = 1.35;    // helix radius (Y/Z)
const TURN = 0.52;   // radians per base

function baseXYZ(i: number, centerX: number, phase: number): THREE.Vector3 {
  const a = i * TURN + phase;
  return new THREE.Vector3(i * RISE - centerX, RAD * Math.cos(a), RAD * Math.sin(a));
}

// =============================================================================
// Memoized so it does not re-render when the parent updates the progress slider
// state ~12x/sec — all per-frame changes happen imperatively inside useFrame.
const Scene = memo(function Scene({
  win, guideSeq, control, onFrame,
}: {
  win: DnaWindow;
  guideSeq: string;
  control: MutableRefObject<Control>;
  onFrame: (p: number) => void;
}) {
  const seq = win.seq;
  const n = seq.length;
  const centerX = ((n - 1) * RISE) / 2;

  // Precompute rest positions for both strands.
  const top = useMemo(() => Array.from({ length: n }, (_, i) => baseXYZ(i, centerX, 0)), [n, centerX]);
  const bot = useMemo(() => Array.from({ length: n }, (_, i) => baseXYZ(i, centerX, Math.PI)), [n, centerX]);

  const gStart = Math.max(0, win.guideStart);
  const gEnd = Math.min(n, win.guideEnd);
  const pamStart = win.pamStart;
  const pamEnd = win.pamEnd;
  const inGuide = (i: number) => i >= gStart && i < gEnd;
  const inPam = (i: number) => pamStart >= 0 && i >= pamStart && i < pamEnd;

  // Cut site: ~3 bp inside the protospacer from the PAM-proximal end.
  const pamOnRight = pamStart >= gEnd; // + strand: PAM is 3' of guide
  const cutIndex = pamOnRight
    ? Math.max(gStart, gEnd - 3)
    : Math.min(gEnd, gStart + 3);
  const dockX = (top[Math.min(n - 1, Math.max(0, cutIndex))]?.x) ?? 0;
  const entryX = pamOnRight ? -centerX - 8 : centerX + 8;

  // Refs we animate imperatively (avoids per-frame React re-renders).
  const rnp = useRef<THREE.Group>(null);
  const leftG = useRef<THREE.Group>(null);   // everything left of the cut
  const rightG = useRef<THREE.Group>(null);  // everything right of the cut
  const rloopTop = useRef<THREE.Group>(null); // displaced non-target strand (excised on edit)
  const rloopMats = useRef<THREE.MeshStandardMaterial[]>([]);
  const grnaPair = useRef<THREE.Group>(null); // gRNA that pairs into the R-loop / slots in
  const grnaMats = useRef<THREE.MeshStandardMaterial[]>([]);
  const spark = useRef<THREE.Mesh>(null);
  const sparkMat = useRef<THREE.MeshStandardMaterial>(null);
  const sparkLight = useRef<THREE.PointLight>(null);
  const hnhMat = useRef<THREE.MeshStandardMaterial>(null);
  const ruvcMat = useRef<THREE.MeshStandardMaterial>(null);
  const lobeGroup = useRef<THREE.Group>(null);
  const editGlow = useRef<THREE.PointLight>(null);

  const progress = useRef(0);
  const lastReport = useRef(0);

  useFrame((_, dt) => {
    const c = control.current;
    // consume a seek request
    if (c.seek != null) {
      progress.current = clamp01(c.seek);
      c.seek = null;
    } else if (c.playing) {
      progress.current += dt * 0.13 * c.speed;
      if (progress.current >= 1) progress.current = c.loop ? 0 : 1;
    }
    const p = progress.current;

    // ---- derived stage amounts ----
    const scan = smooth(ramp(p, 0.0, 0.2));       // RNP travels to dock
    const dock = smooth(ramp(p, 0.2, 0.32));      // settle onto PAM
    const unwind = smooth(ramp(p, 0.34, 0.52));   // R-loop opens
    const cutAmt = ramp(p, 0.54, 0.64);           // nuclease flash
    const dsbOpen = smooth(ramp(p, 0.64, 0.78));  // ends separate
    const edit = smooth(ramp(p, 0.8, 1.0));       // excise + gRNA slots in

    // RNP glide + settle; releases and lifts away during the edit phase
    if (rnp.current) {
      rnp.current.position.x = THREE.MathUtils.lerp(entryX, dockX, scan);
      rnp.current.position.y = Math.sin(dock * Math.PI) * 0.12 + edit * 4.0;
      rnp.current.scale.setScalar(0.9 + 0.1 * dock);
      rnp.current.visible = scan > 0.001 && edit < 0.97;
    }
    if (lobeGroup.current) {
      const b = 1 + 0.02 * Math.sin(p * 40) * dock;
      lobeGroup.current.scale.set(b, b, b);
    }

    // R-loop displaced (non-target) strand: lifts during unwind, then is EXCISED
    // (flies up and away, fading out) during the edit phase.
    if (rloopTop.current) {
      rloopTop.current.position.y = unwind * 1.7 + edit * 5.0;
      rloopTop.current.position.z = unwind * 0.6 + edit * 2.4;
      rloopTop.current.position.x = edit * 2.6;
      rloopTop.current.rotation.z = unwind * 0.25 + edit * 1.0;
    }
    rloopMats.current.forEach((m) => { if (m) m.opacity = (0.2 + 0.8 * unwind) * (1 - edit); });

    // gRNA / edit strand: fades in with the R-loop, then descends into the gap
    // (replacing the excised DNA) and glows as the "edited" strand.
    if (grnaPair.current) {
      grnaPair.current.visible = unwind > 0.01 || edit > 0.01;
      grnaPair.current.position.y = -edit * 1.45;
      grnaPair.current.position.z = -edit * 0.95;
    }
    grnaMats.current.forEach((m) => {
      if (m) {
        m.opacity = 0.15 + 0.85 * Math.max(unwind, edit);
        m.emissiveIntensity = 0.35 + 1.0 * edit;
      }
    });
    if (editGlow.current) { editGlow.current.position.x = dockX; editGlow.current.intensity = edit * 3.2; }

    // Nuclease domains glow as they engage, peak during the cut, fade after edit
    const glow = Math.max(dock * 0.25, cutAmt) * (1 - edit);
    if (hnhMat.current) hnhMat.current.emissiveIntensity = 0.2 + 1.6 * glow;
    if (ruvcMat.current) ruvcMat.current.emissiveIntensity = 0.2 + 1.6 * glow;

    // Cleavage spark (a brief pulse during the cut)
    const pulse = Math.sin(clamp01(cutAmt) * Math.PI);
    if (spark.current) {
      spark.current.position.x = dockX;
      spark.current.visible = cutAmt > 0.001 && cutAmt < 0.999;
      spark.current.scale.setScalar(0.2 + pulse * 1.1);
    }
    if (sparkMat.current) sparkMat.current.emissiveIntensity = pulse * 3;
    if (sparkLight.current) sparkLight.current.intensity = pulse * 6;

    // Double-strand break: halves separate, then close partway around the insert
    const sep = 1.35 * dsbOpen * (1 - 0.72 * edit);
    if (leftG.current) { leftG.current.position.x = -sep; leftG.current.position.y = -dsbOpen * 0.22 * (1 - edit); }
    if (rightG.current) { rightG.current.position.x = sep; rightG.current.position.y = dsbOpen * 0.22 * (1 - edit); }

    // report progress to the HTML layer a few times per second
    lastReport.current += dt;
    if (lastReport.current > 0.08) { lastReport.current = 0; onFrame(p); }
  });

  // Which side of the cut a base index falls on.
  const isLeft = (i: number) => i < cutIndex;
  const idx = useMemo(() => Array.from({ length: n }, (_, i) => i), [n]);

  // Base sphere
  const Sphere = ({ pos, base, hi, pam }: { pos: THREE.Vector3; base: string; hi: boolean; pam: boolean }) => (
    <mesh position={pos} scale={pam ? 1.3 : hi ? 1.15 : 1}>
      <sphereGeometry args={[0.34, 18, 18]} />
      <meshStandardMaterial
        color={DNA_COLORS[base] || "#9ca3af"}
        emissive={pam ? "#f5c542" : hi ? DNA_COLORS[base] || "#000" : "#000"}
        emissiveIntensity={pam ? 0.7 : hi ? 0.35 : 0}
        roughness={0.35}
      />
    </mesh>
  );

  // Backbone as short segments so each half can move independently.
  // `skipGuide` drops segments crossing the melted guide region (top strand).
  const seg = (pts: THREE.Vector3[], i: number, color: string, side: boolean, skipGuide: boolean) => {
    if (i >= n - 1) return null;
    if (isLeft(i) !== side || isLeft(i + 1) !== side) return null; // spans the cut
    if (skipGuide && (inGuide(i) || inGuide(i + 1))) return null;   // melted region
    return <Line key={`${color}${i}`} points={[pts[i], pts[i + 1]]} color={color} lineWidth={2.4} />;
  };

  // gRNA (RNA) that pairs into the R-loop — parallel to the target strand, lifted.
  const grnaPts = useMemo(
    () => Array.from({ length: gEnd - gStart }, (_, k) => {
      const v = bot[gStart + k].clone();
      v.y += 0.7; v.z += 0.9; // sit just above the target strand
      return v;
    }),
    [gStart, gEnd, bot],
  );

  // Render one DNA half (bases + backbone). Top-strand guide bases are omitted
  // here — they live in the liftable / excisable R-loop group instead.
  const half = (side: boolean, ref: RefObject<THREE.Group>) => (
    <group ref={ref}>
      {idx.map((i) => seg(top, i, "#7A33A6", side, true))}
      {idx.map((i) => seg(bot, i, "#4F7E91", side, false))}
      {idx.map((i) => (isLeft(i) === side) && (
        <group key={`b${i}`}>
          {/* base-pair rung, hidden where the duplex has melted */}
          {!inGuide(i) && <Line points={[top[i], bot[i]]} color={inPam(i) ? "#f5c542" : "#4a4a5a"} lineWidth={1.2} />}
          {/* non-target (top) strand base — only outside the guide region */}
          {!inGuide(i) && <Sphere pos={top[i]} base={seq[i]} hi={false} pam={inPam(i)} />}
          {/* target (bottom) strand base — always shown; gRNA pairs to it */}
          <Sphere pos={bot[i]} base={DNA_COMPLEMENT[seq[i]] || "N"} hi={inGuide(i)} pam={inPam(i)} />
        </group>
      ))}
    </group>
  );

  return (
    <group>
      {half(true, leftG)}
      {half(false, rightG)}

      {/* R-loop displaced non-target strand (guide region) — lifted, then excised */}
      <group ref={rloopTop}>
        {seq.split("").map((b, i) => inGuide(i) ? (
          <mesh key={`rl${i}`} position={top[i]} scale={1.1}>
            <sphereGeometry args={[0.32, 16, 16]} />
            <meshStandardMaterial
              ref={(m) => { if (m) rloopMats.current[i] = m; }}
              color={DNA_COLORS[b] || "#9ca3af"} emissive={DNA_COLORS[b] || "#000"}
              emissiveIntensity={0.3} transparent opacity={0.9} roughness={0.4} />
          </mesh>
        ) : null)}
      </group>

      {/* gRNA that base-pairs with the target strand, then slots into the gap */}
      <group ref={grnaPair} visible={false}>
        {grnaPts.map((p0, k) => {
          const gi = gStart + k;
          const gb = (guideSeq[k] || "N").toUpperCase();
          return (
            <group key={`g${k}`}>
              <Line points={[bot[gi], p0]} color="#c49ae0" lineWidth={1.4} />
              <mesh position={p0} scale={1.0}>
                <sphereGeometry args={[0.3, 16, 16]} />
                <meshStandardMaterial
                  ref={(m) => { if (m) grnaMats.current[k] = m; }}
                  color={RNA_COLORS[gb] || "#c49ae0"}
                  emissive={RNA_COLORS[gb] || "#c49ae0"}
                  emissiveIntensity={0.35}
                  transparent
                  opacity={0.15}
                  roughness={0.35}
                />
              </mesh>
            </group>
          );
        })}
      </group>
      <pointLight ref={editGlow} position={[dockX, 0, 2]} color="#c49ae0" intensity={0} distance={14} />

      {/* Cas9 ribonucleoprotein — stylized bilobed translucent blob around the dock */}
      <group ref={rnp} visible={false}>
        <group ref={lobeGroup}>
          {/* recognition (REC) lobe — larger, purple */}
          <mesh position={[0, 1.9, 0]} scale={[2.6, 1.7, 2.2]}>
            <sphereGeometry args={[1, 32, 32]} />
            <meshStandardMaterial color="#7A33A6" transparent opacity={0.34} roughness={0.6} metalness={0.1} />
          </mesh>
          {/* nuclease (NUC) lobe — teal, cradles the DNA from below */}
          <mesh position={[0, -1.9, 0]} scale={[2.4, 1.6, 2.2]}>
            <sphereGeometry args={[1, 32, 32]} />
            <meshStandardMaterial color="#4F7E91" transparent opacity={0.34} roughness={0.6} metalness={0.1} />
          </mesh>
          {/* HNH nuclease domain (cuts target strand) */}
          <mesh position={[0.2, -0.6, 1.0]}>
            <sphereGeometry args={[0.6, 20, 20]} />
            <meshStandardMaterial ref={hnhMat} color="#e0567a" emissive="#e0567a" emissiveIntensity={0.2} roughness={0.4} />
            <Html center distanceFactor={16}><div style={tagStyle}>HNH</div></Html>
          </mesh>
          {/* RuvC nuclease domain (cuts non-target strand) */}
          <mesh position={[-0.2, -1.4, -1.0]}>
            <sphereGeometry args={[0.6, 20, 20]} />
            <meshStandardMaterial ref={ruvcMat} color="#f0a24a" emissive="#f0a24a" emissiveIntensity={0.2} roughness={0.4} />
            <Html center distanceFactor={16}><div style={tagStyle}>RuvC</div></Html>
          </mesh>
        </group>
        <Html position={[0, 3.6, 0]} center distanceFactor={22}>
          <div style={{ ...tagStyle, background: "#2C1A3D", fontSize: 13 }}>Cas9 · gRNA</div>
        </Html>
      </group>

      {/* cleavage spark */}
      <mesh ref={spark} visible={false}>
        <sphereGeometry args={[0.5, 16, 16]} />
        <meshStandardMaterial ref={sparkMat} color="#fff2b0" emissive="#ffd24a" emissiveIntensity={0} transparent opacity={0.9} />
      </mesh>
      <pointLight ref={sparkLight} position={[dockX, 0, 2]} color="#ffd24a" intensity={0} distance={12} />
    </group>
  );
});

const tagStyle: CSSProperties = {
  background: "#4F7E91", color: "#fff", padding: "1px 7px", borderRadius: 7,
  fontSize: 11, fontWeight: 700, whiteSpace: "nowrap",
};

// =============================================================================
export function CrisprSimulation3D({
  win, guideSeq, guideId,
}: {
  win: DnaWindow;
  guideSeq: string;
  guideId?: string;
}) {
  const control = useRef<Control>({ playing: true, speed: 1, seek: 0, loop: true });
  const [progress, setProgress] = useState(0);
  const [playing, setPlaying] = useState(true);
  const [speed, setSpeed] = useState(1);
  const [loop, setLoop] = useState(true);
  const wrap = useRef<HTMLDivElement>(null);
  const orbit = useRef<any>(null);
  const stage = stageForProgress(progress);

  // restart whenever the guide changes
  useEffect(() => {
    control.current.seek = 0;
    control.current.playing = true;
    setPlaying(true);
    setProgress(0);
  }, [guideSeq]);

  const setPlay = (v: boolean) => { control.current.playing = v; setPlaying(v); };
  const setSpd = (v: number) => { control.current.speed = v; setSpeed(v); };
  const setLp = (v: boolean) => { control.current.loop = v; setLoop(v); };
  const seekTo = (v: number) => { control.current.seek = v; setProgress(v); };
  const jumpStage = (i: number) => { setPlay(false); seekTo(STAGES[i].start + 0.001); };
  const restart = () => { seekTo(0); setPlay(true); };

  return (
    <div className="flex flex-col gap-3">
      <div ref={wrap} className="relative rounded-xl overflow-hidden bg-[#0e0a16] h-[460px]">
        <Canvas camera={{ position: [0, 1.5, 16], fov: 50 }} gl={{ antialias: true }}>
          <ambientLight intensity={0.75} />
          <directionalLight position={[6, 8, 6]} intensity={1.1} />
          <directionalLight position={[-6, -4, -6]} intensity={0.4} color="#c49ae0" />
          <Scene win={win} guideSeq={guideSeq} control={control} onFrame={setProgress} />
          <OrbitControls ref={orbit} enablePan enableDamping />
        </Canvas>

        {/* stage chip */}
        <div className="absolute top-2 left-2 flex items-center gap-2">
          <span className="rounded-lg bg-brand/85 text-white text-xs font-bold px-2.5 py-1 backdrop-blur">
            {STAGES[stage].label}
          </span>
          {guideId && <span className="rounded-lg bg-white/10 text-white/90 text-xs font-semibold px-2 py-1 backdrop-blur">{guideId}</span>}
        </div>

        <div className="absolute top-2 right-2 flex gap-1">
          <button title="Reset camera" onClick={() => orbit.current?.reset()} className="w-8 h-8 rounded-lg bg-white/10 hover:bg-white/20 text-white text-sm backdrop-blur">⌖</button>
          <button title="Fullscreen" onClick={() => wrap.current?.requestFullscreen?.()} className="w-8 h-8 rounded-lg bg-white/10 hover:bg-white/20 text-white text-sm backdrop-blur">⤢</button>
        </div>

        {/* legend */}
        <div className="absolute bottom-2 left-2 flex flex-wrap gap-2 text-[10px] text-white/80">
          <span className="flex items-center gap-1"><span className="w-2.5 h-2.5 rounded-full inline-block" style={{ background: "#f5c542" }} />PAM</span>
          <span className="flex items-center gap-1"><span className="w-2.5 h-2.5 rounded-full inline-block" style={{ background: "#c49ae0" }} />gRNA / edit</span>
          <span className="flex items-center gap-1"><span className="w-2.5 h-2.5 rounded-full inline-block" style={{ background: "#e0567a" }} />HNH</span>
          <span className="flex items-center gap-1"><span className="w-2.5 h-2.5 rounded-full inline-block" style={{ background: "#f0a24a" }} />RuvC</span>
        </div>
      </div>

      {/* transport controls */}
      <div className="flex items-center gap-3 flex-wrap">
        <button onClick={() => setPlay(!playing)} className="btn-ghost text-sm w-24">{playing ? "⏸ Pause" : "▶ Play"}</button>
        <button onClick={restart} className="btn-ghost text-sm">↻ Restart</button>
        <input
          type="range" min={0} max={1} step={0.001} value={progress}
          onChange={(e) => { setPlay(false); seekTo(parseFloat(e.target.value)); }}
          className="flex-1 min-w-[160px] accent-brand"
        />
        <div className="flex items-center gap-1 text-xs text-muted">
          <span className="font-semibold">Speed</span>
          {[0.5, 1, 2].map((s) => (
            <button key={s} onClick={() => setSpd(s)}
              className={`px-2 py-0.5 rounded font-bold ${speed === s ? "bg-brand text-white" : "bg-bg text-muted"}`}>{s}×</button>
          ))}
        </div>
        <label className="flex items-center gap-1 text-xs text-muted font-semibold">
          <input type="checkbox" checked={loop} onChange={(e) => setLp(e.target.checked)} className="accent-brand" />Loop
        </label>
      </div>

      {/* jump-to-stage row (free jumps, not a forced sequence) */}
      <div className="flex gap-1 flex-wrap">
        {STAGES.map((s, i) => (
          <button key={s.key} onClick={() => jumpStage(i)}
            className={`px-2.5 py-1 rounded-lg text-xs font-bold transition ${i === stage ? "bg-brand text-white" : "bg-bg text-muted hover:bg-brand/10"}`}>
            {s.label}
          </button>
        ))}
      </div>
      <div className="rounded-xl bg-bg border border-border p-3 text-sm">
        <b className="text-brand">{STAGES[stage].label.split("·").slice(1).join("·").trim()}</b>
        <span className="text-ink"> — {STAGES[stage].desc}</span>
      </div>
      <div className="text-[11px] text-muted">
        Illustrative animation of the canonical Cas9 mechanism for this guide (scan → PAM → R-loop → cleavage → double-strand break → edit).
        Shapes are stylized for clarity and are not a structural or physical simulation; the final "edit" step is a simplified depiction of repair.
      </div>
    </div>
  );
}
