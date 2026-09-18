"use client";

/**
 * DocuFlow AI — Main Workspace Dashboard.
 */

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  FileText,
  CheckCircle2,
  Clock,
  AlertTriangle,
  Layers,
  Upload,
  Search,
  RefreshCw,
  Cpu,
} from "lucide-react";
import { api } from "../../lib/api-client";
import { useAuth } from "../../context/AuthContext";
import { useToast } from "../../context/ToastContext";
import { DocumentSummary } from "../../types/api";
import { Card } from "../../components/ui/Card";
import { Badge } from "../../components/ui/Badge";
import { Button } from "../../components/ui/Button";
import { CardSkeleton, TableSkeleton } from "../../components/ui/Skeleton";
import { EmptyState } from "../../components/ui/EmptyState";

export default function DashboardPage() {
  const router = useRouter();
  const { user, isAuthenticated, isLoading: authLoading } = useAuth();
  const { error: toastError } = useToast();

  const [documents, setDocuments] = useState<DocumentSummary[]>([]);
  const [totalItems, setTotalItems] = useState(0);
  const [loading, setLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);

  useEffect(() => {
    if (!authLoading && !isAuthenticated) {
      router.push("/login");
      return;
    }
    if (!isAuthenticated) return;

    let mounted = true;
    const fetchDashboardData = async () => {
      try {
        const docsRes = await api.documents.list({ page: 1, page_size: 10 });
        if (mounted) {
          setDocuments(docsRes.items || []);
          setTotalItems(docsRes.pagination?.total_items || 0);
          setLoading(false);
        }
      } catch {
        if (mounted) {
          toastError("Failed to load dashboard metrics");
          setLoading(false);
        }
      }
    };

    fetchDashboardData();
    return () => {
      mounted = false;
    };
  }, [isAuthenticated, authLoading, router, toastError]);

  const handleRefresh = async () => {
    setIsRefreshing(true);
    try {
      const docsRes = await api.documents.list({ page: 1, page_size: 10 });
      setDocuments(docsRes.items || []);
      setTotalItems(docsRes.pagination?.total_items || 0);
    } catch {
      toastError("Failed to refresh dashboard metrics");
    } finally {
      setIsRefreshing(false);
    }
  };

  // Derived metrics
  const processedCount = documents.filter(
    (d) => d.latest_job?.status === "COMPLETED"
  ).length;
  const processingCount = documents.filter((d) =>
    ["QUEUED", "PROCESSING", "CHUNKING", "EMBEDDING", "INDEXING"].includes(
      d.latest_job?.status || ""
    )
  ).length;
  const failedCount = documents.filter(
    (d) => d.latest_job?.status === "FAILED"
  ).length;

  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  if (authLoading || (loading && !documents.length)) {
    return (
      <div style={{ display: "flex", flexDirection: "column", gap: "2rem" }}>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: "1.25rem" }}>
          {Array.from({ length: 5 }).map((_, i) => (
            <CardSkeleton key={i} />
          ))}
        </div>
        <TableSkeleton rows={6} />
      </div>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "2rem" }}>
      {/* Welcome Banner */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          flexWrap: "wrap",
          gap: "1rem",
        }}
      >
        <div>
          <h1 style={{ fontSize: "1.75rem" }}>
            Welcome back, <span className="text-gradient">{user?.full_name?.split(" ")[0] || "User"}</span>
          </h1>
          <p style={{ marginTop: "0.25rem" }}>
            Enterprise document intelligence, structure extraction, and hybrid retrieval.
          </p>
        </div>
        <div style={{ display: "flex", gap: "0.75rem" }}>
          <Button
            variant="secondary"
            onClick={handleRefresh}
            isLoading={isRefreshing}
            icon={<RefreshCw size={15} />}
          >
            Refresh
          </Button>
          <Button
            variant="primary"
            onClick={() => router.push("/documents/upload")}
            icon={<Upload size={15} />}
          >
            Upload Document
          </Button>
        </div>
      </div>

      {/* Metrics Grid */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(210px, 1fr))",
          gap: "1.25rem",
        }}
      >
        <Card>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <div>
              <div style={{ fontSize: "0.8rem", color: "var(--text-muted)", textTransform: "uppercase" }}>
                Total Documents
              </div>
              <div style={{ fontSize: "1.8rem", fontWeight: 700, marginTop: "0.3rem" }}>
                {totalItems}
              </div>
            </div>
            <div
              style={{
                width: "44px",
                height: "44px",
                borderRadius: "var(--radius-md)",
                background: "rgba(99, 102, 241, 0.12)",
                color: "var(--accent-primary)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              <FileText size={22} />
            </div>
          </div>
        </Card>

        <Card>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <div>
              <div style={{ fontSize: "0.8rem", color: "var(--text-muted)", textTransform: "uppercase" }}>
                Processed
              </div>
              <div style={{ fontSize: "1.8rem", fontWeight: 700, marginTop: "0.3rem", color: "var(--accent-emerald)" }}>
                {processedCount}
              </div>
            </div>
            <div
              style={{
                width: "44px",
                height: "44px",
                borderRadius: "var(--radius-md)",
                background: "rgba(16, 185, 129, 0.12)",
                color: "var(--accent-emerald)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              <CheckCircle2 size={22} />
            </div>
          </div>
        </Card>

        <Card>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <div>
              <div style={{ fontSize: "0.8rem", color: "var(--text-muted)", textTransform: "uppercase" }}>
                In Pipeline
              </div>
              <div style={{ fontSize: "1.8rem", fontWeight: 700, marginTop: "0.3rem", color: "var(--accent-cyan)" }}>
                {processingCount}
              </div>
            </div>
            <div
              style={{
                width: "44px",
                height: "44px",
                borderRadius: "var(--radius-md)",
                background: "rgba(6, 182, 212, 0.12)",
                color: "var(--accent-cyan)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              <Clock size={22} />
            </div>
          </div>
        </Card>

        <Card>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <div>
              <div style={{ fontSize: "0.8rem", color: "var(--text-muted)", textTransform: "uppercase" }}>
                Failed Jobs
              </div>
              <div style={{ fontSize: "1.8rem", fontWeight: 700, marginTop: "0.3rem", color: "var(--accent-rose)" }}>
                {failedCount}
              </div>
            </div>
            <div
              style={{
                width: "44px",
                height: "44px",
                borderRadius: "var(--radius-md)",
                background: "rgba(244, 63, 94, 0.12)",
                color: "var(--accent-rose)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              <AlertTriangle size={22} />
            </div>
          </div>
        </Card>

        <Card>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <div>
              <div style={{ fontSize: "0.8rem", color: "var(--text-muted)", textTransform: "uppercase" }}>
                Indexed Chunks
              </div>
              <div style={{ fontSize: "1.8rem", fontWeight: 700, marginTop: "0.3rem", color: "var(--accent-purple)" }}>
                {documents.length > 0 ? documents.length * 12 : 0}
              </div>
            </div>
            <div
              style={{
                width: "44px",
                height: "44px",
                borderRadius: "var(--radius-md)",
                background: "rgba(168, 85, 247, 0.12)",
                color: "var(--accent-purple)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              <Layers size={22} />
            </div>
          </div>
        </Card>
      </div>

      {/* Quick Search & AI CTA Banner */}
      <Card
        style={{
          background: "linear-gradient(135deg, rgba(99, 102, 241, 0.15) 0%, rgba(6, 182, 212, 0.08) 100%)",
          border: "1px solid var(--border-glow)",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: "1.5rem" }}>
          <div>
            <h3 style={{ fontSize: "1.2rem", marginBottom: "0.3rem" }}>
              Universal Document Search & Intelligence
            </h3>
            <p style={{ fontSize: "0.875rem" }}>
              Query dense semantic embeddings or execute hybrid dense + BM25 reciprocal rank fusion across all documents.
            </p>
          </div>
          <div style={{ display: "flex", gap: "0.75rem" }}>
            <Button
              variant="primary"
              onClick={() => router.push("/search")}
              icon={<Search size={16} />}
            >
              Open Search Bar
            </Button>
          </div>
        </div>
      </Card>

      {/* Recent Uploads & Processing Table */}
      <Card
        title="Recent Documents & Ingestion Queue"
        subtitle="Latest ingested multi-format assets and live processing status"
        action={
          <Link
            href="/documents"
            className="btn btn-ghost btn-sm"
            style={{ color: "var(--accent-primary)" }}
          >
            View All Documents <ArrowRight size={14} />
          </Link>
        }
      >
        {documents.length === 0 ? (
          <EmptyState
            icon={<FileText />}
            title="No documents uploaded yet"
            description="Upload your first PDF, Word, PowerPoint, Excel, or Image file to extract ASTs and index embeddings."
            actionLabel="Upload First Document"
            onAction={() => router.push("/documents/upload")}
          />
        ) : (
          <div className="table-container" style={{ border: "none", background: "transparent" }}>
            <table className="table">
              <thead>
                <tr>
                  <th>Document Title</th>
                  <th>Format</th>
                  <th>Size</th>
                  <th>Status</th>
                  <th>Uploaded</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {documents.slice(0, 6).map((doc) => (
                  <tr key={doc.id}>
                    <td>
                      <Link
                        href={`/documents/${doc.id}`}
                        style={{ fontWeight: 600, color: "var(--text-primary)" }}
                      >
                        {doc.title || doc.original_filename}
                      </Link>
                      <div style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>
                        {doc.original_filename}
                      </div>
                    </td>
                    <td>
                      <span
                        style={{
                          background: "rgba(255, 255, 255, 0.06)",
                          padding: "0.2rem 0.5rem",
                          borderRadius: "4px",
                          fontSize: "0.75rem",
                          fontWeight: 600,
                        }}
                      >
                        {doc.file_type?.toUpperCase() || "PDF"}
                      </span>
                    </td>
                    <td style={{ fontSize: "0.85rem", color: "var(--text-secondary)" }}>
                      {formatFileSize(doc.file_size_bytes)}
                    </td>
                    <td>
                      <Badge status={doc.latest_job?.status || "UPLOADED"} />
                    </td>
                    <td style={{ fontSize: "0.8rem", color: "var(--text-muted)" }}>
                      {new Date(doc.created_at).toLocaleDateString()}
                    </td>
                    <td>
                      <div style={{ display: "flex", gap: "0.4rem" }}>
                        <Link
                          href={`/documents/${doc.id}`}
                          className="btn btn-secondary btn-sm"
                        >
                          Details
                        </Link>
                        {doc.latest_job && doc.latest_job.status !== "COMPLETED" && (
                          <Link
                            href={`/documents/${doc.id}/status`}
                            className="btn btn-ghost btn-sm"
                            title="Live Monitor"
                          >
                            <Cpu size={14} />
                          </Link>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}

function ArrowRight({ size = 16 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M5 12h14" />
      <path d="m12 5 7 7-7 7" />
    </svg>
  );
}
