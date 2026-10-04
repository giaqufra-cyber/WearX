import { ageOn, nicknameHint, passwordScore } from "./validation";

describe("nicknameHint", () => {
  test.each([
    ["", "empty"],
    ["ab", "invalid"],
    ["con spazio", "invalid"],
    [".punto", "invalid"],
    ["fine_", "invalid"],
    ["due..punti", "invalid"],
    ["wearx_team", "reserved"],
    ["w.e.a.r.x", "reserved"],
    ["il_vero_admin", "reserved"],
    ["Nico.Atelier", "ok"],
    ["fit_2026", "ok"],
  ])("%s → %s", (input, expected) => {
    expect(nicknameHint(input)).toBe(expected);
  });
});

describe("passwordScore", () => {
  test.each([
    ["", 0],
    ["abcdefghij", 1],
    ["abcdefghi1", 2],
    ["abcdefgh1!", 3],
    ["Abcdefgh1!", 4],
    ["Ab1!", 3],
  ])("%s → %i", (pw, score) => {
    expect(passwordScore(pw)).toBe(score);
  });
});

describe("ageOn", () => {
  const today = new Date(2026, 9, 4); // 4 ottobre 2026

  test("compleanno già passato quest'anno", () => {
    expect(ageOn(1, 1, 2010, today)).toBe(16);
  });

  test("compleanno oggi conta", () => {
    expect(ageOn(4, 10, 2010, today)).toBe(16);
  });

  test("compleanno domani: ancora 15 anni", () => {
    expect(ageOn(5, 10, 2010, today)).toBe(15);
  });

  test("date inesistenti", () => {
    expect(ageOn(31, 2, 2005, today)).toBeNull();
    expect(ageOn(29, 2, 2005, today)).toBeNull();
    expect(ageOn(0, 5, 2005, today)).toBeNull();
    expect(ageOn(10, 13, 2005, today)).toBeNull();
  });

  test("29 febbraio in un anno bisestile è valido", () => {
    expect(ageOn(29, 2, 2008, today)).toBe(18);
  });

  test("date nel futuro o troppo vecchie", () => {
    expect(ageOn(1, 1, 2030, today)).toBeNull();
    expect(ageOn(1, 1, 1850, today)).toBeNull();
  });
});
