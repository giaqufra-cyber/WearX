import { TileGrid } from "@/features/saved/TileGrid";
import { useSavedFits } from "@/features/saved/api";
import { t } from "@/lib/i18n";

/** I fit degli altri che hai salvato (seduta 32). Li vedi solo tu. */
export default function SavedScreen() {
  const saved = useSavedFits();
  return (
    <TileGrid
      title={t("Salvati")}
      query={saved}
      own={false}
      empty={{
        title: t("Ancora nessun fit salvato"),
        body: t("Tocca il segnalibro su un fit per ritrovarlo qui. Lo vedi solo tu."),
      }}
    />
  );
}
