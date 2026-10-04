import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook } from "@testing-library/react-native";
import type { ReactNode } from "react";

import { NICKNAME_DEBOUNCE_MS, useNicknameAvailability } from "@/features/auth/useNicknameAvailability";
import { apiRequest } from "@/lib/api";

jest.mock("@/lib/api", () => ({ apiRequest: jest.fn() }));
const request = apiRequest as jest.Mock;

let client: QueryClient;
function wrapper({ children }: { children: ReactNode }) {
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

beforeEach(() => {
  jest.useFakeTimers();
  request.mockReset();
  client = new QueryClient({ defaultOptions: { queries: { gcTime: Infinity } } });
});
afterEach(() => jest.useRealTimers());

async function settle() {
  // Pausa di battitura, poi i timer con cui react-query notifica i risultati.
  await act(async () => {
    await jest.advanceTimersByTimeAsync(NICKNAME_DEBOUNCE_MS);
  });
  await act(async () => {
    await jest.advanceTimersByTimeAsync(50);
  });
}

test("formato non valido: nessuna richiesta", async () => {
  const { result } = await renderHook(() => useNicknameAvailability("ab"), { wrapper });
  await settle();
  expect(result.current).toBe("idle");
  expect(request).not.toHaveBeenCalled();
});

test("chiede all'API solo dopo la pausa di battitura, una volta sola", async () => {
  request.mockResolvedValue({ nickname: "francesco", available: true, reason: null });
  const { result, rerender } = await renderHook(({ nick }: { nick: string }) => useNicknameAvailability(nick), {
    wrapper,
    initialProps: { nick: "" },
  });
  await rerender({ nick: "fran" });
  await rerender({ nick: "franc" });
  await rerender({ nick: "Francesco" });
  expect(result.current).toBe("checking");
  await settle();
  expect(request).toHaveBeenCalledTimes(1);
  expect(request).toHaveBeenCalledWith("POST", "/v1/auth/nickname-check", {
    body: { nickname: "francesco" },
    signal: expect.anything(),
  });
  expect(result.current).toBe("available");
});

test("preso, riservato, API irraggiungibile", async () => {
  request.mockResolvedValueOnce({ nickname: "francesco2", available: false, reason: "taken" });
  const taken = await renderHook(() => useNicknameAvailability("francesco2"), { wrapper });
  await settle();
  expect(taken.result.current).toBe("taken");

  request.mockResolvedValueOnce({ nickname: "studio.moda", available: false, reason: "reserved" });
  const reserved = await renderHook(() => useNicknameAvailability("studio.moda"), { wrapper });
  await settle();
  expect(reserved.result.current).toBe("reserved");

  request.mockRejectedValueOnce(new TypeError("Network request failed"));
  const down = await renderHook(() => useNicknameAvailability("francesco"), { wrapper });
  await settle();
  expect(down.result.current).toBe("unknown");
});
