// Lists t()/plural() keys in src/ without a German entry in src/lib/i18n/de/*.ts, and German entries nothing uses.
// Conventions this relies on: keys are double-quoted literals; dictionary lines look like  "English": "Deutsch",
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";

const files = (dir) => readdirSync(dir).flatMap((f) => (statSync(join(dir, f)).isDirectory() ? files(join(dir, f)) : [join(dir, f)]));
const STR = String.raw`"((?:[^"\\]|\\.)*)"`;
const used = new Map();
for (const f of files("src").filter((f) => /\.(svelte|ts)$/.test(f) && !f.includes(join("lib", "i18n")))) {
  const src = readFileSync(f, "utf8");
  for (const re of [new RegExp(String.raw`\bt\(\s*${STR}`, "g"), new RegExp(String.raw`\bplural\([^,]+,\s*${STR}\s*,\s*${STR}`, "g")])
    for (const m of src.matchAll(re)) for (const k of m.slice(1).filter(Boolean)) used.set(JSON.parse(`"${k}"`), f);
}
const de = new Map();
for (const f of files(join("src", "lib", "i18n", "de")).filter((f) => f.endsWith(".ts"))) {
  for (const m of readFileSync(f, "utf8").matchAll(new RegExp(String.raw`^\s*${STR}\s*:\s*${STR},?\s*$`, "gm"))) {
    const key = JSON.parse(`"${m[1]}"`);
    if (de.has(key)) console.log(`duplicate: ${JSON.stringify(key)} in ${f} and ${de.get(key)}`);
    de.set(key, f);
  }
}
const missing = [...used].filter(([k]) => !de.has(k));
const unused = [...de].filter(([k]) => !used.has(k));
for (const [k, f] of missing) console.log(`missing  ${f}: ${JSON.stringify(k)}`);
for (const [k, f] of unused) console.log(`unused   ${f}: ${JSON.stringify(k)}`);
console.log(`${used.size} keys, ${de.size} German entries, ${missing.length} missing, ${unused.length} unused`);
process.exit(missing.length ? 1 : 0);
