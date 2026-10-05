"use client";

/* eslint-disable @next/next/no-img-element -- URL firmati e temporanei dell'archivio: niente ottimizzazione */
import type { MediaOut } from "@/lib/types";

/** Variante più piccola che basta per la larghezza richiesta. */
export function pickVariant(variants: Record<string, string>, width: number): string | undefined {
  const sizes = Object.keys(variants)
    .map(Number)
    .sort((a, b) => a - b);
  const size = sizes.find((s) => s >= width) ?? sizes.at(-1);
  return size === undefined ? undefined : variants[String(size)];
}

/** Foto sfocata finché il moderatore non sceglie di guardarla (sez. 14.3). */
export function Photo({
  media,
  revealed,
  onReveal,
  warning,
}: {
  media: Pick<MediaOut, "urls">;
  revealed: boolean;
  onReveal: () => void;
  warning?: string;
}) {
  const src = pickVariant(media.urls.variants as Record<string, string>, 640);
  return (
    <div className={`photo${revealed ? "" : " blurred"}`}>
      {src ? <img src={src} alt={revealed ? "Foto del fit" : "Foto sfocata"} referrerPolicy="no-referrer" /> : null}
      {revealed ? null : (
        <div className="reveal">
          {warning ? <strong style={{ color: "var(--warning)" }}>{warning}</strong> : null}
          <button className="btn inverse" type="button" onClick={onReveal}>
            Mostra <kbd>V</kbd>
          </button>
        </div>
      )}
    </div>
  );
}
