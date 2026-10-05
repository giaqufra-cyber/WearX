import { colors, fonts, minTouchTarget, radii } from "@wearx/design-tokens";
import { voteMood } from "@wearx/design-tokens";
import { useRef, useState } from "react";
import { type LayoutChangeEvent, PanResponder, Pressable, StyleSheet, Text, View } from "react-native";

const THUMB = 28;

export function clampScore(value: number): number {
  return Math.min(100, Math.max(1, Math.round(value)));
}

/** Da posizione sul binario (0..width) a voto 1..100. */
export function scoreAt(x: number, width: number): number {
  if (width <= 0) return 1;
  return clampScore(1 + (Math.min(Math.max(x, 0), width) / width) * 99);
}

type Props = { value: number; onChange: (value: number) => void; color: string; label: string };

/**
 * Slider del voto 1-100. Si trascina (o si tocca un punto del binario); con VoiceOver/TalkBack
 * si regola con i gesti su/giù; i pulsanti − e + aggiustano di un punto.
 */
export function VoteSlider({ value, onChange, color, label }: Props) {
  const [width, setWidth] = useState(0);
  const track = useRef<View>(null);
  const origin = useRef(0);
  const widthRef = useRef(0);
  const onChangeRef = useRef(onChange);
  onChangeRef.current = onChange;

  const responder = useRef(
    PanResponder.create({
      onStartShouldSetPanResponder: () => true,
      onMoveShouldSetPanResponder: () => true,
      // Il trascinamento orizzontale del voto non deve far scorrere il feed.
      onPanResponderTerminationRequest: () => false,
      onPanResponderGrant: (event) => {
        const { pageX, locationX } = event.nativeEvent;
        origin.current = pageX - locationX;
        track.current?.measure?.((_x, _y, _w, _h, px) => {
          if (typeof px === "number" && !Number.isNaN(px)) origin.current = px;
        });
        onChangeRef.current(scoreAt(locationX, widthRef.current));
      },
      onPanResponderMove: (_event, gesture) => {
        onChangeRef.current(scoreAt(gesture.moveX - origin.current, widthRef.current));
      },
    }),
  ).current;

  const onLayout = (event: LayoutChangeEvent) => {
    widthRef.current = event.nativeEvent.layout.width;
    setWidth(event.nativeEvent.layout.width);
  };
  const fraction = (value - 1) / 99;

  return (
    <View style={styles.row}>
      <Pressable role="button" aria-label="Un punto in meno" onPress={() => onChange(clampScore(value - 1))} style={styles.step} hitSlop={6}>
        <Text style={styles.stepText}>−</Text>
      </Pressable>
      <View
        ref={track}
        onLayout={onLayout}
        style={styles.touch}
        accessible
        role="slider"
        aria-label={label}
        accessibilityValue={{ min: 1, max: 100, now: value, text: `${value}, ${voteMood(value)}` }}
        accessibilityActions={[{ name: "increment" }, { name: "decrement" }]}
        onAccessibilityAction={(event) => {
          if (event.nativeEvent.actionName === "increment") onChange(clampScore(value + 1));
          if (event.nativeEvent.actionName === "decrement") onChange(clampScore(value - 1));
        }}
        {...responder.panHandlers}
      >
        <View style={styles.track} pointerEvents="none">
          <View style={[styles.fill, { width: `${fraction * 100}%`, backgroundColor: color }]} />
        </View>
        <View
          pointerEvents="none"
          style={[styles.thumb, { left: Math.max(0, fraction * width - THUMB / 2), borderColor: color }]}
        />
      </View>
      <Pressable role="button" aria-label="Un punto in più" onPress={() => onChange(clampScore(value + 1))} style={styles.step} hitSlop={6}>
        <Text style={styles.stepText}>+</Text>
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: "row", alignItems: "center", gap: 6, flex: 1, minWidth: 0 },
  touch: { flex: 1, height: minTouchTarget, justifyContent: "center" },
  track: { height: 6, borderRadius: 3, backgroundColor: "#26262A", overflow: "hidden" },
  fill: { height: 6, borderRadius: 3 },
  thumb: {
    position: "absolute",
    top: (minTouchTarget - THUMB) / 2,
    width: THUMB,
    height: THUMB,
    borderRadius: THUMB / 2,
    backgroundColor: colors.inverse,
    borderWidth: 3,
  },
  step: {
    width: 32,
    height: 32,
    borderRadius: radii.pill,
    borderWidth: 1,
    borderColor: colors.border,
    alignItems: "center",
    justifyContent: "center",
  },
  stepText: { fontFamily: fonts.uiBold, fontSize: 18, lineHeight: 20, color: colors.textSecondary },
});
