import { describe, it, expect } from "vitest";
import { ApiError } from "@/lib/api-client";

describe("ApiError Utility", () => {
  it("formats RFC 7807 problem details properly", () => {
    const error = new ApiError({
      status: 422,
      type: "https://docuflow.ai/errors/validation-error",
      title: "Unprocessable Entity",
      detail: "Invalid file signature.",
      correlation_id: "test-corr-id-999",
    });

    expect(error.status).toBe(422);
    expect(error.type).toBe("https://docuflow.ai/errors/validation-error");
    expect(error.detail).toBe("Invalid file signature.");
    expect(error.correlationId).toBe("test-corr-id-999");
    expect(error.message).toBe("Invalid file signature.");
  });

  it("falls back to default error title if detail is missing", () => {
    const error = new ApiError({
      status: 500,
      title: "Internal Server Error",
    });

    expect(error.status).toBe(500);
    expect(error.message).toBe("Internal Server Error");
  });
});
