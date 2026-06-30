import type { TestSpec } from "../spec/testSpec.ts";
import type { TocRow } from "./types.ts";

export interface AssertionResult {
  label: string;
  expectedLevel: number;
  actualLevel: number | null;
  pass: boolean;
}

export interface VerifyResult {
  pass: boolean;
  results: AssertionResult[];
}

export function verifyToc(spec: TestSpec, rows: TocRow[]): VerifyResult {
  const byLabel = new Map(rows.map((r) => [r.label, r.level] as const));
  const results = spec.expectedAssertions.map((a) => {
    const actualLevel = byLabel.has(a.label) ? byLabel.get(a.label)! : null;
    return {
      label: a.label,
      expectedLevel: a.expectedLevel,
      actualLevel,
      pass: actualLevel === a.expectedLevel,
    };
  });
  return { pass: results.every((r) => r.pass), results };
}
