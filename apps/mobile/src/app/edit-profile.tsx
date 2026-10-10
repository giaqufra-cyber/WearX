import type { ProfileUpdate } from "@wearx/api-types";
import { colors, fonts, fontSizes, radii, spacing } from "@wearx/design-tokens";
import * as ImagePicker from "expo-image-picker";
import { router } from "expo-router";
import { useEffect, useRef, useState } from "react";
import { KeyboardAvoidingView, Platform, ScrollView, StyleSheet, Text, TextInput, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { useAuth } from "@/features/auth/AuthProvider";
import { deleteUpload, realUploadDeps } from "@/features/create/deps";
import { uploadPhoto } from "@/features/create/uploader";
import { BIO_MAX_CHARS, bioLength, bioProblem, saveError, useSaveProfile } from "@/features/profile/edit";
import { Avatar } from "@/ui/Avatar";
import { Button } from "@/ui/Button";
import { TopBar } from "@/ui/TopBar";
import { useToast } from "@/ui/Toast";

const AVATAR = 112;

type Photo =
  | { kind: "same" }
  | { kind: "remove" }
  | { kind: "new"; uri: string; status: "uploading" | "ready" | "error"; progress: number; uploadId?: string; message?: string };

/** Modifica profilo: foto profilo e bio. Si salva tutto insieme con "Salva". */
export default function EditProfileScreen() {
  const { profile, session } = useAuth();
  const toast = useToast();
  const save = useSaveProfile();
  const [bio, setBio] = useState(profile?.bio ?? "");
  const [photo, setPhoto] = useState<Photo>({ kind: "same" });
  const [error, setError] = useState<string | null>(null);
  const abort = useRef<AbortController | null>(null);
  // Caricamento fatto ma non salvato: si cancella uscendo (non resta nell'archivio).
  const unsaved = useRef<string | null>(null);
  // Il token cambia quando si rinnova l'accesso: l'ultimo serve solo per cancellare uscendo.
  const tokenRef = useRef(session?.access_token);
  tokenRef.current = session?.access_token;

  useEffect(
    () => () => {
      abort.current?.abort();
      if (unsaved.current && tokenRef.current) void deleteUpload(tokenRef.current, unsaved.current);
    },
    [],
  );

  if (!profile || !session) return null;

  const token = session.access_token;
  const problem = bioProblem(bio);
  const bioChanged = (bio.trim() || null) !== (profile.bio ?? null);
  const photoChanged = photo.kind === "remove" || (photo.kind === "new" && photo.status === "ready");
  const uploading = photo.kind === "new" && photo.status === "uploading";
  const hasPhoto = photo.kind === "new" || (photo.kind === "same" && Boolean(profile.avatar));

  const discardUpload = () => {
    abort.current?.abort();
    if (unsaved.current) void deleteUpload(token, unsaved.current);
    unsaved.current = null;
  };

  const pick = async () => {
    const result = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ["images"],
      allowsEditing: true,
      aspect: [1, 1],
      quality: 1,
      exif: false,
    });
    const asset = result.canceled ? undefined : result.assets?.[0];
    if (!asset) return;
    discardUpload();
    setError(null);
    const controller = new AbortController();
    abort.current = controller;
    setPhoto({ kind: "new", uri: asset.uri, status: "uploading", progress: 0 });
    await uploadPhoto(
      { uri: asset.uri, width: asset.width, height: asset.height },
      realUploadDeps(token),
      (u) => {
        if (controller.signal.aborted) return;
        if (u.uploadId) unsaved.current = u.uploadId;
        setPhoto((current) => {
          if (current.kind !== "new" || current.uri !== asset.uri) return current;
          if (u.status === "ready") return { ...current, status: "ready", progress: 1, uploadId: u.uploadId };
          if (u.status === "error" || u.status === "rejected") {
            return { ...current, status: "error", message: u.message ?? "Caricamento non riuscito." };
          }
          return { ...current, progress: u.progress ?? current.progress };
        });
      },
      controller.signal,
    );
  };

  const removePhoto = () => {
    discardUpload();
    setError(null);
    setPhoto(profile.avatar ? { kind: "remove" } : { kind: "same" });
  };

  const submit = () => {
    const patch: ProfileUpdate = {};
    if (bioChanged) patch.bio = bio.trim() || null;
    if (photo.kind === "remove") patch.avatar = null;
    if (photo.kind === "new" && photo.status === "ready") patch.avatar = photo.uploadId ?? null;
    setError(null);
    save.mutate(patch, {
      onSuccess: () => {
        unsaved.current = null;
        toast.show("Profilo aggiornato.");
        if (router.canGoBack()) router.back();
        else router.replace("/profile");
      },
      onError: (e) => setError(saveError(e)),
    });
  };

  const status =
    photo.kind === "new"
      ? photo.status === "uploading"
        ? `Carichiamo la foto… ${Math.round(photo.progress * 100)}%`
        : photo.status === "error"
          ? photo.message
          : "Foto pronta: tocca Salva."
      : photo.kind === "remove"
        ? "Foto tolta: tocca Salva. Tornano le iniziali."
        : null;

  return (
    <SafeAreaView style={styles.safe} edges={["top"]}>
      <TopBar
        title="Modifica profilo"
        right={
          <View style={styles.save}>
            <Button
              label="Salva"
              size="sm"
              onPress={submit}
              disabled={(!bioChanged && !photoChanged) || Boolean(problem) || uploading}
              loading={save.isPending}
            />
          </View>
        }
      />
      <KeyboardAvoidingView style={styles.flex} behavior={Platform.OS === "ios" ? "padding" : undefined}>
        <ScrollView contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled">
          <View style={styles.photo}>
            <Avatar
              nickname={profile.nickname}
              avatar={photo.kind === "same" ? profile.avatar : null}
              localUri={photo.kind === "new" ? photo.uri : null}
              size={AVATAR}
            />
            <View style={styles.photoButtons}>
              <Button
                label={hasPhoto ? "Cambia foto" : "Scegli una foto"}
                variant="secondary"
                size="sm"
                onPress={() => void pick()}
              />
              {hasPhoto ? <Button label="Togli foto" variant="ghost" size="sm" onPress={removePhoto} /> : null}
            </View>
            {status ? (
              <Text style={[styles.status, photo.kind === "new" && photo.status === "error" && styles.error]} aria-live="polite">
                {status}
              </Text>
            ) : null}
          </View>

          <View style={styles.field}>
            <View style={styles.labelRow}>
              <Text style={styles.label}>BIO</Text>
              <Text style={[styles.label, problem ? styles.error : null]}>
                {bioLength(bio)}/{BIO_MAX_CHARS}
              </Text>
            </View>
            <TextInput
              aria-label="Bio"
              value={bio}
              onChangeText={setBio}
              placeholder="Due righe su di te e sul tuo stile"
              placeholderTextColor={colors.textTertiary}
              selectionColor={colors.accent}
              multiline
              maxLength={BIO_MAX_CHARS * 2}
              aria-invalid={Boolean(problem)}
              style={[styles.bio, problem ? styles.bioError : null]}
            />
            <Text style={[styles.hint, problem ? styles.error : null]} role={problem ? "alert" : undefined}>
              {problem ?? "Fino a 4 righe. La vede chi apre il tuo profilo."}
            </Text>
          </View>

          <View style={styles.field}>
            <Text style={styles.label}>NICKNAME</Text>
            <Text style={styles.value}>@{profile.nickname}</Text>
            <Text style={styles.hint}>Per ora il nickname non si può cambiare.</Text>
          </View>


          {error ? (
            <Text style={[styles.status, styles.error]} role="alert">
              {error}
            </Text>
          ) : null}
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.background },
  flex: { flex: 1 },
  save: { paddingRight: spacing[3] },
  content: { padding: spacing[5], gap: spacing[6], maxWidth: 560, width: "100%", alignSelf: "center" },
  photo: { alignItems: "center", gap: spacing[3] },
  photoButtons: { flexDirection: "row", gap: spacing[2] },
  status: { fontFamily: fonts.ui, fontSize: 13, lineHeight: 18, color: colors.textSecondary, textAlign: "center" },
  error: { color: colors.danger },
  field: { gap: spacing[2] },
  labelRow: { flexDirection: "row", justifyContent: "space-between" },
  label: { fontFamily: fonts.mono, fontSize: 11, letterSpacing: 1.4, color: colors.textSecondary },
  bio: {
    minHeight: 112,
    borderRadius: radii.md,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.surfaceRaised,
    color: colors.text,
    padding: 14,
    fontFamily: fonts.ui,
    fontSize: fontSizes.body,
    lineHeight: 22,
    textAlignVertical: "top",
    outlineWidth: 0,
  },
  bioError: { borderColor: colors.dangerStrong },
  hint: { fontFamily: fonts.ui, fontSize: 12, lineHeight: 17, color: colors.textTertiary },
  value: { fontFamily: fonts.uiBold, fontSize: 16, color: colors.text },
  note: { fontFamily: fonts.ui, fontSize: 13, lineHeight: 19, color: colors.textSecondary },
});
