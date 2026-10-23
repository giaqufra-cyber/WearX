/**
 * Profili aperti dalla ricerca, solo su questo telefono (seduta 31). Comodità: se la memoria non
 * c'è o non risponde, l'elenco resta vuoto e la ricerca funziona lo stesso.
 */
import AsyncStorage from "@react-native-async-storage/async-storage";
import type { PersonCard } from "@wearx/api-types";
import { useCallback, useEffect, useState } from "react";

import { useAuth } from "@/features/auth/AuthProvider";

export const RECENT_MAX = 8;

export type RecentPerson = Pick<PersonCard, "nickname" | "account_type" | "avatar">;

const storageKey = (uid: string) => `wearx.recent-people.${uid}`;

/** La foto profilo ha un indirizzo che scade: dopo, meglio le iniziali di un'immagine rotta. */
export function freshAvatar(person: RecentPerson, now = Date.now()): RecentPerson["avatar"] {
  const avatar = person.avatar;
  if (!avatar) return null;
  return new Date(avatar.urls.expires_at).getTime() > now ? avatar : null;
}

export function pushRecent(list: RecentPerson[], person: RecentPerson): RecentPerson[] {
  const entry: RecentPerson = { nickname: person.nickname, account_type: person.account_type, avatar: person.avatar ?? null };
  return [entry, ...list.filter((p) => p.nickname !== person.nickname)].slice(0, RECENT_MAX);
}

function parse(raw: string | null): RecentPerson[] {
  if (!raw) return [];
  try {
    const value: unknown = JSON.parse(raw);
    if (!Array.isArray(value)) return [];
    return value
      .filter((p): p is RecentPerson => typeof p?.nickname === "string" && typeof p?.account_type === "string")
      .slice(0, RECENT_MAX);
  } catch {
    return [];
  }
}

export function useRecentPeople() {
  const { session } = useAuth();
  const uid = session?.user.id;
  const [items, setItems] = useState<RecentPerson[]>([]);

  useEffect(() => {
    let alive = true;
    setItems([]);
    if (!uid) return;
    AsyncStorage.getItem(storageKey(uid))
      .then((raw) => {
        if (alive) setItems(parse(raw));
      })
      .catch(() => undefined);
    return () => {
      alive = false;
    };
  }, [uid]);

  const save = useCallback(
    (update: (list: RecentPerson[]) => RecentPerson[]) => {
      setItems((current) => {
        const next = update(current);
        if (uid) void AsyncStorage.setItem(storageKey(uid), JSON.stringify(next)).catch(() => undefined);
        return next;
      });
    },
    [uid],
  );

  return {
    items,
    add: useCallback((person: RecentPerson) => save((list) => pushRecent(list, person)), [save]),
    remove: useCallback((nickname: string) => save((list) => list.filter((p) => p.nickname !== nickname)), [save]),
    clear: useCallback(() => save(() => []), [save]),
  };
}
