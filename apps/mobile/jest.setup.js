// La memoria del telefono (AsyncStorage) non esiste sotto Jest: si usa la sua finta ufficiale.
jest.mock("@react-native-async-storage/async-storage", () =>
  require("@react-native-async-storage/async-storage/jest/async-storage-mock"),
);

// Nei test il telefono è in italiano: i testi attesi sono quelli italiani (seduta 33).
jest.mock("expo-localization", () => ({
  getLocales: () => [{ languageCode: "it", languageTag: "it-IT" }],
}));
