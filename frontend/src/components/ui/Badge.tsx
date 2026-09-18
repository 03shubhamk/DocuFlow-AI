"use client";

/**
 * DocuFlow AI — Status Badge Component.
 */

import React from "react";
import { ProcessingStatus } from "../../types/api";

interface BadgeProps {
  status: ProcessingStatus | string;
  label?: string;
  className?: string;
}

export function Badge({ status, label, className = "" }: BadgeProps) {
  const displayLabel = label || status;
  const statusKey = status.toUpperCase();

  return (
    <span className={`badge badge-${statusKey} ${className}`}>
      <span className="badge-dot" />
      {displayLabel}
    </span>
  );
}
