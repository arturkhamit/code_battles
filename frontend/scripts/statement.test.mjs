// Run: node scripts/statement.test.mjs (this Node has no built-in type stripping, so transpile with typescript)
import assert from "node:assert/strict"
import { readFileSync } from "node:fs"
import ts from "typescript"

const src = readFileSync(new URL("../src/lib/statement.ts", import.meta.url), "utf8")
const js = ts.transpileModule(src, { compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 } }).outputText
const { stripSamples } = await import("data:text/javascript," + encodeURIComponent(js))

// Codeforces, no Note (task 761)
const cf =
  "Find it.\n\nInput\n\nThe only line\n\nOutput\n\nOutput the n-th\n\nExamples\n\nInput\n\n2\n\nOutput\n\n5\n\nInput\n\n5\n\nOutput\n\n35"
assert.equal(stripSamples(cf, true), "Find it.\n\nInput\n\nThe only line\n\nOutput\n\nOutput the n-th\n\n")
// no public tests: keep everything
assert.equal(stripSamples(cf, false), cf)

// CodeChef "Example" + "Input:" then "Explanation"
const cc = "Do it.\n\nConstraints\n\n1 ≤ T ≤ 10\n\n\nExample\nInput:\n3\n\nOutput:\nYES\n\n \n\nExplanation\nExample is self-explanatory."
assert.equal(stripSamples(cc, true), "Do it.\n\nConstraints\n\n1 ≤ T ≤ 10\n\n\nExplanation\nExample is self-explanatory.")

// Examples followed by Note
const note = "S.\n\nOutput\n\nPrint.\n\nExamples\n\nInput\n\n1\n\nOutput\n\n2\n\nNote\n\nIn the first example..."
assert.equal(stripSamples(note, true), "S.\n\nOutput\n\nPrint.\n\nNote\n\nIn the first example...")

// AtCoder/Aizu "Sample Input 1 / Sample Output 1"
const aizu = "T.\n\nInput\n\nN\n\nOutput\n\nAns\n\nSample Input 1\n\n3\n\nSample Output 1\n\n6\n\nSample Input 2\n\n1\n\nSample Output 2\n\n1"
assert.equal(stripSamples(aizu, true), "T.\n\nInput\n\nN\n\nOutput\n\nAns\n\n")

// no samples at all; "example" inside a sentence is not a heading
const plain = "For example, x.\n\nInput\n\nN\n\nOutput\n\nM"
assert.equal(stripSamples(plain, true), plain)

console.log("statement.test: ok")
