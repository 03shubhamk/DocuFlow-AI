"use client";

/**
 * DocuFlow AI — User Profile & Workspace Account Page.
 */

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import {
  Shield,
  Building,
  RotateCw,
  LogOut,
  CheckCircle2,
} from "lucide-react";
import { useAuth } from "../../context/AuthContext";
import { useToast } from "../../context/ToastContext";
import { api } from "../../lib/api-client";
import { Card } from "../../components/ui/Card";
import { Button } from "../../components/ui/Button";

export default function ProfilePage() {
  const router = useRouter();
  const { user, isAuthenticated, isLoading: authLoading, logout, refreshUser } = useAuth();
  const { success: toastSuccess, error: toastError } = useToast();
  const [isRefreshing, setIsRefreshing] = useState(false);

  if (!authLoading && !isAuthenticated) {
    router.push("/login");
  }

  const handleRefreshToken = async () => {
    setIsRefreshing(true);
    try {
      const refreshed = await api.auth.refresh();
      if (refreshed) {
        await refreshUser();
        toastSuccess("JWT access token refreshed successfully.");
      } else {
        toastError("Refresh token expired or invalid.");
      }
    } catch {
      toastError("Failed to refresh token.");
    } finally {
      setIsRefreshing(false);
    }
  };

  return (
    <div style={{ maxWidth: "800px", margin: "0 auto", display: "flex", flexDirection: "column", gap: "2rem" }}>
      <div>
        <h1 style={{ fontSize: "1.75rem" }}>User Profile & Identity</h1>
        <p style={{ marginTop: "0.25rem", color: "var(--text-secondary)" }}>
          Manage your account credentials, tenant roles, and authentication sessions.
        </p>
      </div>

      {/* User Header Card */}
      <Card>
        <div style={{ display: "flex", alignItems: "center", gap: "1.25rem" }}>
          <div
            className="user-avatar"
            style={{
              width: "64px",
              height: "64px",
              fontSize: "1.6rem",
              borderRadius: "var(--radius-lg)",
            }}
          >
            {user?.full_name?.charAt(0).toUpperCase() || "U"}
          </div>
          <div>
            <h2 style={{ fontSize: "1.4rem" }}>{user?.full_name || "DocuFlow User"}</h2>
            <p style={{ fontSize: "0.9rem", color: "var(--text-secondary)", marginTop: "0.2rem" }}>
              {user?.email}
            </p>
          </div>
        </div>
      </Card>

      {/* Account & Tenant Details */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))", gap: "1.5rem" }}>
        <Card title="Tenant & Security Context">
          <div style={{ display: "flex", flexDirection: "column", gap: "1rem", fontSize: "0.9rem" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <span style={{ color: "var(--text-muted)", display: "flex", alignItems: "center", gap: "0.4rem" }}>
                <Shield size={16} /> Role
              </span>
              <span
                style={{
                  background: "rgba(99, 102, 241, 0.15)",
                  color: "#a5b4fc",
                  padding: "0.2rem 0.6rem",
                  borderRadius: "var(--radius-full)",
                  fontWeight: 700,
                  fontSize: "0.75rem",
                  textTransform: "uppercase",
                }}
              >
                {user?.role}
              </span>
            </div>

            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <span style={{ color: "var(--text-muted)", display: "flex", alignItems: "center", gap: "0.4rem" }}>
                <Building size={16} /> Tenant ID
              </span>
              <span style={{ fontFamily: "var(--font-mono)", fontSize: "0.8rem" }}>
                {user?.tenant_id}
              </span>
            </div>

            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <span style={{ color: "var(--text-muted)", display: "flex", alignItems: "center", gap: "0.4rem" }}>
                <CheckCircle2 size={16} /> Account Status
              </span>
              <span style={{ color: "var(--accent-emerald)", fontWeight: 600 }}>
                {user?.is_active ? "Active" : "Disabled"}
              </span>
            </div>
          </div>
        </Card>

        <Card title="Active Authentication Session">
          <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
            <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)" }}>
              Access tokens are signed using HMAC SHA-256 and rotated periodically. You can manually refresh your session token below.
            </p>
            <div style={{ display: "flex", gap: "0.75rem" }}>
              <Button
                variant="secondary"
                size="sm"
                onClick={handleRefreshToken}
                isLoading={isRefreshing}
                icon={<RotateCw size={14} />}
              >
                Refresh JWT
              </Button>
              <Button
                variant="danger"
                size="sm"
                onClick={() => logout()}
                icon={<LogOut size={14} />}
              >
                Sign Out
              </Button>
            </div>
          </div>
        </Card>
      </div>
    </div>
  );
}
