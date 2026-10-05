import * as AppIntegrity from "@expo/app-integrity";
import { render, screen } from "@testing-library/react-native";
import * as SecureStore from "expo-secure-store";
import { Platform } from "react-native";

import { KEY_STORE, resetAttestForTests, verifyDevice } from "@/features/device/attest";
import { ApiError, apiGet, apiRequest } from "@/lib/api";
import { isOlder, markUpdateRequired, useUpdateGate } from "@/lib/updateGate";

jest.mock("@expo/app-integrity", () => ({
  isSupported: true,
  generateKeyAsync: jest.fn(async () => "key-1"),
  attestKeyAsync: jest.fn(async () => "attestazione"),
  generateAssertionAsync: jest.fn(async () => "asserzione"),
  prepareIntegrityTokenProviderAsync: jest.fn(async () => undefined),
  requestIntegrityCheckAsync: jest.fn(async () => "token-google"),
}));
jest.mock("expo-secure-store", () => {
  const store = new Map<string, string>();
  return {
    getItemAsync: jest.fn(async (k: string) => store.get(k) ?? null),
    setItemAsync: jest.fn(async (k: string, v: string) => void store.set(k, v)),
    deleteItemAsync: jest.fn(async (k: string) => void store.delete(k)),
    __store: store,
  };
});
jest.mock("@/lib/api", () => ({ ...jest.requireActual("@/lib/api"), apiGet: jest.fn(), apiRequest: jest.fn() }));

const get = apiGet as jest.Mock;
const request = apiRequest as jest.Mock;
const store = (SecureStore as unknown as { __store: Map<string, string> }).__store;
const soft = { mode: "soft" as const, android_project_number: "123456" };

function setOS(os: "ios" | "android" | "web") {
  Object.defineProperty(Platform, "OS", { get: () => os, configurable: true });
}

beforeEach(() => {
  jest.clearAllMocks();
  store.clear();
  resetAttestForTests();
  request.mockImplementation(async (_m: string, path: string) =>
    path.endsWith("/challenge") ? { challenge: "sfida", expires_in: 300 } : undefined,
  );
});

test("iPhone: prima volta attesta una chiave e la ricorda; poi basta l'asserzione", async () => {
  setOS("ios");
  get.mockResolvedValueOnce({ mode: "soft", attested: false }).mockResolvedValueOnce({ mode: "soft", attested: true });
  expect(await verifyDevice("tok", soft)).toBe(true);
  expect(AppIntegrity.attestKeyAsync).toHaveBeenCalledWith("key-1", "sfida");
  expect(request).toHaveBeenCalledWith("POST", "/v1/me/attest/ios", {
    token: "tok",
    body: { key_id: "key-1", attestation: "attestazione", challenge: "sfida" },
  });
  expect(store.get(KEY_STORE)).toBe("key-1");

  get.mockResolvedValueOnce({ mode: "soft", attested: false }).mockResolvedValueOnce({ mode: "soft", attested: true });
  await verifyDevice("tok2", soft);
  expect(AppIntegrity.generateKeyAsync).toHaveBeenCalledTimes(1);
  expect(request).toHaveBeenCalledWith("POST", "/v1/me/attest/ios/assert", {
    token: "tok2",
    body: { key_id: "key-1", assertion: "asserzione", challenge: "sfida" },
  });
});

test("iPhone: chiave sconosciuta al server, se ne attesta una nuova", async () => {
  setOS("ios");
  store.set(KEY_STORE, "vecchia");
  request.mockImplementation(async (_m: string, path: string) => {
    if (path.endsWith("/challenge")) return { challenge: "sfida", expires_in: 300 };
    if (path.endsWith("/assert")) throw new ApiError(404, "attest.unknown_key", "no");
    return undefined;
  });
  get.mockResolvedValue({ mode: "soft", attested: false });
  await verifyDevice("tok", soft);
  expect(AppIntegrity.generateKeyAsync).toHaveBeenCalled();
  expect(store.get(KEY_STORE)).toBe("key-1");
});

test("Android: token di Google Play per la sfida", async () => {
  setOS("android");
  get.mockResolvedValueOnce({ mode: "soft", attested: false }).mockResolvedValueOnce({ mode: "soft", attested: true });
  expect(await verifyDevice("tok", soft)).toBe(true);
  expect(AppIntegrity.prepareIntegrityTokenProviderAsync).toHaveBeenCalledWith("123456");
  expect(AppIntegrity.requestIntegrityCheckAsync).toHaveBeenCalledWith("sfida");
  expect(request).toHaveBeenCalledWith("POST", "/v1/me/attest/android", {
    token: "tok",
    body: { token: "token-google", challenge: "sfida" },
  });
});

test("niente verifica: modalità off, web, oppure accesso già verificato", async () => {
  setOS("ios");
  expect(await verifyDevice("tok", { mode: "off", android_project_number: null })).toBe(false);
  setOS("web");
  expect(await verifyDevice("tok", soft)).toBe(false);
  setOS("ios");
  get.mockResolvedValueOnce({ mode: "soft", attested: true });
  expect(await verifyDevice("tok", soft)).toBe(true);
  expect(request).not.toHaveBeenCalled();
});

test("versioni: confronto numerico e blocco quando l'API risponde 426", async () => {
  expect(isOlder("0.9.2", "0.10.0")).toBe(true);
  expect(isOlder("1.0.0", "1.0.0")).toBe(false);
  expect(isOlder("1.2", "1.1.9")).toBe(false);
  expect(isOlder("1.0.0-beta", "1.0.1")).toBe(true);

  const real = jest.requireActual("@/lib/api") as typeof import("@/lib/api");
  const fetchMock = jest.fn(
    async () =>
      new Response(JSON.stringify({ code: "app.update_required", title: "Aggiorna" }), {
        status: 426,
        headers: { "content-type": "application/problem+json" },
      }),
  );
  global.fetch = fetchMock as unknown as typeof fetch;
  useUpdateGate.setState({ required: false });
  await expect(real.apiRequest("GET", "/v1/me")).rejects.toMatchObject({ code: "app.update_required" });
  expect(useUpdateGate.getState().required).toBe(true);
  markUpdateRequired();
  expect(useUpdateGate.getState().required).toBe(true);
});

test("schermata Aggiorna WearX", async () => {
  jest.doMock("@/features/styles/useAppConfig", () => ({
    useAppConfig: () => ({
      data: { min_app_version: "9.0.0", store: { ios: "https://apps.apple.com/app/wearx", android: null } },
    }),
  }));
  setOS("ios");
  const { UpdateRequired } = require("@/features/update/UpdateRequired") as typeof import("@/features/update/UpdateRequired");
  const { SafeAreaProvider } = require("react-native-safe-area-context") as typeof import("react-native-safe-area-context");
  const metrics = { frame: { x: 0, y: 0, width: 390, height: 844 }, insets: { top: 47, left: 0, right: 0, bottom: 34 } };
  await render(
    <SafeAreaProvider initialMetrics={metrics}>
      <UpdateRequired />
    </SafeAreaProvider>,
  );
  expect(screen.getByRole("heading", { name: "Aggiorna WearX" })).toBeOnTheScreen();
  expect(screen.getByText(/serve almeno la 9.0.0/)).toBeOnTheScreen();
  expect(screen.getByRole("button", { name: "Apri l'App Store" })).toBeOnTheScreen();
});
