import { randomBytes } from "node:crypto";

import { authErrorMessage } from "@/features/auth/authErrors";
import { signInCredentials, signUpCredentials } from "@/features/auth/credentials";
import { checkPasswordLeak } from "@/features/auth/passwordLeak";
import { decideRoute } from "@/features/auth/routing";
import { checkSignup, emptySignup, normalizePhone, type SignupForm } from "@/features/auth/signupForm";
import { ApiError } from "@/lib/api";
import { decrypt, encrypt, largeSecureStore } from "@/lib/secureStorage";

jest.mock("expo-crypto", () => ({
  getRandomBytes: (n: number) => new Uint8Array(require("node:crypto").randomBytes(n)),
  digestStringAsync: jest.fn(),
  CryptoDigestAlgorithm: { SHA1: "SHA-1" },
}));
jest.mock("@react-native-async-storage/async-storage", () =>
  require("@react-native-async-storage/async-storage/jest/async-storage-mock"),
);
jest.mock("expo-secure-store", () => {
  const store = new Map<string, string>();
  return {
    AFTER_FIRST_UNLOCK_THIS_DEVICE_ONLY: 1,
    getItemAsync: jest.fn(async (k: string) => store.get(k) ?? null),
    setItemAsync: jest.fn(async (k: string, v: string) => void store.set(k, v)),
    deleteItemAsync: jest.fn(async (k: string) => void store.delete(k)),
    __store: store,
  };
});

const TODAY = new Date(2026, 9, 4); // 4 ottobre 2026

const valid: SignupForm = {
  ...emptySignup,
  nickname: "francesco",
  contact: "francesco@example.com",
  password: "Trento-Monaco-2026!",
  day: "14",
  month: "3",
  year: "2003",
  acceptTerms: true,
  acceptRules: true,
};

describe("decideRoute", () => {
  const ok = { state: "ok", status: "active" } as const;

  test("in lettura della sessione si aspetta", () => {
    expect(decideRoute({ initializing: true, hasSession: false, me: { state: "loading" } })).toBe("loading");
  });

  test("senza sessione si va all'accesso", () => {
    expect(decideRoute({ initializing: false, hasSession: false, me: ok })).toBe("auth");
  });

  test("con sessione e profilo attivo si entra nell'app", () => {
    expect(decideRoute({ initializing: false, hasSession: true, me: ok })).toBe("app");
    expect(decideRoute({ initializing: false, hasSession: true, me: { state: "loading" } })).toBe("loading");
  });

  test("profilo da creare -> onboarding; token rifiutato -> accesso", () => {
    const onboarding = new ApiError(409, "onboarding.required", "Profilo da creare");
    const expired = new ApiError(401, "auth.invalid_token", "Token non valido");
    expect(decideRoute({ initializing: false, hasSession: true, me: { state: "error", error: onboarding } })).toBe(
      "onboarding",
    );
    expect(decideRoute({ initializing: false, hasSession: true, me: { state: "error", error: expired } })).toBe("auth");
  });

  test("rete giù o errore del server -> offline, senza disconnettere", () => {
    const down = new TypeError("Network request failed");
    const server = new ApiError(503, "service.unavailable", "Non disponibile");
    expect(decideRoute({ initializing: false, hasSession: true, me: { state: "error", error: down } })).toBe("offline");
    expect(decideRoute({ initializing: false, hasSession: true, me: { state: "error", error: server } })).toBe(
      "offline",
    );
  });

  test("account sospeso", () => {
    expect(decideRoute({ initializing: false, hasSession: true, me: { state: "ok", status: "suspended" } })).toBe(
      "suspended",
    );
  });
});

describe("checkSignup", () => {
  test("modulo completo e valido", () => {
    const result = checkSignup(valid, TODAY);
    expect(result).toEqual({ errors: {}, age: 23, underage: false, canSubmit: true });
  });

  test("modulo vuoto: nessun errore mostrato, ma non si può inviare", () => {
    const result = checkSignup(emptySignup, TODAY);
    expect(result.errors).toEqual({});
    expect(result.canSubmit).toBe(false);
  });

  test("sotto i 16 anni: bloccato", () => {
    const result = checkSignup({ ...valid, year: "2011" }, TODAY);
    expect(result.underage).toBe(true);
    expect(result.canSubmit).toBe(false);
  });

  test("compie 16 anni oggi: ammesso; domani: no", () => {
    expect(checkSignup({ ...valid, day: "4", month: "10", year: "2010" }, TODAY).underage).toBe(false);
    expect(checkSignup({ ...valid, day: "5", month: "10", year: "2010" }, TODAY).underage).toBe(true);
  });

  test("date impossibili e anni assurdi", () => {
    expect(checkSignup({ ...valid, day: "31", month: "2" }, TODAY).errors.birth).toBe("Questa data non esiste.");
    expect(checkSignup({ ...valid, year: "1900" }, TODAY).errors.birth).toBe("Controlla l'anno di nascita.");
  });

  test("errori su nickname, contatto, password e consensi", () => {
    const result = checkSignup(
      { ...valid, nickname: "Fra!", contact: "non-una-mail", password: "corta", acceptRules: false },
      TODAY,
    );
    expect(Object.keys(result.errors).sort()).toEqual(["contact", "nickname", "password"]);
    expect(result.canSubmit).toBe(false);
    expect(checkSignup({ ...valid, acceptTerms: false }, TODAY).canSubmit).toBe(false);
  });

  test("telefono", () => {
    expect(checkSignup({ ...valid, contactMode: "phone", contact: "333 123 4567" }, TODAY).canSubmit).toBe(true);
    expect(normalizePhone("333 123 4567")).toBe("+393331234567");
    expect(normalizePhone("0049 151 2345678")).toBe("+491512345678");
    expect(normalizePhone("+39 333-1234567")).toBe("+393331234567");
  });
});

describe("credenziali per Supabase", () => {
  test("email minuscola, nickname nei metadati", () => {
    expect(signUpCredentials("email", " Francesco@Example.COM ", "pw", "Francesco")).toEqual({
      email: "francesco@example.com",
      password: "pw",
      options: { data: { nickname: "francesco" } },
    });
  });

  test("telefono in E.164 via SMS", () => {
    expect(signUpCredentials("phone", "333 1234567", "pw", "fra")).toEqual({
      phone: "+393331234567",
      password: "pw",
      options: { data: { nickname: "fra" }, channel: "sms" },
    });
    expect(signInCredentials("phone", "333 1234567", "pw")).toEqual({ phone: "+393331234567", password: "pw" });
  });
});

describe("checkPasswordLeak (k-anonymity)", () => {
  // SHA-1 di "password"
  const HASH = "5BAA61E4C9B93F3F0682250B6CF8331B7EE68FD8";
  const sha1 = async () => HASH.toLowerCase();

  const respond = (body: string, ok = true) =>
    jest.fn(async () => ({ ok, text: async () => body }) as unknown as Response);

  test("invia solo i primi 5 caratteri dell'hash, con padding", async () => {
    const fetchImpl = respond("");
    await checkPasswordLeak("password", fetchImpl, sha1);
    const [url, init] = fetchImpl.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe("https://api.pwnedpasswords.com/range/5BAA6");
    expect(url).not.toContain(HASH.slice(5));
    expect(init.headers).toEqual({ "Add-Padding": "true" });
  });

  test("trovata nelle violazioni", async () => {
    const body = `0018A45C4D1DEF81644B54AB7F969B88D65:1\r\n${HASH.slice(5)}:3861493\r\n`;
    expect(await checkPasswordLeak("password", respond(body), sha1)).toBe("compromised");
  });

  test("le voci di padding (conteggio 0) non contano", async () => {
    expect(await checkPasswordLeak("password", respond(`${HASH.slice(5)}:0`), sha1)).toBe("clean");
  });

  test("servizio giù o in errore: non blocca", async () => {
    expect(await checkPasswordLeak("password", respond("", false), sha1)).toBe("unknown");
    const failing = jest.fn(async () => {
      throw new TypeError("Network request failed");
    });
    expect(await checkPasswordLeak("password", failing, sha1)).toBe("unknown");
  });
});

describe("authErrorMessage", () => {
  test("usa il codice, non il testo inglese", () => {
    expect(authErrorMessage({ code: "invalid_credentials", message: "Invalid login credentials" })).toBe(
      "Email o password non corrette.",
    );
    expect(authErrorMessage({ code: "otp_expired" })).toContain("scaduto");
  });

  test("429 senza codice e fallback generico", () => {
    expect(authErrorMessage({ status: 429 })).toBe("Troppi tentativi. Aspetta qualche minuto.");
    expect(authErrorMessage(null)).toContain("Controlla la connessione");
    expect(authErrorMessage({ code: "codice_sconosciuto" })).toContain("Controlla la connessione");
  });
});

describe("archivio cifrato della sessione", () => {
  test("cifra e decifra", () => {
    const key = new Uint8Array(randomBytes(32));
    const secret = JSON.stringify({ access_token: "eyJ…", refresh_token: "r-123", note: "àèìòù ✓" });
    const hex = encrypt(secret, key);
    expect(hex).not.toContain("r-123");
    expect(decrypt(hex, key)).toBe(secret);
  });

  test("su disco solo testo cifrato, chiave nuova a ogni scrittura", async () => {
    const AsyncStorage = require("@react-native-async-storage/async-storage");
    const SecureStore = require("expo-secure-store");
    const session = JSON.stringify({ refresh_token: "segreto-123" });

    await largeSecureStore.setItem("sb-abc-auth-token", session);
    const stored = await AsyncStorage.getItem("wx.d.sb-abc-auth-token");
    expect(stored).not.toContain("segreto");
    const firstKey = SecureStore.__store.get("wx.k.sb-abc-auth-token");
    expect(firstKey).toHaveLength(64);
    expect(await largeSecureStore.getItem("sb-abc-auth-token")).toBe(session);

    await largeSecureStore.setItem("sb-abc-auth-token", session);
    expect(SecureStore.__store.get("wx.k.sb-abc-auth-token")).not.toBe(firstKey);
    expect(SecureStore.setItemAsync).toHaveBeenLastCalledWith("wx.k.sb-abc-auth-token", expect.any(String), {
      keychainAccessible: 1,
    });

    await largeSecureStore.removeItem("sb-abc-auth-token");
    expect(await largeSecureStore.getItem("sb-abc-auth-token")).toBeNull();
  });

  test("chiave mancante o dati corrotti: nessuna sessione, nessun crash", async () => {
    const AsyncStorage = require("@react-native-async-storage/async-storage");
    await AsyncStorage.setItem("wx.d.orfano", "zz-non-esadecimale");
    expect(await largeSecureStore.getItem("orfano")).toBeNull();
  });
});
