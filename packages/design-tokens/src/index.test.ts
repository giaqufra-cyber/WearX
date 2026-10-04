import { test } from "node:test";
import assert from "node:assert/strict";
import { colors, voteMood } from "./index.ts";

test("le fasce del voto coprono 1..100 senza buchi", () => {
  assert.equal(voteMood(1), "Non fa per me");
  assert.equal(voteMood(20), "Non fa per me");
  assert.equal(voteMood(21), "Così così");
  assert.equal(voteMood(70), "Bel fit");
  assert.equal(voteMood(95), "Fit pazzesco");
  assert.equal(voteMood(96), "Icona di stile");
  assert.equal(voteMood(100), "Icona di stile");
});

test("voti fuori intervallo o non interi vengono rifiutati", () => {
  for (const bad of [0, 101, -5, 50.5, Number.NaN]) {
    assert.throws(() => voteMood(bad), RangeError);
  }
});

test("i colori sono esadecimali a 6 cifre o rgba", () => {
  for (const [name, value] of Object.entries(colors)) {
    assert.match(value, /^(#[0-9A-F]{6}|rgba\(.+\))$/, name);
  }
});
