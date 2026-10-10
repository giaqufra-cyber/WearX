import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, fireEvent, render, screen, userEvent, waitFor } from "@testing-library/react-native";
import type { ReactNode } from "react";
import { SafeAreaProvider } from "react-native-safe-area-context";

import NewPostScreen from "@/app/new-post";
import { useNewPostDraft } from "@/features/create/draft";
import { apiGet, apiRequest } from "@/lib/api";
import { ToastProvider } from "@/ui/Toast";

jest.mock("expo-crypto", () => ({ randomUUID: () => `id-${Math.random().toString(36).slice(2)}` }));
jest.mock("expo-router", () => ({
  router: { push: jest.fn(), replace: jest.fn(), back: jest.fn(), canGoBack: () => true },
}));
jest.mock("expo-image-picker", () => ({ launchImageLibraryAsync: jest.fn() }));
jest.mock("@/features/auth/AuthProvider", () => ({
  ME_QUERY_KEY: ["me"],
  useAuth: () => ({ session: { access_token: "tok", user: { id: "u1" } } }),
}));
jest.mock("@/lib/api", () => ({ ...jest.requireActual("@/lib/api"), apiGet: jest.fn(), apiRequest: jest.fn() }));
jest.mock("@/features/create/deps", () => {
  let n = 0;
  return {
    deleteUpload: jest.fn(async () => undefined),
    realUploadDeps: () => ({
      prepare: async () => ({ uri: "file://x.jpg", size: 1000 }),
      createUpload: async () => ({
        id: `up${++n}`,
        status: "pending",
        upload: { url: "https://s3", fields: {} },
      }),
      sendFile: async () => undefined,
      completeUpload: async (id: string) => ({ id, status: "ready" }),
      getUpload: async (id: string) => ({ id, status: "ready" }),
      sleep: async () => undefined,
    }),
  };
});

const ImagePicker = jest.requireMock("expo-image-picker") as { launchImageLibraryAsync: jest.Mock };
const { router } = jest.requireMock("expo-router") as { router: Record<string, jest.Mock> };
const deps = jest.requireMock("@/features/create/deps") as { deleteUpload: jest.Mock };
const get = apiGet as jest.Mock;
const request = apiRequest as jest.Mock;

const style = (slug: string, name: string) => ({
  slug,
  name,
  tagline: "",
  tone: "#3D1018",
  min_age_band: "16_17",
  seasonal: false,
  active_until: null,
  member_count: 1,
  joined: slug === "gala",
});

const metrics = { frame: { x: 0, y: 0, width: 390, height: 844 }, insets: { top: 47, left: 0, right: 0, bottom: 34 } };
let client: QueryClient;
function Providers({ children }: { children: ReactNode }) {
  return (
    <QueryClientProvider client={client}>
      <SafeAreaProvider initialMetrics={metrics}>
        <ToastProvider>{children}</ToastProvider>
      </SafeAreaProvider>
    </QueryClientProvider>
  );
}

beforeEach(() => {
  jest.clearAllMocks();
  useNewPostDraft.getState().reset();
  client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: Infinity } } });
  get.mockImplementation(async (path: string) =>
    path === "/v1/me/styles"
      ? { items: [style("gala", "Galà")], total: 1 }
      : { items: [style("gala", "Galà"), style("jappo", "Jappo")], total: 2 },
  );
  ImagePicker.launchImageLibraryAsync.mockResolvedValue({
    canceled: false,
    assets: [
      { uri: "file://a.heic", width: 3024, height: 4032 },
      { uri: "file://b.heic", width: 3024, height: 4032 },
    ],
  });
});
afterEach(() => client.clear());

test("galleria, ordine, stile, capo, didascalia, pubblica con chiave anti-doppioni", async () => {
  request.mockResolvedValue({ id: "p1", style: { name: "Galà" } });
  const user = userEvent.setup();
  await render(<NewPostScreen />, { wrapper: Providers });

  const publish = screen.getByRole("button", { name: "Pubblica" });
  expect(publish).toBeDisabled();

  await user.press(screen.getByRole("button", { name: "Scegli le foto dalla galleria" }));
  expect(ImagePicker.launchImageLibraryAsync).toHaveBeenCalledWith(
    expect.objectContaining({ allowsMultipleSelection: true, selectionLimit: 10, orderedSelection: true }),
  );
  await waitFor(() => expect(screen.getByLabelText("Foto 2 di 2: Pronta")).toBeOnTheScreen());

  // La seconda foto diventa la prima del carosello.
  await user.press(screen.getByRole("button", { name: "Sposta la foto 2 prima" }));
  expect(screen.getByText("Scegli lo stile del fit.")).toBeOnTheScreen();

  await user.press(screen.getByRole("radio", { name: "Galà" }));
  await fireEvent.changeText(screen.getByLabelText("Brand del capo 1"), "Armani");
  await fireEvent.changeText(screen.getByLabelText("Nome del capo 1"), "Smoking");
  await fireEvent.changeText(screen.getByLabelText("Prezzo in euro del capo 1"), "1.250,50");
  await fireEvent.changeText(screen.getByLabelText("Link del negozio del capo 1"), "http://armani.com");
  expect(screen.getByText("Accettiamo solo link https.")).toBeOnTheScreen();
  expect(publish).toBeDisabled();
  await fireEvent.changeText(screen.getByLabelText("Link del negozio del capo 1"), "https://www.armani.com/");
  await fireEvent.changeText(screen.getByLabelText("Didascalia"), "Prima del gala");

  expect(publish).toBeEnabled();
  const key = useNewPostDraft.getState().idempotencyKey;
  await user.press(publish);

  expect(request).toHaveBeenCalledWith("POST", "/v1/posts", {
    token: "tok",
    idempotencyKey: key,
    body: {
      style: "gala",
      caption: "Prima del gala",
      media: ["up2", "up1"],
      items: [{ brand: "Armani", name: "Smoking", price_cents: 125050, currency: "EUR", url: "https://www.armani.com/" }],
    },
  });
  expect(router.back).toHaveBeenCalled();
  expect(useNewPostDraft.getState().photos).toHaveLength(0); // bozza svuotata
});

test("errore di pubblicazione: la bozza resta e si vede il motivo", async () => {
  const { ApiError } = jest.requireActual("@/lib/api");
  request.mockRejectedValue(new ApiError(422, "link.invalid", "x"));
  const user = userEvent.setup();
  await render(<NewPostScreen />, { wrapper: Providers });
  await user.press(screen.getByRole("button", { name: "Scegli le foto dalla galleria" }));
  await waitFor(() => expect(screen.getByLabelText("Foto 2 di 2: Pronta")).toBeOnTheScreen());
  await user.press(screen.getByRole("radio", { name: "Jappo" }));
  await user.press(screen.getByRole("button", { name: "Pubblica" }));
  expect(screen.getByText(/link ai negozi non è valido/)).toBeOnTheScreen();
  expect(useNewPostDraft.getState().photos).toHaveLength(2);
});

test("annulla: chiede conferma e cancella le foto già caricate", async () => {
  const user = userEvent.setup();
  await render(<NewPostScreen />, { wrapper: Providers });
  await user.press(screen.getByRole("button", { name: "Scegli le foto dalla galleria" }));
  await waitFor(() => expect(screen.getByLabelText("Foto 2 di 2: Pronta")).toBeOnTheScreen());

  await user.press(screen.getByRole("button", { name: "Annulla" }));
  expect(screen.getByText("Scartare il fit?")).toBeOnTheScreen();
  await user.press(screen.getByRole("button", { name: "Scarta" }));
  expect(deps.deleteUpload).toHaveBeenCalledTimes(2);
  expect(useNewPostDraft.getState().photos).toHaveLength(0);
  expect(router.back).toHaveBeenCalled();
});

test("togliere una foto cancella anche il suo caricamento", async () => {
  const user = userEvent.setup();
  await render(<NewPostScreen />, { wrapper: Providers });
  await user.press(screen.getByRole("button", { name: "Scegli le foto dalla galleria" }));
  await waitFor(() => expect(screen.getByLabelText("Foto 2 di 2: Pronta")).toBeOnTheScreen());
  await act(async () => {
    await user.press(screen.getByRole("button", { name: "Togli la foto 1" }));
  });
  expect(deps.deleteUpload).toHaveBeenCalledWith("tok", expect.stringMatching(/^up/));
  expect(screen.getByText("1 di 10")).toBeOnTheScreen();
});

test("segna un capo sulla foto: il punto resta sulla sua foto anche riordinando", async () => {
  request.mockResolvedValue({ id: "p1", style: { name: "Galà" } });
  const user = userEvent.setup();
  await render(<NewPostScreen />, { wrapper: Providers });
  await user.press(screen.getByRole("button", { name: "Scegli le foto dalla galleria" }));
  await waitFor(() => expect(screen.getByLabelText("Foto 2 di 2: Pronta")).toBeOnTheScreen());
  await user.press(screen.getByRole("radio", { name: "Galà" }));
  await fireEvent.changeText(screen.getByLabelText("Brand del capo 1"), "Armani");
  await fireEvent.changeText(screen.getByLabelText("Nome del capo 1"), "Smoking");

  // Seconda foto, punto in alto a sinistra.
  await user.press(screen.getByRole("button", { name: "Segna il capo 1 sulla foto" }));
  expect(screen.getByRole("button", { name: "Fatto" })).toBeDisabled();
  await user.press(screen.getByRole("radio", { name: "Foto 2" }));
  const photo = screen.getByTestId("pin-photo");
  const { width, height } = photo.props.style.find((s: { width?: number }) => s && s.width);
  await fireEvent.press(photo, { nativeEvent: { locationX: width * 0.25, locationY: height * 0.4 } });
  expect(screen.getByText(/Punto segnato/)).toBeOnTheScreen();
  await user.press(screen.getByRole("button", { name: "Fatto" }));
  expect(screen.getByText("Sulla foto 2 · Cambia")).toBeOnTheScreen();

  // Riordinando, il punto resta sulla stessa foto (che ora è la prima).
  await user.press(screen.getByRole("button", { name: "Sposta la foto 2 prima" }));
  expect(screen.getByText("Sulla foto 1 · Cambia")).toBeOnTheScreen();
  await user.press(screen.getByRole("button", { name: "Pubblica" }));
  expect(request).toHaveBeenCalledWith(
    "POST",
    "/v1/posts",
    expect.objectContaining({
      body: expect.objectContaining({
        media: [expect.any(String), expect.any(String)],
        items: [
          {
            brand: "Armani",
            name: "Smoking",
            price_cents: null,
            currency: "EUR",
            url: null,
            media_position: 0,
            pin_x: 0.25,
            pin_y: 0.4,
          },
        ],
      }),
    }),
  );
});

test("togliere la foto su cui è segnato un capo toglie anche il punto", async () => {
  const user = userEvent.setup();
  await render(<NewPostScreen />, { wrapper: Providers });
  await user.press(screen.getByRole("button", { name: "Scegli le foto dalla galleria" }));
  await waitFor(() => expect(screen.getByLabelText("Foto 2 di 2: Pronta")).toBeOnTheScreen());
  const [first] = useNewPostDraft.getState().photos;
  const key = useNewPostDraft.getState().items[0]!.key;
  await act(async () => useNewPostDraft.getState().updateItem(key, { pin: { photo: first!.localId, x: 0.5, y: 0.5 } }));
  expect(screen.getByText("Sulla foto 1 · Cambia")).toBeOnTheScreen();
  await act(async () => {
    await user.press(screen.getByRole("button", { name: "Togli la foto 1" }));
  });
  expect(useNewPostDraft.getState().items[0]!.pin).toBeNull();
  expect(screen.getByText("Segna sulla foto (opz.)")).toBeOnTheScreen();
});
