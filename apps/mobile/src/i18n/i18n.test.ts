/**
 * Traduzioni (seduta 33): ogni testo passato a t(), tn() o N_() ha la sua traduzione inglese,
 * con gli stessi segnaposto; il dizionario non tiene testi che il codice non usa più.
 */
import fs from "fs";
import path from "path";

import { EN } from "@/i18n/en";
import { formatCount, language, locale, setLanguageForTests, t, tn } from "@/lib/i18n";

// eslint-disable-next-line @typescript-eslint/no-require-imports
const parser = require("@babel/parser") as typeof import("@babel/parser");

type Node = { type: string; [key: string]: unknown };

const SRC = path.resolve(__dirname, "..");

function sourceFiles(dir: string): string[] {
  return fs.readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) return sourceFiles(full);
    return /\.tsx?$/.test(entry.name) && !/\.test\./.test(entry.name) ? [full] : [];
  });
}

/** Le stringhe che possono arrivare a t(): letterali, rami di ternari, lato destro di ?? e ||. */
function literals(node: Node | undefined): string[] {
  if (!node) return [];
  if (node.type === "StringLiteral") return [node.value as string];
  if (node.type === "ConditionalExpression") return [...literals(node.consequent as Node), ...literals(node.alternate as Node)];
  if (node.type === "LogicalExpression") return literals(node.right as Node);
  return [];
}

function usedKeys(): Map<string, string> {
  const keys = new Map<string, string>();
  for (const file of sourceFiles(SRC)) {
    const ast = parser.parse(fs.readFileSync(file, "utf8"), { sourceType: "module", plugins: ["jsx", "typescript"] });
    const walk = (node: unknown): void => {
      if (!node || typeof node !== "object") return;
      if (Array.isArray(node)) return node.forEach(walk);
      const n = node as Node;
      if (typeof n.type !== "string") return;
      const callee = n.callee as Node | undefined;
      if (n.type === "CallExpression" && callee?.type === "Identifier" && ["t", "tn", "N_"].includes(callee.name as string)) {
        const args = n.arguments as Node[];
        const texts = callee.name === "tn" ? [args[1], args[2]] : [args[0]];
        for (const arg of texts) for (const key of literals(arg)) keys.set(key, path.relative(SRC, file));
      }
      for (const [k, v] of Object.entries(n)) if (k !== "loc" && k !== "start" && k !== "end") walk(v);
    };
    walk(ast.program);
  }
  return keys;
}

const placeholders = (text: string) => [...text.matchAll(/\{(\w+)\}/g)].map((m) => m[1]).sort();

describe("dizionario inglese", () => {
  const keys = usedKeys();

  test("ogni testo dell'app è tradotto", () => {
    const missing = [...keys].filter(([key]) => !(key in EN)).map(([key, file]) => `${file}: ${key}`);
    expect(missing).toEqual([]);
  });

  test("stessi segnaposto in italiano e in inglese", () => {
    const wrong = Object.entries(EN).filter(([it, en]) => placeholders(it).join() !== placeholders(en).join());
    expect(wrong).toEqual([]);
  });

  test("nessuna traduzione inutilizzata", () => {
    expect(Object.keys(EN).filter((key) => !keys.has(key))).toEqual([]);
  });
});

describe("t() e tn()", () => {
  afterEach(() => setLanguageForTests("it"));

  test("in italiano il testo resta com'è; in inglese si traduce, con i segnaposto", () => {
    expect(language()).toBe("it");
    expect(t("Ora segui @{nickname}.", { nickname: "giulia" })).toBe("Ora segui @giulia.");
    setLanguageForTests("en");
    expect(t("Ora segui @{nickname}.", { nickname: "giulia" })).toBe("You now follow @giulia.");
    expect(t("Testo che non c'è")).toBe("Testo che non c'è"); // senza traduzione resta l'italiano
    expect(locale()).toBe("en-GB");
  });

  test("singolare e plurale, con le migliaia nella lingua giusta", () => {
    expect(tn(1, "{count} voto", "{count} voti")).toBe("1 voto");
    expect(tn(1200, "{count} voto", "{count} voti")).toBe("1.200 voti");
    setLanguageForTests("en");
    expect(tn(1, "{count} voto", "{count} voti")).toBe("1 score");
    expect(tn(1200, "{count} voto", "{count} voti")).toBe("1,200 scores");
    expect(formatCount(1234567)).toBe("1,234,567");
  });
});
