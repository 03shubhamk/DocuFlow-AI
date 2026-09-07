import { describe, it, expect, vi, beforeEach } from "vitest";
import { apiClient, ApiError } from "./api-client";

describe("apiClient", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("should create ApiError with structured error details", () => {
    const error = new ApiError({
      status: 404,
      type: "https://docuflow.ai/errors/document-not-found",
      title: "Document Not Found",
      detail: "Document with id 123 was not found.",
      correlation_id: "corr-123",
    });

    expect(error.status).toBe(404);
    expect(error.type).toBe("https://docuflow.ai/errors/document-not-found");
    expect(error.detail).toBe("Document with id 123 was not found.");
    expect(error.correlationId).toBe("corr-123");
    expect(error.message).toBe("Document with id 123 was not found.");
  });

  it("should make GET request and parse JSON response", async () => {
    const mockData = { status: "alive" };
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => mockData,
    } as Response);

    const result = await apiClient.get<{ status: string }>("/health/live");
    expect(result).toEqual(mockData);
  });

  it("should throw ApiError on non-2xx responses", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce({
      ok: false,
      status: 500,
      statusText: "Internal Server Error",
      json: async () => ({
        type: "https://docuflow.ai/errors/internal-error",
        detail: "Database connection failed",
      }),
    } as Response);

    await expect(apiClient.get("/health/ready")).rejects.toThrow(ApiError);
  });
});
