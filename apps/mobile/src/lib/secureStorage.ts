/**
 * Archivio cifrato per la sessione di Supabase (schema consigliato dalla documentazione
 * Supabase per Expo): il portachiavi sicuro del telefono (Keychain / Keystore) accetta
 * al massimo 2048 byte per valore, la sessione è più grande.
 * Quindi: a ogni scrittura si genera una chiave AES-256 nuova, la si salva nel portachiavi
 * e si salva in AsyncStorage solo il testo cifrato.
 */
import AsyncStorage from "@react-native-async-storage/async-storage";
import aesjs from "aes-js";
import { getRandomBytes } from "expo-crypto";
import * as SecureStore from "expo-secure-store";

const KEY_PREFIX = "wx.k.";
const DATA_PREFIX = "wx.d.";

function keyName(key: string): string {
  // Il portachiavi accetta solo [A-Za-z0-9._-] nei nomi.
  return KEY_PREFIX + key.replace(/[^A-Za-z0-9._-]/g, "_");
}

export function encrypt(value: string, keyBytes: Uint8Array): string {
  const cipher = new aesjs.ModeOfOperation.ctr(keyBytes, new aesjs.Counter(1));
  return aesjs.utils.hex.fromBytes(cipher.encrypt(aesjs.utils.utf8.toBytes(value)));
}

export function decrypt(hex: string, keyBytes: Uint8Array): string {
  const cipher = new aesjs.ModeOfOperation.ctr(keyBytes, new aesjs.Counter(1));
  return aesjs.utils.utf8.fromBytes(cipher.decrypt(aesjs.utils.hex.toBytes(hex)));
}

export const largeSecureStore = {
  async getItem(key: string): Promise<string | null> {
    const [hexKey, data] = await Promise.all([
      SecureStore.getItemAsync(keyName(key)),
      AsyncStorage.getItem(DATA_PREFIX + key),
    ]);
    if (!hexKey || !data) return null;
    try {
      return decrypt(data, aesjs.utils.hex.toBytes(hexKey));
    } catch {
      return null;
    }
  },

  async setItem(key: string, value: string): Promise<void> {
    // Chiave nuova a ogni scrittura: con AES-CTR non si riusa mai lo stesso flusso di cifratura.
    const keyBytes = getRandomBytes(32);
    await SecureStore.setItemAsync(keyName(key), aesjs.utils.hex.fromBytes(keyBytes), {
      keychainAccessible: SecureStore.AFTER_FIRST_UNLOCK_THIS_DEVICE_ONLY,
    });
    await AsyncStorage.setItem(DATA_PREFIX + key, encrypt(value, keyBytes));
  },

  async removeItem(key: string): Promise<void> {
    await Promise.all([
      SecureStore.deleteItemAsync(keyName(key)),
      AsyncStorage.removeItem(DATA_PREFIX + key),
    ]);
  },
};
