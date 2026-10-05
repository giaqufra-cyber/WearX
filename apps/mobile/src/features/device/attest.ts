/**
 * Verifica del dispositivo (seduta 22): dimostra al server che è l'app ufficiale su un telefono
 * vero. Si fa una volta per accesso, in silenzio; se non riesce l'app funziona comunque (in
 * modalità "soft" i voti pesano la metà, in "required" il voto chiede di aggiornare/riprovare).
 * - iOS (App Attest): la prima volta si crea e si attesta una chiave (salvata nel portachiavi);
 *   ai nuovi accessi basta firmare la sfida con quella chiave.
 * - Android (Play Integrity): Google Play rilascia un token per la sfida.
 * Sul web non esiste: non si fa nulla.
 */
import * as AppIntegrity from "@expo/app-integrity";
import type { Schemas } from "@wearx/api-types";
import * as SecureStore from "expo-secure-store";
import { Platform } from "react-native";

import { ApiError, apiGet, apiRequest } from "@/lib/api";

type AttestationConfig = Schemas["AttestationConfig"];
type Challenge = Schemas["ChallengeOut"];
type Status = Schemas["AttestStatus"];

export const KEY_STORE = "wearx.attest.key";
let preparedProject: string | null = null;

async function challenge(token: string): Promise<string> {
  return (await apiRequest<Challenge>("POST", "/v1/me/attest/challenge", { token })).challenge;
}

async function attestNewKey(token: string): Promise<void> {
  const keyId = await AppIntegrity.generateKeyAsync();
  const value = await challenge(token);
  const attestation = await AppIntegrity.attestKeyAsync(keyId, value);
  await apiRequest("POST", "/v1/me/attest/ios", {
    token,
    body: { key_id: keyId, attestation, challenge: value },
  });
  await SecureStore.setItemAsync(KEY_STORE, keyId);
}

async function verifyIos(token: string): Promise<void> {
  if (!AppIntegrity.isSupported) return;
  const keyId = await SecureStore.getItemAsync(KEY_STORE);
  if (!keyId) return attestNewKey(token);
  const value = await challenge(token);
  try {
    const assertion = await AppIntegrity.generateAssertionAsync(keyId, value);
    await apiRequest("POST", "/v1/me/attest/ios/assert", {
      token,
      body: { key_id: keyId, assertion, challenge: value },
    });
  } catch (error) {
    // Chiave sconosciuta al server o non più valida sul telefono: se ne attesta una nuova.
    if (error instanceof ApiError && error.code !== "attest.unknown_key") throw error;
    await SecureStore.deleteItemAsync(KEY_STORE);
    await attestNewKey(token);
  }
}

async function verifyAndroid(token: string, project: string | null | undefined): Promise<void> {
  if (!project) return;
  if (preparedProject !== project) {
    await AppIntegrity.prepareIntegrityTokenProviderAsync(project);
    preparedProject = project;
  }
  const value = await challenge(token);
  const integrityToken = await AppIntegrity.requestIntegrityCheckAsync(value);
  await apiRequest("POST", "/v1/me/attest/android", {
    token,
    body: { token: integrityToken, challenge: value },
  });
}

/** Verifica il dispositivo se serve. Restituisce true se l'accesso risulta verificato. */
export async function verifyDevice(token: string, config: AttestationConfig | undefined): Promise<boolean> {
  if (!config || config.mode === "off" || Platform.OS === "web") return false;
  const status = await apiGet<Status>("/v1/me/attest", { token });
  if (status.attested) return true;
  if (Platform.OS === "ios") await verifyIos(token);
  else if (Platform.OS === "android") await verifyAndroid(token, config.android_project_number);
  else return false;
  return (await apiGet<Status>("/v1/me/attest", { token })).attested;
}

/** Solo per i test. */
export function resetAttestForTests(): void {
  preparedProject = null;
}
