import { readFileSync } from "node:fs";
import { z } from "zod";

export const AssertionSchema = z.strictObject({
  label: z.string().min(1),
  expectedLevel: z.number().int().min(0),
});

export const ReproContentSchema = z.strictObject({
  sectionTitle: z.string().min(1),
  narrativeHtml: z.string().min(1),
});

export const TestSpecSchema = z.strictObject({
  ticketKey: z.string().regex(/^[A-Z]+-\d+$/),
  reproContent: ReproContentSchema,
  expectedAssertions: z.array(AssertionSchema).min(1),
});

export type TestSpec = z.infer<typeof TestSpecSchema>;

export function loadSpec(path: string): TestSpec {
  const raw = readFileSync(path, "utf8");
  const parsed = TestSpecSchema.safeParse(JSON.parse(raw));
  if (!parsed.success) {
    throw new Error(`Invalid TestSpec at ${path}: ${parsed.error.message}`);
  }
  return parsed.data;
}
