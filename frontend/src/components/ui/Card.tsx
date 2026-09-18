"use client";

/**
 * DocuFlow AI — Glassmorphism Card Component.
 */

import React from "react";

interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  title?: string;
  subtitle?: string;
  action?: React.ReactNode;
}

export function Card({
  title,
  subtitle,
  action,
  children,
  className = "",
  ...props
}: CardProps) {
  return (
    <div className={`card ${className}`} {...props}>
      {(title || action) && (
        <div className="card-header">
          <div>
            {title && <h3 className="card-title">{title}</h3>}
            {subtitle && (
              <p style={{ fontSize: "0.825rem", marginTop: "0.15rem" }}>
                {subtitle}
              </p>
            )}
          </div>
          {action && <div>{action}</div>}
        </div>
      )}
      {children}
    </div>
  );
}
