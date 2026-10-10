import { useQueryClient } from "@tanstack/react-query";
import type { Post, StyleCard } from "@wearx/api-types";
import { colors, fonts, fontSizes, radii, spacing } from "@wearx/design-tokens";
import * as ImagePicker from "expo-image-picker";
import { router } from "expo-router";
import { useMemo, useState } from "react";
import { KeyboardAvoidingView, Platform, Pressable, ScrollView, StyleSheet, Text as RNText, TextInput, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { useAuth } from "@/features/auth/AuthProvider";
import { realUploadDeps, deleteUpload } from "@/features/create/deps";
import { draftHasContent, useNewPostDraft } from "@/features/create/draft";
import { cancelAllUploads, cancelUpload, retryPhoto, useUploadEngine } from "@/features/create/engine";
import { buildPostRequest, canPublish, CAPTION_MAX, MAX_ITEMS, MAX_PHOTOS } from "@/features/create/form";
import { ItemCard } from "@/features/create/ItemCard";
import { PhotoStrip } from "@/features/create/PhotoStrip";
import { PORTFOLIO_KEY } from "@/features/portfolio/api";
import { STYLES_KEY, useMyStyles, useStyles } from "@/features/styles/api";
import { ApiError, apiRequest } from "@/lib/api";
import { Button } from "@/ui/Button";
import { IconClose, IconLock } from "@/ui/icons";
import { IconButton } from "@/ui/IconButton";
import { Sheet } from "@/ui/Sheet";
import { useToast } from "@/ui/Toast";

const PUBLISH_ERRORS: Record<string, string> = {
  "link.invalid": "Uno dei link ai negozi non è valido: usa un indirizzo https del sito.",
  "style.not_found": "Questo stile non è più disponibile: scegline un altro.",
  "media.unavailable": "Una foto non è più disponibile: toglila e aggiungila di nuovo.",
  "text.invalid_characters": "C'è un carattere non ammesso nella didascalia o nei capi.",
  "text.too_long": "Un testo è troppo lungo.",
  "rate.limited": "Hai pubblicato molto in poco tempo: riprova tra un po'.",
  "text.not_allowed": "Ci sono parole non ammesse nella didascalia o nei capi.",
};

/** Nuovo fit (prototipo, schermata Create). Si apre a tutto schermo dal "+" della barra. */
export default function NewPostScreen() {
  const { session } = useAuth();
  const token = session?.access_token;
  const deps = useMemo(() => (token ? realUploadDeps(token) : null), [token]);
  useUploadEngine(deps);

  const draft = useNewPostDraft();
  const toast = useToast();
  const queryClient = useQueryClient();
  const mine = useMyStyles();
  const all = useStyles("");
  const [confirmDiscard, setConfirmDiscard] = useState(false);
  const [publishing, setPublishing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // I tuoi stili per primi, poi gli altri.
  const styleOptions = useMemo(() => {
    const own = mine.data?.items ?? [];
    const others = (all.data?.items ?? []).filter((s) => !own.some((o) => o.slug === s.slug));
    return [...own, ...others];
  }, [mine.data, all.data]);

  const check = canPublish(draft);

  const pick = async () => {
    const remaining = MAX_PHOTOS - draft.photos.length;
    if (remaining <= 0) return;
    const result = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ["images"],
      allowsMultipleSelection: true,
      selectionLimit: remaining,
      orderedSelection: true,
      quality: 1,
      exif: false,
    });
    if (result.canceled || !result.assets?.length) return;
    draft.addPhotos(result.assets.slice(0, remaining).map((a) => ({ uri: a.uri, width: a.width, height: a.height })));
  };

  const removePhoto = (localId: string) => {
    const photo = draft.photos.find((p) => p.localId === localId);
    cancelUpload(localId);
    draft.removePhoto(localId);
    if (token && photo?.uploadId) void deleteUpload(token, photo.uploadId);
  };

  const discard = () => {
    cancelAllUploads();
    if (token) for (const p of draft.photos) if (p.uploadId) void deleteUpload(token, p.uploadId);
    draft.reset();
    setConfirmDiscard(false);
    close();
  };

  const close = () => (router.canGoBack() ? router.back() : router.replace("/"));

  const publish = async () => {
    if (!check.ok || !token || publishing) return;
    setPublishing(true);
    setError(null);
    try {
      const post = await apiRequest<Post>("POST", "/v1/posts", {
        token,
        body: buildPostRequest(draft),
        idempotencyKey: draft.idempotencyKey,
      });
      draft.reset();
      void queryClient.invalidateQueries({ queryKey: STYLES_KEY });
      void queryClient.invalidateQueries({ queryKey: PORTFOLIO_KEY });
      toast.show(`Fit pubblicato in ${post.style.name}.`);
      close();
    } catch (caught) {
      const code = caught instanceof ApiError ? caught.code : "";
      // Pubblicazione sospesa: il messaggio del server ha la data di fine.
      const suspended = caught instanceof ApiError && code === "account.posting_restricted" ? `${caught.title}.` : null;
      setError(suspended ?? PUBLISH_ERRORS[code] ?? "Non riusciamo a pubblicare. Controlla la connessione e riprova.");
    } finally {
      setPublishing(false);
    }
  };

  return (
    <SafeAreaView style={styles.safe} edges={["top", "bottom"]}>
      <View style={styles.header}>
        <IconButton label="Annulla" onPress={() => (draftHasContent(draft) ? setConfirmDiscard(true) : close())}>
          <IconClose color={colors.text} size={22} />
        </IconButton>
        <RNText style={styles.title} role="heading">
          Nuovo fit
        </RNText>
        <Button label="Pubblica" size="sm" onPress={() => void publish()} disabled={!check.ok} loading={publishing} hint={check.ok ? undefined : check.reason} />
      </View>
      {!check.ok && draft.photos.length > 0 ? (
        <RNText style={styles.status} aria-live="polite">
          {check.reason}
        </RNText>
      ) : null}

      <KeyboardAvoidingView style={styles.flex} behavior={Platform.OS === "ios" ? "padding" : undefined}>
        <ScrollView contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled" showsVerticalScrollIndicator={false}>
          <Section title="1 · DALLA GALLERIA" aside={`${draft.photos.length} di ${MAX_PHOTOS}`} />
          <PhotoStrip
            photos={draft.photos}
            onAdd={() => void pick()}
            onRemove={removePhoto}
            onMove={draft.movePhoto}
            onRetry={retryPhoto}
          />
          <RNText style={styles.note}>L'ordine qui è l'ordine del carosello. Fino a 10 foto.</RNText>

          <Section title="2 · STILE DEL FIT" />
          <View style={styles.styles} role="radiogroup" aria-label="Stile del fit">
            {styleOptions.map((style: StyleCard) => {
              const selected = draft.style === style.slug;
              return (
                <Pressable
                  key={style.slug}
                  role="radio"
                  aria-checked={selected}
                  aria-label={style.name}
                  onPress={() => draft.setStyle(selected ? null : style.slug)}
                  style={[styles.styleChip, selected ? { backgroundColor: style.tone, borderColor: colors.text } : null]}
                >
                  <RNText style={styles.styleText}>{style.name}</RNText>
                </Pressable>
              );
            })}
          </View>
          <RNText style={styles.note}>Un solo stile per post. I primi votanti confermano se è davvero quello.</RNText>

          <Section title="3 · I CAPI" />
          <View style={styles.items}>
            {draft.items.map((item, index) => (
              <ItemCard
                key={item.key}
                index={index}
                item={item}
                photos={draft.photos}
                canRemove={draft.items.length > 1 || Boolean(item.brand || item.name || item.price || item.link || item.pin)}
                onChange={(patch) => draft.updateItem(item.key, patch)}
                onRemove={() => draft.removeItem(item.key)}
              />
            ))}
          </View>
          {draft.items.length < MAX_ITEMS ? (
            <Pressable role="button" onPress={draft.addItem} style={({ pressed }) => [styles.addItem, pressed ? styles.pressed : null]}>
              <RNText style={styles.addItemText}>+ Aggiungi un capo</RNText>
            </Pressable>
          ) : null}
          <RNText style={styles.note}>Segna ogni capo sulla foto: sul fit compare un punto con il brand. Accettiamo solo link https. Ogni link viene controllato prima di essere mostrato.</RNText>

          <Section title="4 · DIDASCALIA" aside={`${draft.caption.length}/${CAPTION_MAX}`} />
          <TextInput
            aria-label="Didascalia"
            value={draft.caption}
            onChangeText={draft.setCaption}
            placeholder="Dove l'hai indossato?"
            placeholderTextColor={colors.textTertiary}
            selectionColor={colors.accent}
            maxLength={CAPTION_MAX}
            multiline
            style={styles.caption}
          />

          {error ? (
            <RNText style={styles.error} role="alert">
              {error}
            </RNText>
          ) : null}

          <View style={styles.privacy}>
            <IconLock color={colors.textTertiary} />
            <RNText style={styles.privacyText}>
              Togliamo in automatico posizione GPS, modello del telefono e ogni altro dato nascosto dalle foto prima di
              pubblicarle.
            </RNText>
          </View>
        </ScrollView>
      </KeyboardAvoidingView>

      <Sheet visible={confirmDiscard} title="Scartare il fit?" onClose={() => setConfirmDiscard(false)}>
        <RNText style={styles.sheetText}>Foto, capi e didascalia andranno persi.</RNText>
        <Button label="Scarta" variant="danger" onPress={discard} fullWidth />
        <Button label="Continua a modificare" variant="secondary" onPress={() => setConfirmDiscard(false)} fullWidth />
      </Sheet>
    </SafeAreaView>
  );
}

function Section({ title, aside }: { title: string; aside?: string }) {
  return (
    <View style={styles.section}>
      <RNText style={styles.sectionTitle}>{title}</RNText>
      {aside ? <RNText style={styles.sectionAside}>{aside}</RNText> : null}
    </View>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.background },
  flex: { flex: 1 },
  header: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingLeft: spacing[1],
    paddingRight: spacing[3],
    paddingVertical: spacing[2],
    borderBottomWidth: 1,
    borderBottomColor: colors.divider,
  },
  title: { fontFamily: fonts.display, fontSize: 22, color: colors.text },
  status: {
    fontFamily: fonts.ui,
    fontSize: 12,
    color: colors.textSecondary,
    textAlign: "center",
    paddingVertical: 6,
    backgroundColor: colors.surface,
  },
  content: { padding: spacing[4], paddingBottom: spacing[8] },
  section: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "baseline",
    marginTop: 26,
    marginBottom: 10,
  },
  sectionTitle: { fontFamily: fonts.mono, fontSize: 11, letterSpacing: 11 * 0.14, color: colors.textSecondary },
  sectionAside: { fontFamily: fonts.ui, fontSize: 12, color: colors.textTertiary },
  note: { fontFamily: fonts.ui, fontSize: 12, lineHeight: 17, color: colors.textTertiary, marginTop: spacing[2] },
  styles: { flexDirection: "row", flexWrap: "wrap", gap: spacing[2] },
  styleChip: {
    height: 36,
    paddingHorizontal: 14,
    borderRadius: radii.pill,
    borderWidth: 1,
    borderColor: colors.border,
    justifyContent: "center",
  },
  styleText: { fontFamily: fonts.display, fontSize: 15, color: colors.text },
  items: { gap: 10 },
  addItem: {
    height: 46,
    marginTop: 10,
    borderRadius: 14,
    borderWidth: 1,
    borderStyle: "dashed",
    borderColor: "#3A3A40",
    alignItems: "center",
    justifyContent: "center",
  },
  addItemText: { fontFamily: fonts.uiSemiBold, fontSize: 14, color: colors.text },
  pressed: { opacity: 0.7 },
  caption: {
    minHeight: 50,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.surface,
    color: colors.text,
    paddingHorizontal: 14,
    paddingVertical: 14,
    fontFamily: fonts.ui,
    fontSize: fontSizes.bodyLarge,
    outlineWidth: 0,
  },
  error: { fontFamily: fonts.ui, fontSize: 13, lineHeight: 19, color: colors.danger, marginTop: spacing[4] },
  privacy: { flexDirection: "row", gap: 10, alignItems: "flex-start", marginTop: 20 },
  privacyText: { flex: 1, fontFamily: fonts.ui, fontSize: 12, lineHeight: 18, color: colors.textTertiary },
  sheetText: { fontFamily: fonts.ui, fontSize: 14, color: colors.textSecondary, marginBottom: spacing[2] },
});
