"use client";

import { Bar, BarChart, CartesianGrid, Cell, LabelList, Line, LineChart, ReferenceLine, XAxis, YAxis } from "recharts";
import { ChartConfig, ChartContainer, ChartLegend, ChartLegendContent, ChartTooltip, ChartTooltipContent } from "@/components/ui/chart";
import { DTE_CODES, DteResult } from "@/lib/api";

const config: ChartConfig = {
  P: { label: "P", color: "var(--blue)" },
  T: { label: "T", color: "var(--red)" },
  SM: { label: "SM", color: "var(--olive)" },
  ET: { label: "ET", color: "var(--lava)" },
};

/** The four standardised anomaly series on one axis (unitless), smoothed lines with a legend. */
export function AnomalyChart({ dte, className = "h-44 w-full" }: { dte: DteResult; className?: string }) {
  // Yearly means of the monthly standardised anomalies: 24 readable points instead of 288 noisy ones.
  const byYear = new Map<string, { n: number; P: number; T: number; SM: number; ET: number }>();
  for (const a of dte.joint.standardized_anomalies) {
    const y = a.date.slice(0, 4);
    const acc = byYear.get(y) ?? { n: 0, P: 0, T: 0, SM: 0, ET: 0 };
    acc.n += 1;
    for (const c of DTE_CODES) acc[c] += a[c] ?? 0;
    byYear.set(y, acc);
  }
  const data = [...byYear.entries()].map(([date, a]) => ({
    date,
    P: Number((a.P / a.n).toFixed(2)),
    T: Number((a.T / a.n).toFixed(2)),
    SM: Number((a.SM / a.n).toFixed(2)),
    ET: Number((a.ET / a.n).toFixed(2)),
  }));
  return (
    <ChartContainer config={config} className={className}>
      <LineChart data={data} margin={{ top: 8, right: 6, left: 6, bottom: 0 }}>
        <CartesianGrid vertical={false} strokeDasharray="3 4" stroke="var(--border)" />
        <XAxis dataKey="date" tickLine={false} axisLine={false} tickMargin={6} minTickGap={28} interval="preserveStartEnd" />
        <YAxis hide domain={["auto", "auto"]} />
        <ReferenceLine y={0} stroke="var(--muted-foreground)" strokeDasharray="4 4" />
        <ChartTooltip content={<ChartTooltipContent indicator="line" />} />
        {DTE_CODES.map((c) => (
          <Line key={c} dataKey={c} type="monotone" stroke={`var(--color-${c})`} strokeWidth={2} dot={false} isAnimationActive animationDuration={1200} />
        ))}
        <ChartLegend content={<ChartLegendContent />} />
      </LineChart>
    </ChartContainer>
  );
}

const pairConfig: ChartConfig = { r: { label: "r", color: "var(--blue)" } };

/** Pearson r of each pair as horizontal bars: blue = move together, red = move opposite. */
export function CorrelationBars({ dte, className = "h-36 w-full" }: { dte: DteResult; className?: string }) {
  const data = dte.joint.pairs_list
    .filter((p) => p.r !== null)
    .map((p) => ({ pair: p.pair.replace("-", " · "), r: Number((p.r as number).toFixed(2)) }));
  return (
    <ChartContainer config={pairConfig} className={className}>
      <BarChart data={data} layout="vertical" margin={{ top: 4, right: 36, left: 8, bottom: 4 }}>
        <CartesianGrid horizontal={false} strokeDasharray="3 4" stroke="var(--border)" />
        <XAxis type="number" domain={[-1, 1]} tickLine={false} axisLine={false} ticks={[-1, -0.5, 0, 0.5, 1]} />
        <YAxis type="category" dataKey="pair" tickLine={false} axisLine={false} width={64} />
        <ReferenceLine x={0} stroke="var(--muted-foreground)" />
        <ChartTooltip cursor={false} content={<ChartTooltipContent hideLabel />} />
        <Bar dataKey="r" radius={999} barSize={16} isAnimationActive animationDuration={1000}>
          {data.map((d) => (
            <Cell key={d.pair} fill={d.r >= 0 ? "var(--blue)" : "var(--red)"} />
          ))}
          <LabelList dataKey="r" position="right" className="fill-foreground text-xs" formatter={(v: unknown) => (typeof v === "number" ? (v > 0 ? `+${v}` : `${v}`) : "")} />
        </Bar>
      </BarChart>
    </ChartContainer>
  );
}
