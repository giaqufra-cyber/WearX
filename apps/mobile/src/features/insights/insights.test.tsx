import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { Insights } from "@wearx/api-types";
import { render, screen, userEvent } from "@testing-library/react-native";
import type { ReactNode } from "react";
import { SafeAreaProvider } from "react-native-safe-area-context";

import InsightsScreen from "@/app/insights";
import { formatChange, formatInt, formatMetric } from "@/features/insights/api";
import { apiGet } from "@/lib/api";

jest.mock("expo-router", () => ({
  router: { push: jest.fn(), replace: jest.fn(), back: jest.fn(), canGoBack: () => true },
}));
jest.mock("@/features/auth/AuthProvider", () => ({
  useAuth: () => ({ session: { access_token: "tok", user: { id: "u1" } } }),
}));
jest.mock("@/lib/api", () => ({ ...jest.requireActual("@/lib/api"), apiGet: jest.fn() }));

const { router } = jest.requireMock("expo-router") as { router: Record<string, jest.Mock> };
const get = apiGet as jest.Mock;

const metrics = { frame: { x: 0, y: 0, width: 390, height: 844 }, insets: { top: 47, left: 0, right: 0, bottom: 34 } };
let client: QueryClient;
function Providers({ children }: { children: ReactNode }) {
  return (
    <QueryClientProvider client={client}>
      <SafeAreaProvider initialMetrics={metrics}>{children}</SafeAreaProvider>
    </QueryClientProvider>
  );
}

beforeEach(() => {
  jest.clearAllMocks();
  client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: Infinity } } });
});
afterEach(() => client.clear());

const days = ["2026-09-28", "2026-09-29", "2026-09-30", "2026-10-01", "2026-10-02", "2026-10-03", "2026-10-04"];

const data = (extra: Partial<Insights> = {}): Insights => ({
  days: 7,
  start: "2026-09-28",
  end: "2026-10-04",
  updated_at: "2026-10-05T01:40:00Z",
  threshold: 5,
  bucket: "day",
  totals: {
    impressions: { value: 1240, change: 12.4 },
    opens: { value: 310, change: -8 },
    votes: { value: 86, change: 0.2 },
    shop_clicks: { value: null, change: null },
    profile_views: { value: 0, change: null },
    average: 78.4,
  },
  series: days.map((start, i) => ({ start, impressions: i === 0 ? null : 100 + i * 20, votes: i === 0 ? null : 10 + i })),
  top_posts: [
    {
      id: "p1",
      caption: "Prima alla Scala",
      style: "Galà",
      blurhash: null,
      thumb: null,
      impressions: 640,
      votes: 51,
      average: 84.2,
      shop_clicks: null,
    },
    {
      id: "p2",
      caption: null,
      style: "Old Money",
      blurhash: null,
      thumb: null,
      impressions: null,
      votes: null,
      average: null,
      shop_clicks: 0,
    },
  ],
  ...extra,
});

test("formati", () => {
  expect(formatInt(1234567)).toBe("1.234.567");
  expect(formatMetric(null)).toBe("<5");
  expect(formatMetric(0)).toBe("0");
  expect(formatChange({ value: 10, change: 12.4 })).toBe("+12%");
  expect(formatChange({ value: 10, change: -8 })).toBe("−8%");
  expect(formatChange({ value: 10, change: 0.2 })).toBe("=");
  expect(formatChange({ value: 10, change: null })).toBeNull();
});

test("numeri, soglie, confronto, grafico e fit migliori", async () => {
  get.mockResolvedValue(data());
  const user = userEvent.setup();
  await render(<InsightsScreen />, { wrapper: Providers });

  expect(await screen.findByLabelText("Visualizzazioni: 1.240, +12% vs 7 giorni prima")).toBeOnTheScreen();
  expect(screen.getByLabelText("Aperture: 310, −8% vs 7 giorni prima")).toBeOnTheScreen();
  expect(screen.getByLabelText("Click ai negozi: meno di 5")).toBeOnTheScreen();
  expect(screen.getByLabelText("Media voti: 78,4")).toBeOnTheScreen();
  expect(get).toHaveBeenCalledWith("/v1/me/insights?days=7", expect.objectContaining({ token: "tok" }));

  // Il grafico parte dall'ultimo giorno; toccando un giorno con pochi dati si legge "meno di 5".
  expect(screen.getByText(/220 visualizzazioni$/)).toBeOnTheScreen();
  await user.press(screen.getByRole("button", { name: /28 set: meno di 5 visualizzazioni/ }));
  expect(screen.getByText(/meno di 5 visualizzazioni$/)).toBeOnTheScreen();
  await user.press(screen.getByRole("radio", { name: "Voti" }));
  expect(screen.getByText(/16 voti$/)).toBeOnTheScreen();

  expect(screen.getByRole("button", { name: "2. Fit senza didascalia, Old Money: <5 visualizzazioni, <5 voti" })).toBeOnTheScreen();
  await user.press(screen.getByRole("button", { name: /^1\. Prima alla Scala/ }));
  expect(router.push).toHaveBeenCalledWith({ pathname: "/post/[id]", params: { id: "p1" } });

  await user.press(screen.getByRole("radio", { name: "28 giorni" }));
  expect(get).toHaveBeenCalledWith("/v1/me/insights?days=28", expect.anything());
});

test("nessun dato", async () => {
  const empty = data();
  get.mockResolvedValue({
    ...empty,
    totals: { ...empty.totals, impressions: { value: 0, change: null }, votes: { value: 0, change: null } },
    top_posts: [],
  });
  await render(<InsightsScreen />, { wrapper: Providers });
  expect(await screen.findByText("Ancora nessun dato")).toBeOnTheScreen();
  expect(screen.getByText(/i numeri da 1 a 4 compaiono come/)).toBeOnTheScreen();
});
