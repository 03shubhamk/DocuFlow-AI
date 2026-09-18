/**
 * DocuFlow AI — Centralized Typed API Client.
 *
 * Provides a type-safe interface for all DocuFlow backend endpoints with
 * automatic JWT authorization injection, token refresh handling,
 * error normalization, and multipart file upload support.
 */

import {
  AuthResponse,
  BuildInfo,
  DocumentChunkListResponse,
  DocumentDetailResponse,
  DocumentListResponse,
  DocumentStructureResponse,
  DocumentUploadResponse,
  HealthStatus,
  ProcessDocumentRequest,
  ProcessingStatusResponse,
  ReindexResponse,
  SearchRequest,
  SearchResponse,
  TokenResponse,
  User,
} from "../types/api";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL || "/api/v1";

export class ApiError extends Error {
  status: number;
  type: string;
  detail: string;
  correlationId?: string;

  constructor(response: {
    status: number;
    type?: string;
    title?: string;
    detail?: string;
    correlation_id?: string;
  }) {
    super(response.detail || response.title || "An API error occurred");
    this.status = response.status;
    this.type = response.type || "api_error";
    this.detail = response.detail || "";
    this.correlationId = response.correlation_id;
  }
}

function getStoredAccessToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("docuflow_access_token");
}

function getStoredRefreshToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("docuflow_refresh_token");
}

function setStoredTokens(tokens: { access_token: string; refresh_token?: string }) {
  if (typeof window === "undefined") return;
  localStorage.setItem("docuflow_access_token", tokens.access_token);
  if (tokens.refresh_token) {
    localStorage.setItem("docuflow_refresh_token", tokens.refresh_token);
  }
}

function clearStoredTokens() {
  if (typeof window === "undefined") return;
  localStorage.removeItem("docuflow_access_token");
  localStorage.removeItem("docuflow_refresh_token");
  localStorage.removeItem("docuflow_user");
}

function getDefaultHeaders(isMultipart = false): Record<string, string> {
  const headers: Record<string, string> = {};
  if (!isMultipart) {
    headers["Content-Type"] = "application/json";
  }
  const token = getStoredAccessToken();
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }
  return headers;
}

async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let errorBody: {
      status?: number;
      type?: string;
      title?: string;
      detail?: string;
      correlation_id?: string;
    };
    try {
      errorBody = await response.json();
    } catch {
      errorBody = {
        status: response.status,
        detail: response.statusText || "Unexpected network error",
      };
    }
    throw new ApiError({
      status: response.status,
      type: errorBody.type,
      title: errorBody.title,
      detail: errorBody.detail || response.statusText,
      correlation_id: errorBody.correlation_id,
    });
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return response.json();
}

/** Core HTTP primitives */
export const http = {
  async get<T>(
    path: string,
    params?: Record<string, string | number | boolean | undefined | null>,
    signal?: AbortSignal
  ): Promise<T> {
    let url = `${API_BASE_URL}${path}`;
    if (params) {
      const searchParams = new URLSearchParams();
      Object.entries(params).forEach(([key, value]) => {
        if (value !== undefined && value !== null && value !== "") {
          searchParams.append(key, String(value));
        }
      });
      const qs = searchParams.toString();
      if (qs) {
        url += `?${qs}`;
      }
    }
    const response = await fetch(url, {
      method: "GET",
      headers: getDefaultHeaders(),
      signal,
    });
    return handleResponse<T>(response);
  },

  async post<T>(path: string, body?: unknown, signal?: AbortSignal): Promise<T> {
    const response = await fetch(`${API_BASE_URL}${path}`, {
      method: "POST",
      headers: getDefaultHeaders(),
      body: body !== undefined ? JSON.stringify(body) : undefined,
      signal,
    });
    return handleResponse<T>(response);
  },

  async put<T>(path: string, body?: unknown, signal?: AbortSignal): Promise<T> {
    const response = await fetch(`${API_BASE_URL}${path}`, {
      method: "PUT",
      headers: getDefaultHeaders(),
      body: body !== undefined ? JSON.stringify(body) : undefined,
      signal,
    });
    return handleResponse<T>(response);
  },

  async delete<T>(path: string, signal?: AbortSignal): Promise<T> {
    const response = await fetch(`${API_BASE_URL}${path}`, {
      method: "DELETE",
      headers: getDefaultHeaders(),
      signal,
    });
    return handleResponse<T>(response);
  },

  async upload<T>(path: string, formData: FormData, signal?: AbortSignal): Promise<T> {
    const response = await fetch(`${API_BASE_URL}${path}`, {
      method: "POST",
      headers: getDefaultHeaders(true),
      body: formData,
      signal,
    });
    return handleResponse<T>(response);
  },
};

/** Dedicated domain services */
export const api = {
  auth: {
    async login(payload: { email: string; password: string }): Promise<{ access_token: string; user: User }> {
      const tokenRes = await http.post<TokenResponse>("/auth/login", payload);
      setStoredTokens(tokenRes);
      const user = await http.get<User>("/auth/me");
      if (typeof window !== "undefined") {
        localStorage.setItem("docuflow_user", JSON.stringify(user));
      }
      return {
        access_token: tokenRes.access_token,
        user,
      };
    },

    async register(payload: {
      email: string;
      password: string;
      full_name: string;
      tenant_name?: string;
    }): Promise<{ access_token: string; user: User }> {
      await http.post<User>("/auth/register", payload);
      return api.auth.login({ email: payload.email, password: payload.password });
    },

    async me(): Promise<User> {
      return http.get<User>("/auth/me");
    },

    async refresh(): Promise<TokenResponse | null> {
      const refreshToken = getStoredRefreshToken();
      if (!refreshToken) return null;
      try {
        const res = await http.post<TokenResponse>("/auth/refresh", {
          refresh_token: refreshToken,
        });
        setStoredTokens(res);
        return res;
      } catch {
        clearStoredTokens();
        return null;
      }
    },

    async logout(): Promise<void> {
      const refreshToken = getStoredRefreshToken();
      try {
        if (refreshToken) {
          await http.post("/auth/logout", { refresh_token: refreshToken });
        }
      } finally {
        clearStoredTokens();
      }
    },
  },

  documents: {
    async list(params?: {
      page?: number;
      page_size?: number;
      search?: string;
      file_type?: string;
      status?: string;
      sort_by?: string;
      sort_desc?: boolean;
    }): Promise<DocumentListResponse> {
      return http.get<DocumentListResponse>("/documents", params);
    },

    async getById(id: string): Promise<DocumentDetailResponse> {
      return http.get<DocumentDetailResponse>(`/documents/${id}`);
    },

    async upload(file: File): Promise<DocumentUploadResponse> {
      const formData = new FormData();
      formData.append("file", file);
      return http.upload<DocumentUploadResponse>("/documents", formData);
    },

    async delete(id: string): Promise<{ message: string; document_id: string }> {
      return http.delete<{ message: string; document_id: string }>(`/documents/${id}`);
    },

    async process(
      id: string,
      options?: ProcessDocumentRequest
    ): Promise<ProcessingStatusResponse> {
      return http.post<ProcessingStatusResponse>(`/documents/${id}/process`, options || {});
    },

    async getStatus(id: string): Promise<ProcessingStatusResponse> {
      return http.get<ProcessingStatusResponse>(`/documents/${id}/processing-status`);
    },

    async getStructure(id: string): Promise<DocumentStructureResponse> {
      return http.get<DocumentStructureResponse>(`/documents/${id}/structure`);
    },

    async getChunks(
      id: string,
      params?: { page?: number; page_size?: number }
    ): Promise<DocumentChunkListResponse> {
      return http.get<DocumentChunkListResponse>(`/documents/${id}/chunks`, params);
    },

    async reindex(id: string): Promise<ReindexResponse> {
      return http.post<ReindexResponse>(`/documents/${id}/reindex`);
    },

    getAssetDownloadUrl(id: string, assetType: string): string {
      return `${API_BASE_URL}/documents/${id}/assets/${assetType}`;
    },

    async fetchAssetText(id: string, assetType: string): Promise<string> {
      const response = await fetch(this.getAssetDownloadUrl(id, assetType), {
        headers: getDefaultHeaders(),
      });
      if (!response.ok) {
        throw new Error(`Failed to fetch ${assetType} asset`);
      }
      return response.text();
    },
  },

  search: {
    async query(payload: SearchRequest, signal?: AbortSignal): Promise<SearchResponse> {
      return http.post<SearchResponse>("/search", payload, signal);
    },
  },

  health: {
    async check(): Promise<HealthStatus> {
      return http.get<HealthStatus>("/health");
    },

    async buildInfo(): Promise<BuildInfo> {
      return http.get<BuildInfo>("/health/build-info");
    },
  },
};

export const apiClient = http;

export { clearStoredTokens, getStoredAccessToken, getStoredRefreshToken, setStoredTokens };
