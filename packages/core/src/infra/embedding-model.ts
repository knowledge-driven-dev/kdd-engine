/**
 * Embedding model — @huggingface/transformers wrapper.
 */

import type { FeatureExtractionPipeline } from "@huggingface/transformers";

const MODEL_MAP: Record<string, string> = {
  "all-MiniLM-L6-v2": "Xenova/all-MiniLM-L6-v2",
  "all-mpnet-base-v2": "Xenova/all-mpnet-base-v2",
  "paraphrase-multilingual-MiniLM-L12-v2": "Xenova/paraphrase-multilingual-MiniLM-L12-v2",
};

const DEFAULT_MODEL = "Xenova/all-MiniLM-L6-v2";

let pipelineInstance: FeatureExtractionPipeline | null = null;
let currentModelId: string | null = null;

async function getPipeline(modelId: string): Promise<FeatureExtractionPipeline> {
  if (pipelineInstance && currentModelId === modelId) return pipelineInstance;
  const { pipeline } = await import("@huggingface/transformers");
  pipelineInstance = (await pipeline("feature-extraction", modelId, {
    dtype: "fp32",
  })) as FeatureExtractionPipeline;
  currentModelId = modelId;
  return pipelineInstance;
}

export function createEncoder(modelName?: string): (texts: string[]) => Promise<number[][]> {
  const modelId = modelName
    ? (MODEL_MAP[modelName] ?? `Xenova/${modelName}`)
    : DEFAULT_MODEL;

  return async (texts: string[]) => {
    const pipe = await getPipeline(modelId);
    const output = await pipe(texts, { pooling: "mean", normalize: true });
    return output.tolist() as number[][];
  };
}
