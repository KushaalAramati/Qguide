"use client";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell,
  PieChart, Pie, RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, Radar,
} from "recharts";
import { useThemeColors, ThemeColors } from "@/lib/themeColors";

/**
 * Charts read their palette from the live theme tokens, so light ("Stone") and
 * dark ("Charcoal") stay in step with the rest of the interface.
 *
 * Colour still carries only the four system meanings: accent for the headline
 * series, series for neutral quantity, warn for provisional or medium, bad for
 * high risk. Ordinal categories use a value ramp, not a rainbow.
 */
const axis = (c: ThemeColors) => ({ fontSize: 10, fill: c.muted });

function chartTooltip(c: ThemeColors) {
  return {
    contentStyle: {
      background: c.surface,
      border: `1px solid ${c.line}`,
      borderRadius: 0,
      fontSize: 11,
      color: c.ink,
    },
    itemStyle: { color: c.ink },
    labelStyle: { color: c.muted },
    cursor: { fill: c.track, fillOpacity: 0.35 },
  };
}

export function OutcomePie({ outcome }: { outcome: any }) {
  const c = useThemeColors();
  const data = [
    { name: "Frameshift", value: outcome.frameshift_prob, fill: c.accent },
    { name: "In-frame indel", value: outcome.in_frame_indel_prob, fill: c.warn },
    { name: "No edit", value: outcome.no_edit_prob, fill: c.track },
  ];
  return (
    <ResponsiveContainer width="100%" height={240}>
      <PieChart>
        <Pie
          data={data} dataKey="value" nameKey="name" innerRadius={52} outerRadius={88}
          stroke={c.surface} strokeWidth={2}
          label={(d: any) => `${(d.value * 100).toFixed(0)}%`}
        >
          {data.map((d, i) => <Cell key={i} fill={d.fill} />)}
        </Pie>
        <Tooltip formatter={(v: any) => `${(v * 100).toFixed(0)}%`} {...chartTooltip(c)} />
      </PieChart>
    </ResponsiveContainer>
  );
}

export function OutcomeBars({ outcome }: { outcome: any }) {
  const c = useThemeColors();
  const data = [
    { name: "Knockout", value: outcome.knockout_prob },
    { name: "Frameshift", value: outcome.frameshift_prob },
    { name: "Exon disrupt", value: outcome.exon_disruption_prob },
    { name: "In-frame", value: outcome.in_frame_indel_prob },
    { name: "Functional", value: outcome.functional_disruption_score },
  ];
  return (
    <ResponsiveContainer width="100%" height={240}>
      <BarChart data={data} margin={{ top: 8, right: 8, left: -22, bottom: 0 }}>
        <XAxis dataKey="name" tick={axis(c)} stroke={c.line} tickLine={false} />
        <YAxis domain={[0, 1]} tick={axis(c)} stroke={c.line} tickLine={false} />
        <Tooltip formatter={(v: any) => `${(v * 100).toFixed(0)}%`} {...chartTooltip(c)} />
        <Bar dataKey="value" radius={0} fill={c.series}>
          {data.map((_, i) => <Cell key={i} fill={i === 0 ? c.accent : c.series} />)}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

export function GuideRadar({ guide }: { guide: any }) {
  const c = useThemeColors();
  const data = [
    { k: "On-target", v: guide.scores.on_target },
    { k: "Knockout", v: guide.outcome.knockout_prob },
    { k: "Functional", v: guide.outcome.functional_disruption_score },
    { k: "Off-tgt safety", v: 1 - guide.off_target.risk_score },
    { k: "GC", v: guide.scores.gc_content },
    { k: "Context", v: Math.min(1, guide.context.multiplier) },
  ];
  return (
    <ResponsiveContainer width="100%" height={240}>
      <RadarChart data={data} outerRadius={86}>
        <PolarGrid stroke={c.line} />
        <PolarAngleAxis dataKey="k" tick={{ fontSize: 9.5, fill: c.muted }} />
        <PolarRadiusAxis domain={[0, 1]} tick={false} axisLine={false} />
        <Radar dataKey="v" stroke={c.accent} fill={c.accent} fillOpacity={0.28} />
      </RadarChart>
    </ResponsiveContainer>
  );
}

export function CompareBars({ guides }: { guides: any[] }) {
  const c = useThemeColors();
  const data = guides.map((g) => ({
    name: g.guide_id.replace("gRNA_", ""),
    Final: g.final_score,
    Knockout: g.outcome.knockout_prob,
    "Off-target": g.off_target.risk_score,
  }));
  return (
    <ResponsiveContainer width="100%" height={280}>
      <BarChart data={data} margin={{ top: 8, right: 8, left: -22, bottom: 0 }}>
        <XAxis dataKey="name" tick={axis(c)} stroke={c.line} tickLine={false} />
        <YAxis domain={[0, 1]} tick={axis(c)} stroke={c.line} tickLine={false} />
        <Tooltip {...chartTooltip(c)} />
        {/* accent = the score you act on, series = context, warn = the risk term */}
        <Bar dataKey="Final" fill={c.accent} radius={0} />
        <Bar dataKey="Knockout" fill={c.series} radius={0} />
        <Bar dataKey="Off-target" fill={c.warn} radius={0} />
      </BarChart>
    </ResponsiveContainer>
  );
}
