"use client";

/**
 * DocuFlow AI — Empty State Component.
 */

import React from "react";
import { Button } from "./Button";

interface EmptyStateProps {
  icon?: React.ReactNode;
  title: string;
  description: string;
  actionLabel?: string;
  onAction?: () => void;
}

export function EmptyState({
  icon,
  title,
  description,
  actionLabel,
  onAction,
}: EmptyStateProps) {
  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        padding: "4rem 2rem",
        textAlign: "center",
      }}
    >
      {icon && (
        <div
          style={{
            fontSize: "2.5rem",
            color: "var(--text-muted)",
            marginBottom: "1rem",
          }}
        >
          {icon}
        </div>
      )}
      <h3 style={{ fontSize: "1.25rem", marginBottom: "0.5rem" }}>{title}</h3>
      <p
        style={{
          color: "var(--text-secondary)",
          maxWidth: "420px",
          marginBottom: actionLabel ? "1.5rem" : "0",
          fontSize: "0.9rem",
        }}
      >
        {description}
      </p>
      {actionLabel && onAction && (
        <Button onClick={onAction} variant="primary">
          {actionLabel}
        </Button>
      )}
    </div>
  );
}
