import type { MediaUpload } from "@wearx/api-types";

import { draftHasContent, useNewPostDraft } from "@/features/create/draft";
import {
  buildPostRequest,
  canPublish,
  formatPrice,
  type ItemDraft,
  itemErrors,
  linkProblem,
  parsePrice,
} from "@/features/create/form";
import { RETRY_DELAYS_MS, type UploadDeps, UploadHttpError, type UploadUpdate, uploadPhoto } from "@/features/create/uploader";
import { ApiError } from "@/lib/api";

jest.mock("expo-crypto", () => ({ randomUUID: () => Math.random().toString(36).slice(2) }));

const item = (patch: Partial<ItemDraft> = {}): ItemDraft => ({ key: "k", brand: "", name: "", price: "", link: "", ...patch });

describe("prezzi", () => {
  test.each([
    ["", null],
    ["89", 8900],
    ["89,9", 8990],
    ["89,90", 8990],
    ["89.90", 8990],
    ["1.250,50", 125050],
    ["1,250.50", 125050],
    ["1250", 125000],
    ["€ 1.250", 125000],
    ["0", 0],
    ["12,345", 1234500], // tre cifre dopo il separatore: sono migliaia
  ])("%s -> %s", (raw, cents) => {
    expect(parsePrice(raw)).toBe(cents);
  });

  test.each(["abc", "12,3456", "-5", "1,2,3", "100000,01", "9.99.9"])("%s non è un prezzo", (raw) => {
    expect(parsePrice(raw)).toBeNaN();
  });

  test("formato italiano", () => {
    expect(formatPrice(125050)).toBe("1.250,50 €");
    expect(formatPrice(8900)).toBe("89 €");
  });
});

describe("link", () => {
  test.each(["", "https://www.armani.com/it-it/", "https://shop.example.com:443/p?x=1"])("%s va bene", (url) => {
    expect(linkProblem(url)).toBeNull();
  });
  test.each([
    ["http://armani.com", "Accettiamo solo link https."],
    ["armani.com", "Accettiamo solo link https."],
    ["https://armani .com", "Il link non può contenere spazi."],
    ["https://user@armani.com", "Il link non è valido."],
    ["https://192.168.1.1/", "Il link non è valido."],
    ["https://localhost/", "Il link non è valido."],
  ])("%s -> %s", (url, message) => {
    expect(linkProblem(url)).toBe(message);
  });
});

describe("capi e pubblicazione", () => {
  test("capo vuoto ignorato, capo a metà segnalato", () => {
    expect(itemErrors(item())).toEqual({});
    expect(itemErrors(item({ price: "50" }))).toEqual({ brand: "Manca il brand.", name: "Manca il capo." });
    expect(itemErrors(item({ brand: "Armani", name: "Smoking", price: "x" })).price).toContain("Prezzo");
  });

  const ready = { status: "ready" as const, uploadId: "u1" };
  const base = { photos: [ready], style: "gala", items: [item()], caption: "" };

  test("cosa manca, in ordine", () => {
    expect(canPublish({ ...base, photos: [] })).toEqual({ ok: false, reason: "Scegli almeno una foto." });
    expect(canPublish({ ...base, photos: [ready, { status: "uploading" }] })).toEqual({
      ok: false,
      reason: "Carichiamo le foto: 1 di 2.",
    });
    expect(canPublish({ ...base, photos: [{ status: "error" }] }).ok).toBe(false);
    expect(canPublish({ ...base, photos: [{ status: "rejected" }] })).toEqual({
      ok: false,
      reason: "Togli le foto che non possiamo pubblicare.",
    });
    expect(canPublish({ ...base, style: null })).toEqual({ ok: false, reason: "Scegli lo stile del fit." });
    expect(canPublish({ ...base, items: [item({ brand: "X" })] })).toEqual({ ok: false, reason: "Controlla i capi." });
    expect(canPublish(base)).toEqual({ ok: true });
  });

  test("richiesta per il server", () => {
    expect(
      buildPostRequest({
        ...base,
        photos: [ready, { status: "ready", uploadId: "u2" }],
        caption: "  Serata  ",
        items: [item({ brand: " Armani ", name: "Smoking", price: "1.250,50", link: " https://armani.com " }), item()],
      }),
    ).toEqual({
      style: "gala",
      caption: "Serata",
      media: ["u1", "u2"],
      items: [{ brand: "Armani", name: "Smoking", price_cents: 125050, currency: "EUR", url: "https://armani.com" }],
    });
  });
});

describe("bozza", () => {
  beforeEach(() => useNewPostDraft.getState().reset());

  test("massimo 10 foto, ordine modificabile, capi mai a zero", () => {
    const d = () => useNewPostDraft.getState();
    d().addPhotos(Array.from({ length: 12 }, (_, i) => ({ uri: `f${i}`, width: 100, height: 100 })));
    expect(d().photos).toHaveLength(10);
    expect(d().photos[0]!.status).toBe("queued");
    const [a, b] = d().photos;
    d().movePhoto(b!.localId, -1);
    expect(d().photos[0]!.localId).toBe(b!.localId);
    d().movePhoto(b!.localId, -1); // già primo: niente
    expect(d().photos[0]!.localId).toBe(b!.localId);
    d().removePhoto(a!.localId);
    expect(d().photos).toHaveLength(9);
    d().removeItem(d().items[0]!.key);
    expect(d().items).toHaveLength(1);
    expect(draftHasContent(d())).toBe(true);
    d().reset();
    expect(draftHasContent(d())).toBe(false);
  });

  test("la chiave anti-doppioni cambia solo con una bozza nuova", () => {
    const first = useNewPostDraft.getState().idempotencyKey;
    useNewPostDraft.getState().setCaption("x");
    expect(useNewPostDraft.getState().idempotencyKey).toBe(first);
    useNewPostDraft.getState().reset();
    expect(useNewPostDraft.getState().idempotencyKey).not.toBe(first);
  });
});

describe("caricamento con ripresa", () => {
  const upload = (id: string, extra: Partial<MediaUpload> = {}): MediaUpload => ({
    id,
    status: "pending",
    upload: { url: "https://s3/bucket", fields: { key: `quarantine/${id}` } },
    ...extra,
  });

  function fakeDeps(overrides: Partial<UploadDeps> = {}) {
    let n = 0;
    const deps: UploadDeps = {
      prepare: jest.fn(async () => ({ uri: "file://x.jpg", size: 1234 })),
      createUpload: jest.fn(async () => upload(`u${++n}`)),
      sendFile: jest.fn(async (_t, _f, onProgress) => {
        onProgress(0.5);
        onProgress(1);
      }),
      completeUpload: jest.fn(async (id) => ({ id, status: "processing" as const })),
      getUpload: jest.fn(async (id) => ({ id, status: "ready" as const, width: 1080, height: 1350 })),
      sleep: jest.fn(async () => undefined),
      ...overrides,
    };
    return deps;
  }

  const photo = { uri: "file://orig.heic", width: 4032, height: 3024 };

  test("percorso normale: prepara, carica con avanzamento, aspetta la pulizia", async () => {
    const deps = fakeDeps();
    const updates: UploadUpdate[] = [];
    const id = await uploadPhoto(photo, deps, (u) => updates.push(u), new AbortController().signal);
    expect(id).toBe("u1");
    expect(deps.createUpload).toHaveBeenCalledWith(1234);
    expect(updates.map((u) => u.status)).toEqual([
      "preparing",
      "uploading",
      "uploading",
      "uploading",
      "processing",
      "ready",
    ]);
    expect(updates.find((u) => u.progress === 0.5)).toBeTruthy();
  });

  test("rete caduta: riprova da sola e riesce", async () => {
    const sendFile = jest
      .fn()
      .mockRejectedValueOnce(new TypeError("Network request failed"))
      .mockRejectedValueOnce(new TypeError("Network request failed"))
      .mockResolvedValue(undefined);
    const deps = fakeDeps({ sendFile });
    const id = await uploadPhoto(photo, deps, () => undefined, new AbortController().signal);
    expect(id).toBe("u3"); // ogni tentativo riparte con un permesso nuovo
    expect(deps.sleep).toHaveBeenNthCalledWith(1, RETRY_DELAYS_MS[0], expect.anything());
    expect(deps.sleep).toHaveBeenNthCalledWith(2, RETRY_DELAYS_MS[1], expect.anything());
  });

  test("permesso firmato scaduto (403): se ne chiede un altro", async () => {
    const sendFile = jest.fn().mockRejectedValueOnce(new UploadHttpError(403)).mockResolvedValue(undefined);
    const deps = fakeDeps({ sendFile });
    expect(await uploadPhoto(photo, deps, () => undefined, new AbortController().signal)).toBe("u2");
  });

  test("dopo 4 riprove si ferma con l'errore (e il pulsante Riprova)", async () => {
    const deps = fakeDeps({ sendFile: jest.fn().mockRejectedValue(new TypeError("Network request failed")) });
    const updates: UploadUpdate[] = [];
    expect(await uploadPhoto(photo, deps, (u) => updates.push(u), new AbortController().signal)).toBeNull();
    expect(deps.sendFile).toHaveBeenCalledTimes(RETRY_DELAYS_MS.length + 1);
    expect(updates.at(-1)).toEqual({ status: "error", message: expect.stringContaining("connessione") });
  });

  test("foto rifiutata dal server: nessuna riprova, motivo in italiano", async () => {
    const deps = fakeDeps({
      getUpload: jest.fn(async (id) => ({ id, status: "rejected" as const, reject_reason: "bad_aspect_ratio" })),
    });
    const updates: UploadUpdate[] = [];
    expect(await uploadPhoto(photo, deps, (u) => updates.push(u), new AbortController().signal)).toBeNull();
    expect(deps.createUpload).toHaveBeenCalledTimes(1);
    expect(updates.at(-1)).toEqual({ status: "rejected", message: expect.stringContaining("2:1") });
  });

  test("errore definitivo del server (422): niente riprove", async () => {
    const deps = fakeDeps({
      createUpload: jest.fn().mockRejectedValue(new ApiError(422, "request.invalid", "x")),
    });
    expect(await uploadPhoto(photo, deps, () => undefined, new AbortController().signal)).toBeNull();
    expect(deps.createUpload).toHaveBeenCalledTimes(1);
  });

  test("foto tolta durante il caricamento: si ferma senza errori", async () => {
    const controller = new AbortController();
    const deps = fakeDeps({
      sendFile: jest.fn(async () => {
        controller.abort();
        throw new DOMException("Annullato", "AbortError");
      }),
    });
    const updates: UploadUpdate[] = [];
    expect(await uploadPhoto(photo, deps, (u) => updates.push(u), controller.signal)).toBeNull();
    expect(updates.some((u) => u.status === "error")).toBe(false);
  });
});
