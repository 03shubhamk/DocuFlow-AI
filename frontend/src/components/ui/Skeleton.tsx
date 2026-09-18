"use client";

/**
 * DocuFlow AI — Skeleton Loading Placeholder.
 */

import React from "react";

interface SkeletonProps {
  width?: string | number;
  height?: string | number;
  borderRadius?: string;
  className?: string;
}

export function Skeleton({
  width = "100%",
  height = "20px",
  borderRadius = "var(--radius-sm)",
  className = "",
}: SkeletonProps) {
  return (
    <div
      className={`skeleton ${className}`}
      style={{
        width,
        height,
        borderRadius,
      }}
    />
  );
}

export function CardSkeleton() {
  return (
    <div className="card" style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
      <Skeleton height="28px" width="60%" />
      <Skeleton height="16px" width="80%" />
      <Skeleton height="16px" width="40%" />
    </div>
  );
}

export function TableSkeleton({ rows = 5 }: { rows?: number }) {
  return (
    <div className="table-container" style={{ padding: "1.5rem" }}>
      <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
        {Array.from({ length: rows }).map((_, i) => (
          <Skeleton key={i} height="42px" width="100%" />
        ))}
      </div>
    </div>
  );
}
