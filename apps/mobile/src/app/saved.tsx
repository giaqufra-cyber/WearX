import { TileGrid } from "@/features/saved/TileGrid";
import { useSavedFits } from "@/features/saved/api";

/** I fit degli altri che hai salvato (seduta 32). Li vedi solo tu. */
export default function SavedScreen() {
  const saved = useSavedFits();
  return (
    <TileGrid
      title="Salvati"
      query={saved}
      own={false}
      empty={{
        title: "Ancora nessun fit salvato",
        body: "Tocca il segnalibro su un fit per ritrovarlo qui. Lo vedi solo tu.",
      }}
    />
  );
}
