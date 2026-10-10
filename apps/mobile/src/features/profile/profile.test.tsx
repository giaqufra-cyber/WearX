import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { Profile } from "@wearx/api-types";
import { fireEvent, render, screen, userEvent, waitFor } from "@testing-library/react-native";
import type { ReactNode } from "react";
import { SafeAreaProvider } from "react-native-safe-area-context";

import EditProfileScreen from "@/app/edit-profile";
import { bioLength, bioProblem } from "@/features/profile/edit";
import { ApiError, apiRequest } from "@/lib/api";
import { ToastProvider } from "@/ui/Toast";

jest.mock("expo-router", () => ({
  router: { push: jest.fn(), replace: jest.fn(), back: jest.fn(), canGoBack: () => true },
}));
jest.mock("expo-image-picker", () => ({ launchImageLibraryAsync: jest.fn() }));
const AVATAR = {
  blurhash: "LEHV6nWB2yk8pyo0adR*.7kCMdnj",
  urls: { variants: { "320": "https://cdn/a-320.webp" }, expires_at: "2026-10-10T20:00:00Z" },
};
let mockAuth: { session: object; profile: Partial<Profile> };
function signIn(profile: Partial<Profile> = {}) {
  mockAuth = {
    session: { access_token: "tok", user: { id: "u1" } },
    profile: { nickname: "fra.fit", bio: "Trento.", avatar: null, ...profile },
  };
}
jest.mock("@/features/auth/AuthProvider", () => ({ ME_QUERY_KEY: ["me"], useAuth: () => mockAuth }));
jest.mock("@/lib/api", () => ({ ...jest.requireActual("@/lib/api"), apiRequest: jest.fn() }));
jest.mock("@/features/create/deps", () => ({
  deleteUpload: jest.fn(async () => undefined),
  realUploadDeps: () => ({
    prepare: async () => ({ uri: "file://x.jpg", size: 1000 }),
    createUpload: async () => ({ id: "up1", status: "pending", upload: { url: "https://s3", fields: {} } }),
    sendFile: async () => undefined,
    completeUpload: async (id: string) => ({ id, status: "ready" }),
    getUpload: async (id: string) => ({ id, status: "ready" }),
    sleep: async () => undefined,
  }),
}));

const ImagePicker = jest.requireMock("expo-image-picker") as { launchImageLibraryAsync: jest.Mock };
const { router } = jest.requireMock("expo-router") as { router: Record<string, jest.Mock> };
const deps = jest.requireMock("@/features/create/deps") as { deleteUpload: jest.Mock };
const request = apiRequest as jest.Mock;

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
  signIn();
  client = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: Infinity }, mutations: { retry: false, gcTime: Infinity } },
  });
  request.mockImplementation(async (_m: string, _p: string, { body }: { body: Record<string, unknown> }) => ({
    nickname: "fra.fit",
    ...body,
  }));
  ImagePicker.launchImageLibraryAsync.mockResolvedValue({
    canceled: false,
    assets: [{ uri: "file://scelta.jpg", width: 1200, height: 1200 }],
  });
});

afterEach(() => client.clear());

describe("regole della bio", () => {
  test("come il server: 150 caratteri (un'emoji vale 1) e 4 righe", () => {
    expect(bioLength("  ciao 👋  ")).toBe(6);
    expect(bioProblem("x".repeat(150))).toBeNull();
    expect(bioProblem("x".repeat(151))).toMatch(/150/);
    expect(bioProblem("👋".repeat(150))).toBeNull();
    expect(bioProblem("a\nb\nc\nd")).toBeNull();
    expect(bioProblem("a\nb\nc\nd\ne")).toMatch(/4 righe/);
  });
});

describe("Modifica profilo", () => {
  test("cambia la bio: Salva manda solo la bio", async () => {
    const user = userEvent.setup();
    await render(<EditProfileScreen />, { wrapper: Providers });
    const save = screen.getByRole("button", { name: "Salva" });
    expect(save).toBeDisabled();
    await fireEvent.changeText(screen.getByLabelText("Bio"), "Sartoria e vintage.\nTrento → Monaco");
    expect(save).toBeEnabled();
    await user.press(save);
    expect(request).toHaveBeenCalledWith("PATCH", "/v1/me", {
      token: "tok",
      body: { bio: "Sartoria e vintage.\nTrento → Monaco" },
    });
    expect(router.back).toHaveBeenCalled();
    expect(client.getQueryData(["me", "u1"])).toMatchObject({ bio: "Sartoria e vintage.\nTrento → Monaco" });
  });

  test("bio troppo lunga: avviso e Salva bloccato; svuotarla la toglie", async () => {
    const user = userEvent.setup();
    await render(<EditProfileScreen />, { wrapper: Providers });
    await fireEvent.changeText(screen.getByLabelText("Bio"), "x".repeat(151));
    expect(screen.getByText("Massimo 150 caratteri.")).toBeOnTheScreen();
    expect(screen.getByRole("button", { name: "Salva" })).toBeDisabled();
    await fireEvent.changeText(screen.getByLabelText("Bio"), "   ");
    await user.press(screen.getByRole("button", { name: "Salva" }));
    expect(request).toHaveBeenCalledWith("PATCH", "/v1/me", { token: "tok", body: { bio: null } });
  });

  test("nuova foto: si carica, poi Salva la mette come foto profilo", async () => {
    const user = userEvent.setup();
    await render(<EditProfileScreen />, { wrapper: Providers });
    await user.press(screen.getByRole("button", { name: "Scegli una foto" }));
    expect(ImagePicker.launchImageLibraryAsync).toHaveBeenCalledWith(
      expect.objectContaining({ allowsEditing: true, aspect: [1, 1] }),
    );
    expect(await screen.findByText("Foto pronta: tocca Salva.")).toBeOnTheScreen();
    await user.press(screen.getByRole("button", { name: "Salva" }));
    expect(request).toHaveBeenCalledWith("PATCH", "/v1/me", { token: "tok", body: { avatar: "up1" } });
    expect(deps.deleteUpload).not.toHaveBeenCalled();
  });

  test("togliere la foto attuale", async () => {
    signIn({ avatar: AVATAR });
    const user = userEvent.setup();
    await render(<EditProfileScreen />, { wrapper: Providers });
    await user.press(screen.getByRole("button", { name: "Togli foto" }));
    expect(screen.getByText(/Tornano le iniziali/)).toBeOnTheScreen();
    await user.press(screen.getByRole("button", { name: "Salva" }));
    expect(request).toHaveBeenCalledWith("PATCH", "/v1/me", { token: "tok", body: { avatar: null } });
  });

  test("foto non ammessa: il motivo resta a schermo", async () => {
    request.mockRejectedValue(new ApiError(422, "avatar.not_allowed", "x"));
    const user = userEvent.setup();
    await render(<EditProfileScreen />, { wrapper: Providers });
    await user.press(screen.getByRole("button", { name: "Scegli una foto" }));
    await screen.findByText("Foto pronta: tocca Salva.");
    await user.press(screen.getByRole("button", { name: "Salva" }));
    expect(await screen.findByText("Questa foto non può essere usata come foto profilo.")).toBeOnTheScreen();
    expect(router.back).not.toHaveBeenCalled();
  });

  test("uscendo senza salvare la foto caricata si cancella", async () => {
    const user = userEvent.setup();
    const view = await render(<EditProfileScreen />, { wrapper: Providers });
    await user.press(screen.getByRole("button", { name: "Scegli una foto" }));
    await screen.findByText("Foto pronta: tocca Salva.");
    await view.unmount();
    await waitFor(() => expect(deps.deleteUpload).toHaveBeenCalledWith("tok", "up1"));
  });
});
