"use client";

/**
 * DocuFlow AI — Top Navigation Bar.
 */

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  FileSearch,
  Activity,
  User as UserIcon,
  LogOut,
  Upload,
} from "lucide-react";
import { useAuth } from "../../context/AuthContext";
import { api } from "../../lib/api-client";
import { HealthStatus } from "../../types/api";

export function Navbar({ onMenuToggle }: { onMenuToggle?: () => void }) {
  const { user, logout, isAuthenticated } = useAuth();
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const router = useRouter();

  useEffect(() => {
    const fetchHealth = async () => {
      try {
        const res = await api.health.check();
        setHealth(res);
      } catch {
        setHealth({ status: "degraded", checks: {} });
      }
    };
    fetchHealth();
    const timer = setInterval(fetchHealth, 30000);
    return () => clearInterval(timer);
  }, []);

  return (
    <header className="navbar">
      <div style={{ display: "flex", alignItems: "center", gap: "1rem" }}>
        {onMenuToggle && (
          <button
            onClick={onMenuToggle}
            className="btn btn-ghost btn-sm"
            style={{ display: "none" }}
            aria-label="Toggle menu"
          >
            ☰
          </button>
        )}
        <div
          onClick={() => router.push("/search")}
          style={{
            display: "flex",
            alignItems: "center",
            gap: "0.5rem",
            background: "rgba(255, 255, 255, 0.04)",
            border: "1px solid var(--border-subtle)",
            borderRadius: "var(--radius-md)",
            padding: "0.4rem 0.9rem",
            color: "var(--text-muted)",
            fontSize: "0.85rem",
            cursor: "pointer",
            width: "280px",
          }}
        >
          <FileSearch size={16} />
          <span>Quick search documents...</span>
          <kbd
            style={{
              marginLeft: "auto",
              background: "rgba(255, 255, 255, 0.08)",
              padding: "0.1rem 0.35rem",
              borderRadius: "4px",
              fontSize: "0.7rem",
            }}
          >
            ⌘K
          </kbd>
        </div>
      </div>

      <div style={{ display: "flex", alignItems: "center", gap: "1rem" }}>
        {/* System Health Indicator */}
        <div
          title={`System Health: ${health?.status || "Checking..."}`}
          style={{
            display: "flex",
            alignItems: "center",
            gap: "0.4rem",
            fontSize: "0.8rem",
            padding: "0.3rem 0.6rem",
            borderRadius: "var(--radius-full)",
            background:
              health?.status === "healthy"
                ? "rgba(16, 185, 129, 0.1)"
                : "rgba(244, 63, 94, 0.1)",
            color:
              health?.status === "healthy"
                ? "var(--accent-emerald)"
                : "var(--accent-rose)",
          }}
        >
          <Activity size={14} />
          <span style={{ fontWeight: 600, textTransform: "capitalize" }}>
            {health?.status || "Live"}
          </span>
        </div>

        <Link href="/documents/upload" className="btn btn-primary btn-sm">
          <Upload size={14} />
          <span>Upload</span>
        </Link>

        {isAuthenticated && user ? (
          <div style={{ display: "flex", alignItems: "center", gap: "0.6rem" }}>
            <Link
              href="/profile"
              style={{
                display: "flex",
                alignItems: "center",
                gap: "0.5rem",
                color: "var(--text-primary)",
              }}
            >
              <div className="user-avatar" style={{ width: "32px", height: "32px" }}>
                {user.full_name?.charAt(0).toUpperCase() || "U"}
              </div>
              <span style={{ fontSize: "0.85rem", fontWeight: 600 }}>
                {user.full_name?.split(" ")[0]}
              </span>
            </Link>
            <button
              onClick={() => logout()}
              className="btn btn-ghost btn-sm"
              title="Sign Out"
              aria-label="Sign Out"
            >
              <LogOut size={16} />
            </button>
          </div>
        ) : (
          <Link href="/login" className="btn btn-secondary btn-sm">
            <UserIcon size={14} />
            <span>Sign In</span>
          </Link>
        )}
      </div>
    </header>
  );
}
