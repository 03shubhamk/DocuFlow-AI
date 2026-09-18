/**
 * DocuFlow AI — Shared TypeScript API Types & Domain Contracts.
 *
 * Fully mirrors backend Pydantic models for complete type safety across
 * the frontend application.
 */

export type ProcessingStatus =
  | "UPLOADED"
  | "QUEUED"
  | "PROCESSING"
  | "CHUNKING"
  | "EMBEDDING"
  | "INDEXING"
  | "COMPLETED"
  | "FAILED"
  | "CANCELLED";

export type UserRole = "ADMIN" | "EDITOR" | "VIEWER";

export type SearchStrategy = "dense" | "hybrid";

export interface User {
  id: string;
  email: string;
  full_name: string;
  role: UserRole;
  tenant_id: string;
  is_active: boolean;
  created_at?: string;
  updated_at?: string;
}

export interface AuthTokens {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}

export interface AuthResponse extends AuthTokens {
  user: User;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
}

export interface DocumentSummary {
  id: string;
  title: string;
  original_filename: string;
  file_type: string;
  file_size_bytes: number;
  checksum?: string;
  version_number?: number;
  created_at: string;
  updated_at: string;
  latest_job?: ProcessingJobSummary | null;
}

export interface DocumentVersionSummary {
  id: string;
  version_number: number;
  file_size_bytes: number;
  checksum: string;
  created_at: string;
}

export interface DocumentAssetSummary {
  id: string;
  asset_type: string;
  file_size_bytes: number;
  created_at: string;
}

export interface ProcessingErrorSummary {
  id?: string;
  job_id?: string;
  error_type: string;
  error_message: string;
  traceback_snippet?: string | null;
  stage: string;
  created_at: string;
}

export interface ProcessingJobSummary {
  id: string;
  document_id: string;
  version_id?: string;
  status: ProcessingStatus;
  stage: string;
  progress_percent: number;
  retry_count: number;
  max_retries: number;
  started_at?: string | null;
  completed_at?: string | null;
  execution_time_ms?: number | null;
  errors?: ProcessingErrorSummary[];
}

export interface DocumentDetailResponse {
  id: string;
  tenant_id: string;
  user_id: string;
  title: string;
  original_filename: string;
  file_type: string;
  file_size_bytes: number;
  is_deleted: boolean;
  created_at: string;
  updated_at: string;
  versions: DocumentVersionSummary[];
  assets: DocumentAssetSummary[];
  latest_job: ProcessingJobSummary | null;
}

export interface DocumentUploadResponse {
  document_id: string;
  version_id: string;
  job_id: string;
  title: string;
  original_filename: string;
  file_type: string;
  file_size_bytes: number;
  checksum: string;
  status: ProcessingStatus;
  created_at: string;
}

export interface PaginationMetadata {
  page: number;
  page_size: number;
  total_items: number;
  total_pages: number;
  has_next: boolean;
  has_prev: boolean;
}

export interface DocumentListResponse {
  items: DocumentSummary[];
  pagination: PaginationMetadata;
}

export interface ProcessingStatusResponse {
  job_id: string;
  document_id: string;
  version_id: string;
  status: ProcessingStatus;
  stage: string;
  progress_percent: number;
  retry_count: number;
  max_retries: number;
  started_at?: string | null;
  completed_at?: string | null;
  execution_time_ms?: number | null;
  errors: ProcessingErrorSummary[];
}

export interface ProcessDocumentRequest {
  do_ocr?: boolean;
  ocr_provider?: string;
  ocr_languages?: string[];
  do_table_structure?: boolean;
  extract_figures?: boolean;
  chunking_strategy?: "hierarchical" | "hybrid";
  chunk_size?: number;
  chunk_overlap?: number;
}

export interface SectionHierarchyNode {
  title: string;
  level: number;
  page?: number | null;
  section_path: string;
  children: SectionHierarchyNode[];
}

export interface DocumentStructureResponse {
  document_id: string;
  version_id?: string;
  title: string;
  page_count: number;
  table_count: number;
  figure_count: number;
  language?: string | null;
  section_hierarchy: SectionHierarchyNode[];
  word_count?: number;
  character_count?: number;
}

export interface DocumentChunkSummary {
  id: string;
  document_id: string;
  version_id: string;
  chunk_index: number;
  token_count: number;
  page_number: number;
  page_numbers: number[];
  heading_hierarchy: string[];
  section_path: string;
  chunk_type: string;
  content: string;
  chunk_metadata: Record<string, unknown>;
  created_at: string;
}

export interface DocumentChunkListResponse {
  items: DocumentChunkSummary[];
  pagination: PaginationMetadata;
}

export interface ReindexResponse {
  document_id: string;
  version_id: string;
  chunks_indexed: number;
  vector_store_collection: string;
  status: string;
}

export interface SearchRequest {
  query: string;
  top_k?: number;
  document_ids?: string[];
  page?: number | null;
  page_size?: number;
  score_threshold?: number | null;
  filters?: Record<string, unknown>;
  strategy?: SearchStrategy;
}

export interface SearchResultItem {
  chunk_id: string;
  document_id: string;
  document_name: string;
  score: number;
  text: string;
  page_number: number;
  page_numbers: number[];
  section?: string | null;
  heading_hierarchy: string[];
  metadata: Record<string, unknown>;
}

export interface SearchResponse {
  query: string;
  total_results: number;
  page: number;
  page_size: number;
  strategy: string;
  duration_ms: number;
  results: SearchResultItem[];
}

export interface HealthStatus {
  status: "healthy" | "degraded" | "unhealthy";
  checks: Record<string, { status: string; detail?: string; latency_ms?: number }>;
  timestamp?: string;
}

export interface BuildInfo {
  project: string;
  environment: string;
  api_version: string;
  docling_version?: string;
  fastembed_version?: string;
}

export interface ApiProblemDetail {
  type?: string;
  title?: string;
  status: number;
  detail: string;
  instance?: string;
  correlation_id?: string;
}
