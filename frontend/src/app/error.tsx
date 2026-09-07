"use client";

import { useEffect } from "react";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("Unhandled error:", error);
  }, [error]);

  return (
    <div
      style={{
        minHeight: "100vh",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        gap: "1rem",
        background: "#0a0e1a",
        color: "#f1f5f9",
        fontFamily: "system-ui, sans-serif",
      }}
    >
      <div
        style={{
          fontSize: "3rem",
          marginBottom: "0.5rem",
        }}
      >
        ⚠️
      </div>
      <h2 style={{ fontSize: "1.5rem", fontWeight: 700 }}>
        Something went wrong
      </h2>
      <p
        style={{
          color: "#94a3b8",
          maxWidth: "400px",
          textAlign: "center",
          lineHeight: 1.6,
        }}
      >
        An unexpected error occurred in the application. Please try again or
        contact support if the issue persists.
      </p>
      <button
        onClick={reset}
        style={{
          marginTop: "0.5rem",
          padding: "0.6rem 1.5rem",
          borderRadius: "10px",
          border: "1px solid rgba(99, 102, 241, 0.4)",
          background: "rgba(99, 102, 241, 0.1)",
          color: "#818cf8",
          cursor: "pointer",
          fontSize: "0.9rem",
          fontWeight: 600,
          transition: "all 250ms",
        }}
      >
        Try Again
      </button>
    </div>
  );
}
