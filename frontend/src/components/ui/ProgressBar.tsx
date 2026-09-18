"use client";

/**
 * DocuFlow AI — Animated Progress Bar.
 */

import React from "react";

interface ProgressBarProps {
  progress: number;
  stage?: string;
  showPercentage?: boolean;
  className?: string;
}

export function ProgressBar({
  progress,
  stage,
  showPercentage = true,
  className = "",
}: ProgressBarProps) {
  const clamped = Math.min(100, Math.max(0, progress));

  return (
    <div className={className} style={{ width: "100%" }}>
      {(stage || showPercentage) && (
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            fontSize: "0.8rem",
            marginBottom: "0.35rem",
            color: "var(--text-secondary)",
          }}
        >
          {stage && <span style={{ fontWeight: 600, textTransform: "capitalize" }}>{stage}</span>}
          {showPercentage && (
            <span style={{ fontWeight: 700, color: "var(--text-primary)" }}>{clamped}%</span>
          )}
        </div>
      )}
      <div className="progress-container">
        <div className="progress-fill" style={{ width: `${clamped}%` }} />
      </div>
    </div>
  );
}
