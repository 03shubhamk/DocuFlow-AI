/**
 * DocuFlow AI — API Client Abstraction.
 *
 * Centralized HTTP client for communicating with the FastAPI backend.
 * Handles authentication headers, error parsing, and base URL configuration.
 */

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000/api/v1";

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
    this.type = response.type || "unknown";
    this.detail = response.detail || "";
    this.correlationId = response.correlation_id;
  }
}

async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let errorBody;
    try {
      errorBody = await response.json();
    } catch {
      errorBody = { status: response.status, detail: response.statusText };
    }
    throw new ApiError({ ...errorBody, status: response.status });
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return response.json();
}

function getHeaders(): Record<string, string> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };

  // Token will be added when auth is implemented (Phase 3)
  if (typeof window !== "undefined") {
    const token = localStorage.getItem("docuflow_access_token");
    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }
  }

  return headers;
}

export const apiClient = {
  async get<T>(path: string): Promise<T> {
    const response = await fetch(`${API_BASE_URL}${path}`, {
      method: "GET",
      headers: getHeaders(),
    });
    return handleResponse<T>(response);
  },

  async post<T>(path: string, body?: unknown): Promise<T> {
    const response = await fetch(`${API_BASE_URL}${path}`, {
      method: "POST",
      headers: getHeaders(),
      body: body ? JSON.stringify(body) : undefined,
    });
    return handleResponse<T>(response);
  },

  async put<T>(path: string, body: unknown): Promise<T> {
    const response = await fetch(`${API_BASE_URL}${path}`, {
      method: "PUT",
      headers: getHeaders(),
      body: JSON.stringify(body),
    });
    return handleResponse<T>(response);
  },

  async delete<T>(path: string): Promise<T> {
    const response = await fetch(`${API_BASE_URL}${path}`, {
      method: "DELETE",
      headers: getHeaders(),
    });
    return handleResponse<T>(response);
  },

  /**
   * Multipart file upload (for document ingestion).
   */
  async upload<T>(path: string, formData: FormData): Promise<T> {
    const headers: Record<string, string> = {};
    if (typeof window !== "undefined") {
      const token = localStorage.getItem("docuflow_access_token");
      if (token) {
        headers["Authorization"] = `Bearer ${token}`;
      }
    }
    // Don't set Content-Type — browser sets it with boundary for multipart
    const response = await fetch(`${API_BASE_URL}${path}`, {
      method: "POST",
      headers,
      body: formData,
    });
    return handleResponse<T>(response);
  },
};
