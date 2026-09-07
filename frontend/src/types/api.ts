/**
 * DocuFlow AI — Shared TypeScript API Types.
 *
 * These interfaces mirror the backend Pydantic response schemas
 * for type safety across the frontend codebase.
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

export interface User {
  id: string;
  email: string;
  full_name: string;
  role: UserRole;
  tenant_id: string;
  is_active: boolean;
}

export interface DocumentSummary {
  id: string;
  title: string;
  original_filename: string;
  file_type: string;
  file_size_bytes: number;
  version_number: number;
  latest_job?: {
    id: string;
    status: ProcessingStatus;
    progress_percent: number;
  };
  created_at: string;
  updated_at: string;
}

export interface Pagination {
  page: number;
  page_size: number;
  total_items: number;
  total_pages: number;
}

export interface PaginatedResponse<T> {
  items: T[];
  pagination: Pagination;
}

export interface ProcessingJob {
  job_id: string;
  document_id: string;
  status: ProcessingStatus;
  stage: string;
  progress_percent: number;
  retry_count: number;
  max_retries: number;
  started_at: string | null;
  completed_at: string | null;
  errors: ProcessingError[];
}

export interface ProcessingError {
  stage: string;
  error_type: string;
  error_message: string;
  retryable: boolean;
  created_at: string;
}

export interface DocumentChunk {
  id: string;
  chunk_index: number;
  content: string;
  token_count: number;
  heading_hierarchy: string[];
  page_numbers: number[];
  chunk_metadata: Record<string, unknown>;
}

export interface SearchResult {
  chunk_id: string;
  document_id: string;
  document_title: string;
  score: number;
  content: string;
  heading_hierarchy: string[];
  page_numbers: number[];
  chunk_index: number;
}

export interface HealthStatus {
  status: "healthy" | "degraded";
  checks: Record<string, { status: string; detail?: string }>;
}

export interface BuildInfo {
  project: string;
  environment: string;
  api_version: string;
}

export interface ApiProblemDetail {
  type: string;
  title: string;
  status: number;
  detail: string;
  instance: string;
  correlation_id: string;
}
