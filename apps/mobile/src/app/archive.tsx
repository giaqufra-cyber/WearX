import { colors, fonts } from "@wearx/design-tokens";
import { StyleSheet, Text } from "react-native";

import { TileGrid } from "@/features/saved/TileGrid";
import { useArchivedFits } from "@/features/saved/api";

/** I tuoi fit archiviati (seduta 32): spariti dal profilo, non cancellati. */
export default function ArchiveScreen() {
  const archived = useArchivedFits();
  const some = (archived.data?.pages[0]?.items.length ?? 0) > 0;
  return (
    <TileGrid
      title="Archivio"
      query={archived}
      own
      intro={
        some ? (
          <Text style={styles.intro}>
            Li vedi solo tu. Apri un fit e scegli «Rimetti nel profilo» per farlo tornare al suo posto.
          </Text>
        ) : undefined
      }
      empty={{
        title: "L'archivio è vuoto",
        body: "Apri un tuo fit e scegli «Archivia»: sparisce dal profilo senza eliminarlo.",
      }}
    />
  );
}

const styles = StyleSheet.create({
  intro: { fontFamily: fonts.ui, fontSize: 13, lineHeight: 18, color: colors.textSecondary },
});
