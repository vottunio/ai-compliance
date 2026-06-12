/** AI Act 50 v2.1 — shared types (Phase 3 marking + composite). */

export type MarkingMode = "standard" | "proprietary" | "hybrid" | "auto";
export type AnchorMode = "public" | "private";
export type ProductConfiguration = "A" | "B" | "C" | "D";
export type CertificationPattern = "standard" | "proprietary" | "composite";
export type IngredientDisclosureMode = "full" | "hash_only" | "nominal" | "mixed";

export type CompositionIngredient = {
  cert_id?: string;
  content_hash?: string;
  model_id?: string;
  role?: string;
  disclosure?: IngredientDisclosureMode;
};

export type MarkingSignals = {
  image_watermark?: boolean;
  lexical_watermark?: boolean;
  upstream_c2pa?: boolean;
  synthid?: boolean;
  c2pa_present?: boolean;
};

export type VottunDetectResponse = {
  watermark_detected: boolean;
  confidence: number;
  extracted_payload?: string | null;
  matched_cert_id?: string | null;
  certificate?: Record<string, unknown> | null;
  hash_match?: boolean;
  note?: string | null;
  c2pa_verified?: boolean | null;
  c2pa_manifest?: Record<string, unknown> | null;
  synthid_detected?: boolean | null;
  synthid_confidence?: number | null;
  detected_marking_mode?: MarkingMode | null;
  marking_signals?: MarkingSignals | null;
};

export type VottunWrapResponse = {
  cert_id?: string | null;
  marking_mode: MarkingMode;
  upstream_c2pa_preserved: boolean;
  c2pa_manifest?: Record<string, unknown> | null;
  file_format?: string | null;
  file_size_bytes?: number | null;
  file_download_url?: string | null;
  content_hash?: string | null;
};

export type VottunCompositionRecord = {
  cert_id?: string;
  root_hash?: string;
  disclosure_mode?: string;
  ingredient_count?: number;
  tree_location?: string;
  ingredients?: CompositionIngredient[];
  leaf_digests?: string[];
};

/** Phase 4 — mode-aware anchor proof union on verify / audit export. */
export type BlockchainAnchorProof = {
  type: "blockchain";
  tx_hash: string;
  block_number?: number | null;
  chain_id?: string | null;
};

export type MerkleLogAnchorProof = {
  type: "merkle_log";
  log_id: string;
  leaf_index: number;
  inclusion_proof?: string | null;
  signed_root?: string | null;
  eidas_timestamp?: string | null;
  on_chain_root_tx_hash?: string | null;
};

export type AnchorProof = BlockchainAnchorProof | MerkleLogAnchorProof;

export type VottunVerifyResponse = {
  cert_id: string;
  status: "valid" | "not_found" | "invalid";
  content_hash?: string | null;
  anchor_mode?: AnchorMode | null;
  configuration?: ProductConfiguration | null;
  marking_mode?: MarkingMode | null;
  tx_hash?: string | null;
  on_chain_verified?: boolean;
  anchor_proof?: AnchorProof | null;
  verification_result?: "valid" | "invalid" | "not_found" | null;
  [key: string]: unknown;
};

export type CoverageDimensionCount = { count: number; pct: number };

export type ConfigurationCoverageRow = {
  configuration: string;
  total: number;
  marking: CoverageDimensionCount;
  robustness: CoverageDimensionCount;
  demonstrability: CoverageDimensionCount;
};

export type VottunAuditCoverageResponse = {
  success: boolean;
  days?: number | null;
  configurations: ConfigurationCoverageRow[];
  totals: Record<string, number>;
};

export type VottunAuditSamplingRequest = {
  sample_size?: number;
  seed?: string;
  date_from?: string;
  date_to?: string;
  configuration?: ProductConfiguration;
  anchor_mode?: AnchorMode;
};

export type VottunAuditSamplingResponse = {
  success: boolean;
  seed: string;
  sample_size: number;
  population: number;
  items: Array<Record<string, unknown>>;
};

export type VottunInclusionProofResponse = Record<string, unknown>;
