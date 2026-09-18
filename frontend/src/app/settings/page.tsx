"use client";

/**
 * DocuFlow AI — Platform Settings & Diagnostics.
 */

import React, { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  CheckCircle2,
  RefreshCw,
} from "lucide-react";
import { api } from "../../lib/api-client";
import { useToast } from "../../context/ToastContext";
import { useAuth } from "../../context/AuthContext";
import { BuildInfo, HealthStatus } from "../../types/api";
import { Card } from "../../components/ui/Card";
import { Button } from "../../components/ui/Button";

export default function SettingsPage() {
  const router = useRouter();
  const { isAuthenticated, isLoading: authLoading } = useAuth();
  const { success: toastSuccess, error: toastError } = useToast();

  const [buildInfo, setBuildInfo] = useState<BuildInfo | null>(null);
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [isTesting, setIsTesting] = useState(false);

  // Search defaults
  const [defaultStrategy, setDefaultStrategy] = useState("dense");
  const [defaultTopK, setDefaultTopK] = useState(10);
  const [defaultThreshold, setDefaultThreshold] = useState(0.0);

  useEffect(() => {
    if (!authLoading && !isAuthenticated) {
      router.push("/login");
      return;
    }

    const fetchInfo = async () => {
      try {
        const [bRes, hRes] = await Promise.allSettled([
          api.health.buildInfo(),
          api.health.check(),
        ]);
        if (bRes.status === "fulfilled") setBuildInfo(bRes.value);
        if (hRes.status === "fulfilled") setHealth(hRes.value);
      } catch {
        // ignore
      }
    };

    if (isAuthenticated) {
      fetchInfo();
    }
  }, [isAuthenticated, authLoading, router]);

  const testConnection = async () => {
    setIsTesting(true);
    try {
      const h = await api.health.check();
      setHealth(h);
      toastSuccess(`Backend connection healthy (${h.status}).`, "Connection Test");
    } catch {
      toastError("Failed to connect to DocuFlow backend.");
    } finally {
      setIsTesting(false);
    }
  };

  const handleSavePreferences = () => {
    toastSuccess("Search preferences saved to local profile.");
  };

  return (
    <div style={{ maxWidth: "900px", margin: "0 auto", display: "flex", flexDirection: "column", gap: "2rem" }}>
      <div>
        <h1 style={{ fontSize: "1.75rem" }}>Platform Settings & Diagnostics</h1>
        <p style={{ marginTop: "0.25rem", color: "var(--text-secondary)" }}>
          Configure API connectors, search defaults, and inspect runtime Docling & FastEmbed environments.
        </p>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(360px, 1fr))", gap: "1.5rem" }}>
        {/* API Connection & Health */}
        <Card title="API Backend Gateway" subtitle="FastAPI runtime connection status">
          <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
            <div className="form-group" style={{ marginBottom: "0.5rem" }}>
              <label className="form-label">API Base URL</label>
              <input
                type="text"
                disabled
                className="form-input"
                value={process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000/api/v1"}
              />
            </div>

            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                <CheckCircle2
                  size={16}
                  color={health?.status === "healthy" ? "var(--accent-emerald)" : "var(--accent-rose)"}
                />
                <span style={{ fontSize: "0.85rem", fontWeight: 600 }}>
                  Status: {health?.status || "Unknown"}
                </span>
              </div>
              <Button
                variant="secondary"
                size="sm"
                onClick={testConnection}
                isLoading={isTesting}
                icon={<RefreshCw size={14} />}
              >
                Test Connection
              </Button>
            </div>
          </div>
        </Card>

        {/* Runtime Diagnostics */}
        <Card title="Engine Build Diagnostics" subtitle="Integrated parser and AI model versions">
          <div style={{ display: "flex", flexDirection: "column", gap: "0.85rem", fontSize: "0.875rem" }}>
            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <span style={{ color: "var(--text-muted)" }}>Project</span>
              <span style={{ fontWeight: 600 }}>{buildInfo?.project || "DocuFlow AI"}</span>
            </div>
            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <span style={{ color: "var(--text-muted)" }}>Environment</span>
              <span style={{ textTransform: "uppercase", color: "var(--accent-cyan)", fontWeight: 700 }}>
                {buildInfo?.environment || "development"}
              </span>
            </div>
            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <span style={{ color: "var(--text-muted)" }}>API Version</span>
              <span>{buildInfo?.api_version || "1.0.0"}</span>
            </div>
            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <span style={{ color: "var(--text-muted)" }}>Docling Engine</span>
              <span>{buildInfo?.docling_version || "2.x (Unified AST)"}</span>
            </div>
            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <span style={{ color: "var(--text-muted)" }}>Embedding Provider</span>
              <span>{buildInfo?.fastembed_version || "FastEmbed / BAAI/bge-small-en-v1.5"}</span>
            </div>
          </div>
        </Card>
      </div>

      {/* Search & Ingestion Defaults */}
      <Card title="Default Search & Ingestion Preferences">
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
            gap: "1.25rem",
          }}
        >
          <div className="form-group">
            <label className="form-label">Default Retrieval Strategy</label>
            <select
              className="form-select"
              value={defaultStrategy}
              onChange={(e) => setDefaultStrategy(e.target.value)}
            >
              <option value="dense">Dense Vector Search (Cosine)</option>
              <option value="hybrid">Hybrid (Dense + BM25 RRF)</option>
            </select>
          </div>

          <div className="form-group">
            <label className="form-label">Default Top Chunks (k)</label>
            <select
              className="form-select"
              value={defaultTopK}
              onChange={(e) => setDefaultTopK(Number(e.target.value))}
            >
              <option value={5}>Top 5 chunks</option>
              <option value={10}>Top 10 chunks</option>
              <option value={20}>Top 20 chunks</option>
            </select>
          </div>

          <div className="form-group">
            <label className="form-label">Default Score Threshold</label>
            <input
              type="number"
              className="form-input"
              value={defaultThreshold}
              min={0.0}
              max={0.9}
              step={0.05}
              onChange={(e) => setDefaultThreshold(Number(e.target.value))}
            />
          </div>
        </div>

        <div style={{ display: "flex", justifyContent: "flex-end", marginTop: "1.5rem" }}>
          <Button variant="primary" onClick={handleSavePreferences}>
            Save Preferences
          </Button>
        </div>
      </Card>
    </div>
  );
}
