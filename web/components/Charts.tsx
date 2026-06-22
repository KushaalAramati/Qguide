"use client";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell,
  PieChart, Pie, RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, Radar,
} from "recharts";

const PURPLE = "#7A33A6";
const COLORS = ["#7A33A6", "#A569BD", "#C49AE0", "#C9892F", "#C2566B"];

export function OutcomePie({ outcome }: { outcome: any }) {
  const data = [
    { name: "Frameshift", value: outcome.frameshift_prob },
    { name: "In-frame indel", value: outcome.in_frame_indel_prob },
    { name: "No edit", value: outcome.no_edit_prob },
  ];
  return (
    <ResponsiveContainer width="100%" height={260}>
      <PieChart>
        <Pie data={data} dataKey="value" nameKey="name" innerRadius={50} outerRadius={90} label={(d: any) => `${(d.value * 100).toFixed(0)}%`}>
          {data.map((_, i) => <Cell key={i} fill={COLORS[i]} />)}
        </Pie>
        <Tooltip formatter={(v: any) => `${(v * 100).toFixed(0)}%`} />
      </PieChart>
    </ResponsiveContainer>
  );
}

export function OutcomeBars({ outcome }: { outcome: any }) {
  const data = [
    { name: "Knockout", value: outcome.knockout_prob },
    { name: "Frameshift", value: outcome.frameshift_prob },
    { name: "Exon disrupt", value: outcome.exon_disruption_prob },
    { name: "In-frame", value: outcome.in_frame_indel_prob },
    { name: "Functional", value: outcome.functional_disruption_score },
  ];
  return (
    <ResponsiveContainer width="100%" height={260}>
      <BarChart data={data} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
        <XAxis dataKey="name" tick={{ fontSize: 11 }} />
        <YAxis domain={[0, 1]} tick={{ fontSize: 11 }} />
        <Tooltip formatter={(v: any) => `${(v * 100).toFixed(0)}%`} />
        <Bar dataKey="value" radius={[6, 6, 0, 0]}>
          {data.map((_, i) => <Cell key={i} fill={PURPLE} />)}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

export function GuideRadar({ guide }: { guide: any }) {
  const data = [
    { k: "On-target", v: guide.scores.on_target },
    { k: "Knockout", v: guide.outcome.knockout_prob },
    { k: "Functional", v: guide.outcome.functional_disruption_score },
    { k: "Off-tgt safety", v: 1 - guide.off_target.risk_score },
    { k: "GC", v: guide.scores.gc_content },
    { k: "Context", v: Math.min(1, guide.context.multiplier) },
  ];
  return (
    <ResponsiveContainer width="100%" height={260}>
      <RadarChart data={data} outerRadius={90}>
        <PolarGrid />
        <PolarAngleAxis dataKey="k" tick={{ fontSize: 10 }} />
        <PolarRadiusAxis domain={[0, 1]} tick={false} axisLine={false} />
        <Radar dataKey="v" stroke={PURPLE} fill={PURPLE} fillOpacity={0.4} />
      </RadarChart>
    </ResponsiveContainer>
  );
}

export function CompareBars({ guides }: { guides: any[] }) {
  const data = guides.map((g) => ({
    name: g.guide_id.replace("gRNA_", ""),
    Final: g.final_score,
    Knockout: g.outcome.knockout_prob,
    "Off-target": g.off_target.risk_score,
  }));
  return (
    <ResponsiveContainer width="100%" height={300}>
      <BarChart data={data} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
        <XAxis dataKey="name" tick={{ fontSize: 11 }} />
        <YAxis domain={[0, 1]} tick={{ fontSize: 11 }} />
        <Tooltip />
        <Bar dataKey="Final" fill={COLORS[0]} radius={[4, 4, 0, 0]} />
        <Bar dataKey="Knockout" fill={COLORS[1]} radius={[4, 4, 0, 0]} />
        <Bar dataKey="Off-target" fill={COLORS[3]} radius={[4, 4, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}
