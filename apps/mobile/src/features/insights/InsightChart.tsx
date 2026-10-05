import type { InsightPoint } from "@wearx/api-types";
import { colors, fonts, spacing } from "@wearx/design-tokens";
import { useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import Svg, { Line, Path, Rect } from "react-native-svg";

import { formatInt, shortDate, weekdayDate } from "@/features/insights/api";

type Props = {
  points: InsightPoint[];
  metric: "impressions" | "votes";
  bucket: "day" | "week";
  width: number;
};

const HEIGHT = 140;
const TOP = 18;
const MAX_BAR = 24;
const GAP = 2;
const LOW_STUB = 6;

/** Colonna con la cima arrotondata (4px) e la base dritta sulla linea dello zero. */
function columnPath(x: number, y: number, w: number, h: number): string {
  const r = Math.min(4, w / 2, h);
  const base = y + h;
  return `M${x},${base} L${x},${y + r} Q${x},${y} ${x + r},${y} L${x + w - r},${y} Q${x + w},${y} ${x + w},${y + r} L${x + w},${base} Z`;
}

/**
 * Colonne giornaliere (o settimanali) di una sola misura. I giorni "meno di 5" sono un contorno
 * vuoto basso: non un colore diverso, una forma diversa. Toccando una colonna si legge il valore.
 */
export function InsightChart({ points, metric, bucket, width }: Props) {
  const [selected, setSelected] = useState<number | null>(null);
  const values = points.map((p) => p[metric]);
  const max = Math.max(5, ...values.map((v) => v ?? 0));
  const slot = width / Math.max(points.length, 1);
  const bar = Math.max(2, Math.min(MAX_BAR, slot - GAP));
  const plot = HEIGHT - TOP;
  const unit = metric === "impressions" ? "visualizzazioni" : "voti";
  const index = selected ?? points.length - 1;
  const current = points[index];
  const label = (p: InsightPoint) => (bucket === "week" ? `settimana del ${shortDate(p.start)}` : weekdayDate(p.start));
  const valueText = (v: number | null) => (v === null ? `meno di 5 ${unit}` : `${formatInt(v)} ${unit}`);

  return (
    <View>
      <Text style={styles.readout} aria-live="polite">
        {current ? `${label(current)} · ${valueText(current[metric])}` : ""}
      </Text>
      <View style={{ width, height: HEIGHT }}>
        <Text style={styles.max}>{formatInt(max)}</Text>
        <Svg width={width} height={HEIGHT}>
          <Line x1={0} x2={width} y1={TOP} y2={TOP} stroke={colors.divider} strokeWidth={1} />
          <Line x1={0} x2={width} y1={HEIGHT - 0.5} y2={HEIGHT - 0.5} stroke={colors.border} strokeWidth={1} />
          {values.map((v, i) => {
            const x = i * slot + (slot - bar) / 2;
            const active = i === index;
            if (v === null) {
              return (
                <Rect
                  key={i}
                  x={x + 0.5}
                  y={HEIGHT - LOW_STUB}
                  width={bar - 1}
                  height={LOW_STUB - 1}
                  rx={2}
                  fill="none"
                  stroke={active ? colors.text : colors.textSecondary}
                  strokeWidth={1}
                />
              );
            }
            if (v === 0) return null;
            const h = Math.max(2, (v / max) * plot);
            return (
              <Path
                key={i}
                d={columnPath(x, HEIGHT - h, bar, h)}
                fill={colors.accent}
                opacity={selected === null || active ? 1 : 0.45}
              />
            );
          })}
        </Svg>
        {/* Aree toccabili più larghe delle colonne. */}
        <View style={StyleSheet.absoluteFill}>
          <View style={styles.hitRow}>
            {points.map((p, i) => (
              <Pressable
                key={p.start}
                style={{ width: slot, height: HEIGHT }}
                onPress={() => setSelected(i)}
                role="button"
                aria-label={`${label(p)}: ${valueText(p[metric])}`}
              />
            ))}
          </View>
        </View>
      </View>
      <View style={styles.axis}>
        <Text style={styles.axisText}>{points[0] ? shortDate(points[0].start) : ""}</Text>
        <Text style={styles.axisText}>{points.at(-1) ? shortDate(points.at(-1)!.start) : ""}</Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  readout: { fontFamily: fonts.uiSemiBold, fontSize: 13, color: colors.text, marginBottom: spacing[3] },
  hitRow: { flexDirection: "row" },
  max: {
    position: "absolute",
    right: 0,
    top: 0,
    fontFamily: fonts.mono,
    fontSize: 10,
    color: colors.textTertiary,
  },
  axis: { flexDirection: "row", justifyContent: "space-between", marginTop: 6 },
  axisText: { fontFamily: fonts.mono, fontSize: 10, letterSpacing: 0.5, color: colors.textTertiary },
});
