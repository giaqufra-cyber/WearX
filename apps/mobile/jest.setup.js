// La memoria del telefono (AsyncStorage) non esiste sotto Jest: si usa la sua finta ufficiale.
jest.mock("@react-native-async-storage/async-storage", () =>
  require("@react-native-async-storage/async-storage/jest/async-storage-mock"),
);
