import type { PersonCard } from "@wearx/api-types";
import { colors, fonts, spacing } from "@wearx/design-tokens";
import { router } from "expo-router";
import { useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";

import { useDismissSuggestion, useFollowFromList, usePeopleSearch, useSuggestions } from "@/features/people/api";
import { normalizeQuery, personLine, splitMatch } from "@/features/people/format";
import { freshAvatar, type RecentPerson, useRecentPeople } from "@/features/people/recent";
import { useDebouncedValue } from "@/lib/useDebouncedValue";
import { Avatar } from "@/ui/Avatar";
import { Button } from "@/ui/Button";
import { EmptyState } from "@/ui/EmptyState";
import { IconButton } from "@/ui/IconButton";
import { IconClose } from "@/ui/icons";
import { ErrorNotice } from "@/ui/LoadState";
import { SearchField } from "@/ui/SearchField";
import { Skeleton } from "@/ui/Skeleton";
import { useToast } from "@/ui/Toast";

export const PEOPLE_DEBOUNCE_MS = 200;
const AVATAR = 44;

function openProfile(nickname: string, isSelf: boolean) {
  if (isSelf) router.navigate("/profile");
  else router.push({ pathname: "/user/[nickname]", params: { nickname } });
}

/**
 * Cerca persone (seduta 31). Senza testo: profili aperti di recente e persone che potresti
 * conoscere, ognuna con il motivo. Con il testo: i nickname che iniziano, contengono o
 * somigliano, con davanti chi conosci già.
 */
export function PeopleSearch({ autoFocus = false }: { autoFocus?: boolean }) {
  const [text, setText] = useState("");
  const query = useDebouncedValue(normalizeQuery(text), PEOPLE_DEBOUNCE_MS);
  const typing = normalizeQuery(text).length > 0;
  const results = usePeopleSearch(typing ? query : "");
  const recent = useRecentPeople();

  const open = (person: PersonCard | RecentPerson, isSelf = false) => {
    if (!isSelf) recent.add(person);
    openProfile(person.nickname, isSelf);
  };

  return (
    <View style={styles.wrap}>
      <SearchField
        value={text}
        onChangeText={setText}
        label="Cerca persone"
        placeholder="Cerca un nickname"
        maxLength={31}
        autoFocus={autoFocus}
      />
      {typing ? (
        <View style={styles.list}>
          {results.isError ? <ErrorNotice error={results.error} onRetry={() => void results.refetch()} /> : null}
          {results.isPending ? <RowsSkeleton count={3} /> : null}
          {results.data?.items.map((person) => (
            <PersonRow
              key={person.nickname}
              person={person}
              highlight={results.data?.query ?? ""}
              onOpen={() => open(person, person.is_self)}
            />
          ))}
          {results.isSuccess && results.data.items.length === 0 && query === results.data.query ? (
            <EmptyState
              title="Nessuno con questo nickname"
              body="Controlla come si scrive. Chi ha scelto di non farsi trovare compare solo col nickname esatto."
            />
          ) : null}
        </View>
      ) : (
        <>
          {recent.items.length > 0 ? (
            <View style={styles.list}>
              <View style={styles.head}>
                <Text style={styles.section}>RECENTI</Text>
                <Pressable role="button" onPress={recent.clear} hitSlop={8}>
                  <Text style={styles.clear}>Cancella</Text>
                </Pressable>
              </View>
              {recent.items.map((person) => (
                <RecentRow
                  key={person.nickname}
                  person={person}
                  onOpen={() => open(person)}
                  onRemove={() => recent.remove(person.nickname)}
                />
              ))}
            </View>
          ) : null}
          <Suggested onOpen={(person) => open(person)} hide={recent.items.map((p) => p.nickname)} />
        </>
      )}
    </View>
  );
}

function Suggested({ onOpen, hide }: { onOpen: (person: PersonCard) => void; hide: string[] }) {
  const toast = useToast();
  const suggestions = useSuggestions();
  const dismiss = useDismissSuggestion({ onError: (message) => toast.show(message, { tone: "error" }) });
  // Chi è già nei recenti non si ripete qui sotto.
  const items = (suggestions.data?.items ?? []).filter((p) => !hide.includes(p.nickname));

  return (
    <View style={styles.list}>
      <Text style={styles.section}>PERSONE CHE POTRESTI CONOSCERE</Text>
      {suggestions.isPending ? <RowsSkeleton count={4} /> : null}
      {suggestions.isError ? <ErrorNotice error={suggestions.error} onRetry={() => void suggestions.refetch()} /> : null}
      {items.map((person) => (
        <PersonRow
          key={person.nickname}
          person={person}
          onOpen={() => onOpen(person)}
          onDismiss={() => dismiss.mutate(person.nickname)}
        />
      ))}
      {suggestions.isSuccess && items.length === 0 ? (
        <EmptyState
          title="Ancora nessun suggerimento"
          body="Segui qualcuno o entra in altri stili: qui compariranno amici di amici e persone con i tuoi stili."
        />
      ) : null}
    </View>
  );
}

function PersonRow({
  person,
  highlight = "",
  onOpen,
  onDismiss,
}: {
  person: PersonCard;
  highlight?: string;
  onOpen: () => void;
  onDismiss?: () => void;
}) {
  const line = personLine(person);
  const [before, match, after] = splitMatch(person.nickname, highlight);
  return (
    <View style={styles.row}>
      <Pressable
        role="link"
        aria-label={`@${person.nickname}, ${line}`}
        onPress={onOpen}
        style={({ pressed }) => [styles.who, pressed ? styles.pressed : null]}
      >
        <Avatar nickname={person.nickname} avatar={person.avatar} size={AVATAR} />
        <View style={styles.text}>
          <Text style={[styles.nick, match ? styles.dim : null]} numberOfLines={1}>
            @{before}
            {match ? <Text style={styles.match}>{match}</Text> : null}
            {after}
          </Text>
          <Text style={styles.line} numberOfLines={1}>
            {line}
          </Text>
        </View>
      </Pressable>
      {person.is_self ? null : <RowFollow person={person} onOpen={onOpen} />}
      {onDismiss ? (
        <IconButton label={`Non suggerire più @${person.nickname}`} onPress={onDismiss}>
          <IconClose color={colors.textTertiary} size={18} />
        </IconButton>
      ) : null}
    </View>
  );
}

/** Testi corti: nella riga c'è poco spazio, e "Ti segue" lo dice già la riga sotto il nickname. */
export function rowFollowLabel(state: PersonCard["following"]): string {
  if (state === "accepted") return "Segui già";
  if (state === "pending") return "Inviata";
  return "Segui";
}

/** Segui, ritira la richiesta; "Segui già" apre il profilo (lì si smette di seguire, con conferma). */
function RowFollow({ person, onOpen }: { person: PersonCard; onOpen: () => void }) {
  const toast = useToast();
  const follow = useFollowFromList({ onError: (message) => toast.show(message, { tone: "error" }) });
  const state = person.following;
  const press = () => {
    if (state === "accepted") {
      onOpen();
    } else if (state === "pending") {
      follow.mutate({ person, action: "unfollow" }, { onSuccess: () => toast.show("Richiesta ritirata.") });
    } else {
      follow.mutate(
        { person, action: "follow" },
        {
          onSuccess: (now) =>
            toast.show(now === "pending" ? `Richiesta inviata a @${person.nickname}.` : `Ora segui @${person.nickname}.`),
        },
      );
    }
  };
  return (
    <Button
      label={rowFollowLabel(state)}
      variant={state === "none" ? "primary" : "secondary"}
      size="sm"
      onPress={press}
      hint={
        state === "pending"
          ? `Richiesta inviata. Tocca per ritirarla`
          : state === "accepted"
            ? `Apri il profilo di @${person.nickname}`
            : `Segui @${person.nickname}`
      }
    />
  );
}

function RecentRow({ person, onOpen, onRemove }: { person: RecentPerson; onOpen: () => void; onRemove: () => void }) {
  return (
    <View style={styles.row}>
      <Pressable
        role="link"
        aria-label={`@${person.nickname}, aperto di recente`}
        onPress={onOpen}
        style={({ pressed }) => [styles.who, pressed ? styles.pressed : null]}
      >
        <Avatar nickname={person.nickname} avatar={freshAvatar(person)} size={AVATAR} />
        <View style={styles.text}>
          <Text style={styles.nick} numberOfLines={1}>
            @{person.nickname}
          </Text>
          {person.account_type === "business" ? <Text style={styles.line}>Account business</Text> : null}
        </View>
      </Pressable>
      <IconButton label={`Togli @${person.nickname} dai recenti`} onPress={onRemove}>
        <IconClose color={colors.textTertiary} size={18} />
      </IconButton>
    </View>
  );
}

function RowsSkeleton({ count }: { count: number }) {
  return (
    <View style={styles.list} role="progressbar" aria-label="Carico le persone">
      {Array.from({ length: count }, (_, i) => (
        <View key={i} style={styles.row}>
          <Skeleton width={AVATAR} height={AVATAR} radius={AVATAR / 2} />
          <View style={styles.text}>
            <Skeleton width="55%" height={14} radius={6} />
            <Skeleton width="80%" height={12} radius={6} />
          </View>
        </View>
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { gap: spacing[4] },
  list: { gap: spacing[3] },
  head: { flexDirection: "row", justifyContent: "space-between", alignItems: "baseline" },
  section: { fontFamily: fonts.mono, fontSize: 11, letterSpacing: 11 * 0.14, color: colors.textSecondary },
  clear: { fontFamily: fonts.uiBold, fontSize: 13, color: colors.accent },
  row: { flexDirection: "row", alignItems: "center", gap: spacing[2], minHeight: 52 },
  who: { flex: 1, minWidth: 0, flexDirection: "row", alignItems: "center", gap: 12 },
  pressed: { opacity: 0.7 },
  text: { flex: 1, minWidth: 0, gap: 4 },
  nick: { fontFamily: fonts.uiBold, fontSize: 15, color: colors.text },
  // Con la ricerca: il resto del nickname più tenue, la parte scritta piena.
  dim: { color: colors.textSecondary },
  match: { color: colors.text },
  line: { fontFamily: fonts.ui, fontSize: 13, color: colors.textTertiary },
});
