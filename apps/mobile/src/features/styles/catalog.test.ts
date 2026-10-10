import { fold, inCategory, searchStyles, styleChoices } from "@/features/styles/catalog";

const s = (slug: string, name: string, tagline = "", category = "stili") => ({ slug, name, tagline, category });
// In ordine di iscritti, come li manda il server.
const ALL = [
  s("streetwear", "Streetwear", "Sneakers, hoodie, drop"),
  s("gala", "Galà", "Black tie", "occasioni"),
  s("surf", "Surf", "Mute, board shorts", "sport"),
  s("sci-snowboard", "Sci e snowboard", "Giacche tecniche", "sport"),
  s("gioielli", "Gioielli", "Catene, anelli", "accessori"),
  s("emo", "Emo", "Frangia, nero", "sottoculture"),
];

describe("catalogo degli stili", () => {
  test("fold: minuscole e senza accenti", () => {
    expect(fold("  Galà ")).toBe("gala");
    expect(fold("CAFÉ")).toBe("cafe");
  });

  test("categoria: filtra senza cambiare l'ordine", () => {
    expect(inCategory(ALL, "sport").map((x) => x.slug)).toEqual(["surf", "sci-snowboard"]);
    expect(inCategory(ALL, null)).toHaveLength(ALL.length);
  });

  test("ricerca: nome, descrizione e categoria; prima chi inizia con il testo", () => {
    expect(searchStyles(ALL, "gala").map((x) => x.slug)).toEqual(["gala"]);
    expect(searchStyles(ALL, "snow").map((x) => x.slug)).toEqual(["sci-snowboard"]);
    expect(searchStyles(ALL, "sport").map((x) => x.slug)).toEqual(["surf", "sci-snowboard"]);
    expect(searchStyles(ALL, "sne").map((x) => x.slug)).toEqual(["streetwear"]);
    expect(searchStyles(ALL, "s").slice(0, 3).map((x) => x.slug)).toEqual(["streetwear", "surf", "sci-snowboard"]);
    expect(searchStyles(ALL, "zzz")).toEqual([]);
  });

  test("scelta quando pubblichi: scelto, i tuoi, poi i più seguiti; con la ricerca tutto il catalogo", () => {
    const mine = [s("emo", "Emo")];
    expect(styleChoices(ALL, mine, "", null, 3)).toEqual({
      items: [mine[0], ALL[0], ALL[1]],
      more: 3,
    });
    expect(styleChoices(ALL, mine, "", "gioielli", 2).items.map((x) => x.slug)).toEqual(["gioielli", "emo"]);
    expect(styleChoices(ALL, mine, "gio", null, 1)).toEqual({ items: [ALL[4]], more: 0 });
  });
});
