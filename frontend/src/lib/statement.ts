// code_contests statements embed their own samples; the page shows public_tests separately.
// Start: an "Example(s)" / "Sample(s)" / "Sample Input/Output [N]" heading on its own line.
const SAMPLES_START = /^[ \t]*(examples?|samples?|sample (input|output)( \d+)?( for input \d+)?)[ \t]*:?[ \t]*$/im
// End: the next Note/Explanation heading, which is kept.
const SAMPLES_END = /^[ \t]*(notes?|explanation)[ \t]*:?[ \t]*$/im

/** Cut the in-text samples section; keep it when there are no public tests to show instead. */
export const stripSamples = (text: string, hasPublicTests: boolean): string => {
  if (!hasPublicTests) return text
  const start = text.search(SAMPLES_START)
  if (start < 0) return text
  const end = text.slice(start).search(SAMPLES_END)
  return text.slice(0, start) + (end < 0 ? "" : text.slice(start + end))
}
