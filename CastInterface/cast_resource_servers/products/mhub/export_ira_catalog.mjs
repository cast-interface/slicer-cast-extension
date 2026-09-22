/**
 * Export slim IRA MHub catalog (mhub-models.ts) from the vendored skill
 * summary, enriched with per-model GitHub / website / citation URLs.
 *
 * Run from slicer-cast-extension CastInterface/:
 *   node cast_resource_servers/products/mhub/export_ira_catalog.mjs
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const summaryPath = path.join(__dirname, "MHubSkill", "data", "models_summary.json");
const outPath = path.resolve(
  __dirname,
  "../../../../../../pw46/SlicerLive/render/demos/ira/mhub-models.ts"
);

function canonBodyPart(raw) {
  const s = String(raw || "").trim();
  if (!s) return "";
  const u = s.toUpperCase().replace(/[\s_-]+/g, "");
  const map = {
    WHOLEBODY: "WHOLEBODY",
    CHEST: "Chest",
    ABDOMEN: "Abdomen",
    PROSTATE: "Prostate",
    KIDNEY: "Kidney",
    LIVER: "Liver",
    LUNG: "Lung",
    SPINE: "Spine",
    BREAST: "Breast",
  };
  return map[u] || s.charAt(0).toUpperCase() + s.slice(1).toLowerCase();
}

function extractCiteUrl(cite) {
  const text = String(cite || "");
  const doi = text.match(
    /https?:\/\/(?:dx\.)?doi\.org\/[^\s)\]>",]+/i
  );
  if (doi) return doi[0].replace(/[.,;]+$/, "");
  const arxivAbs = text.match(/https?:\/\/arxiv\.org\/abs\/[^\s)\]>",]+/i);
  if (arxivAbs) return arxivAbs[0].replace(/[.,;]+$/, "");
  const arxivId = text.match(/arXiv[:\s]+(\d{4}\.\d{4,5})(?:v\d+)?/i);
  if (arxivId) return `https://arxiv.org/abs/${arxivId[1]}`;
  const bareDoi = text.match(/\b10\.\d{4,9}\/[^\s)\]>",]+/i);
  if (bareDoi) return `https://doi.org/${bareDoi[0].replace(/[.,;]+$/, "")}`;
  return "";
}

async function fetchMeta(name) {
  const url = `https://raw.githubusercontent.com/MHubAI/models/main/models/${encodeURIComponent(name)}/meta.json`;
  try {
    const res = await fetch(url);
    if (!res.ok) {
      console.warn(`meta miss ${name}: HTTP ${res.status}`);
      return null;
    }
    return await res.json();
  } catch (err) {
    console.warn(`meta miss ${name}:`, err instanceof Error ? err.message : err);
    return null;
  }
}

function escapeTsString(value) {
  return JSON.stringify(String(value ?? ""));
}

const summary = JSON.parse(fs.readFileSync(summaryPath, "utf8"));
const entries = Object.entries(summary.models || {});
entries.sort((a, b) =>
  String(a[1].label || a[0]).localeCompare(String(b[1].label || b[0]))
);

const models = [];
for (const [name, info] of entries) {
  const bodyParts = [
    ...new Set(
      (Array.isArray(info.inputs) ? info.inputs : [])
        .map((inp) => canonBodyPart(inp?.bodypartexamined))
        .filter(Boolean)
    ),
  ].sort((a, b) => a.localeCompare(b));

  const cite = String(info.cite || "").trim();
  const websiteUrl = `https://mhub.ai/models/${name}`;
  let githubUrl = "";
  let citeUrl = extractCiteUrl(cite);

  const meta = await fetchMeta(name);
  if (meta && typeof meta === "object") {
    const details = meta.details && typeof meta.details === "object" ? meta.details : {};
    const gh = String(details.github || "").trim();
    if (gh) githubUrl = gh;
    if (!citeUrl && Array.isArray(details.publications)) {
      for (const pub of details.publications) {
        const uri = String(pub?.uri || "").trim();
        if (uri) {
          citeUrl = uri;
          break;
        }
      }
    }
    if (!cite && details.cite) {
      // prefer summary cite; fall back to meta
    }
  }

  const def = {
    name,
    label: String(info.label || name),
    description: String(info.description || ""),
    modalities: Array.isArray(info.modalities) ? info.modalities.map(String) : [],
    category: String(info.category || ""),
    bodyParts,
    websiteUrl,
  };
  if (githubUrl) def.githubUrl = githubUrl;
  if (cite) def.cite = cite;
  if (citeUrl) def.citeUrl = citeUrl;
  models.push(def);
  console.log(
    `${name}: github=${githubUrl ? "yes" : "no"} citeUrl=${citeUrl ? "yes" : "no"}`
  );
}

const header = `/**
 * Slim MHub model catalog for IRA Medical Inference.
 * Source: products/mhub/MHubSkill/data/models_summary.json
 * (cache_date: ${summary.cache_date || "unknown"}).
 * Enriched with GitHub / website / cite via:
 *   node cast_resource_servers/products/mhub/export_ira_catalog.mjs
 */

export type MhubModelDef = {
  name: string;
  label: string;
  description: string;
  modalities: string[];
  category: string;
  /** Canonical body parts from model inputs[].bodypartexamined */
  bodyParts: string[];
  githubUrl?: string;
  websiteUrl?: string;
  cite?: string;
  citeUrl?: string;
};

/** @type {readonly MhubModelDef[]} */
export const MHUB_MODELS: readonly MhubModelDef[] = Object.freeze(${JSON.stringify(models, null, 2)});

function modalityTokens(entry: string): string[] {
  return String(entry || "")
    .split("|")
    .map((t) => t.trim().toUpperCase())
    .filter(Boolean)
    .map((t) => (t === "MRI" ? "MR" : t === "PET" ? "PT" : t));
}

function modelMatchesModality(model: MhubModelDef, modality: string): boolean {
  const want = modality.trim().toUpperCase();
  if (!want) return true;
  const normalizedWant = want === "MRI" ? "MR" : want === "PET" ? "PT" : want;
  return model.modalities.some((m) => modalityTokens(m).includes(normalizedWant));
}

/** Filter skill models by open-study modality. Null/empty → all models. */
export function listMhubModelsForModality(
  modality: string | null | undefined,
): MhubModelDef[] {
  const raw = String(modality || "").trim();
  if (!raw) return [...MHUB_MODELS];
  return MHUB_MODELS.filter((m) => modelMatchesModality(m, raw));
}

function canonBodyPartKey(raw: string): string {
  return String(raw || "")
    .trim()
    .toUpperCase()
    .replace(/[\\s_-]+/g, "");
}

/** Unique body-part options for a model list (sorted, WHOLEBODY last). */
export function listMhubBodyPartsForModels(
  models: readonly MhubModelDef[],
): string[] {
  const parts = new Set<string>();
  for (const model of models) {
    for (const bp of model.bodyParts || []) {
      const t = String(bp || "").trim();
      if (t) parts.add(t);
    }
  }
  return [...parts].sort((a, b) => {
    if (a === "WHOLEBODY") return 1;
    if (b === "WHOLEBODY") return -1;
    return a.localeCompare(b);
  });
}

/** Filter models that declare the given body part examined. */
export function listMhubModelsForBodyPart(
  models: readonly MhubModelDef[],
  bodyPart: string | null | undefined,
): MhubModelDef[] {
  const want = String(bodyPart || "").trim();
  if (!want) return [...models];
  const wantKey = canonBodyPartKey(want);
  return models.filter((m) =>
    (m.bodyParts || []).some((bp) => canonBodyPartKey(bp) === wantKey),
  );
}
`;

fs.mkdirSync(path.dirname(outPath), { recursive: true });
fs.writeFileSync(outPath, header);
console.log(`Wrote ${models.length} models → ${outPath}`);
// silence unused
void escapeTsString;
