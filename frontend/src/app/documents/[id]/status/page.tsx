"use client";

/**
 * DocuFlow AI — Dedicated Real-Time Processing Job Monitor.
 */

import React, { useEffect, useState, use } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  Cpu,
  RotateCw,
  CheckCircle2,
  AlertCircle,
  ArrowLeft,
  Layers,
  Sparkles,
  FileCode,
  FileCheck,
  UploadCloud,
} from "lucide-react";
import { api } from "../../../../lib/api-client";
import { useToast } from "../../../../context/ToastContext";
import { useAuth } from "../../../../context/AuthContext";
import { ProcessingStatusResponse } from "../../../../types/api";
import { Card } from "../../../../components/ui/Card";
import { Badge } from "../../../../components/ui/Badge";
import { Button } from "../../../../components/ui/Button";
import { ProgressBar } from "../../../../components/ui/ProgressBar";
import { CardSkeleton } from "../../../../components/ui/Skeleton";

export default function DocumentStatusPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const resolvedParams = use(params);
  const documentId = resolvedParams.id;

  const router = useRouter();
  const { isAuthenticated, isLoading: authLoading } = useAuth();
  const { success: toastSuccess, error: toastError } = useToast();

  const [statusInfo, setStatusInfo] = useState<ProcessingStatusResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [isRetrying, setIsRetrying] = useState(false);

  useEffect(() => {
    if (!authLoading && !isAuthenticated) {
      router.push("/login");
      return;
    }

    const fetchStatus = async () => {
      try {
        const res = await api.documents.getStatus(documentId);
        setStatusInfo(res);
      } catch {
        toastError("Failed to fetch processing status.");
      } finally {
        setLoading(false);
      }
    };

    fetchStatus();

    // Auto-poll if job is still in progress
    const timer = setInterval(() => {
      if (
        statusInfo?.status &&
        !["COMPLETED", "FAILED", "CANCELLED"].includes(statusInfo.status)
      ) {
        fetchStatus();
      }
    }, 2000);

    return () => clearInterval(timer);
  }, [documentId, isAuthenticated, authLoading, router, statusInfo?.status, toastError]);

  const handleRetry = async () => {
    setIsRetrying(true);
    try {
      await api.documents.process(documentId);
      toastSuccess("Pipeline restarted.");
      const updated = await api.documents.getStatus(documentId);
      setStatusInfo(updated);
    } catch {
      toastError("Failed to retry pipeline.");
    } finally {
      setIsRetrying(false);
    }
  };

  if (loading) {
    return <CardSkeleton />;
  }

  const isCompleted = statusInfo?.status === "COMPLETED";
  const isFailed = statusInfo?.status === "FAILED";
  const progressPercent = statusInfo?.progress_percent || (isCompleted ? 100 : 35);

  return (
    <div style={{ maxWidth: "860px", margin: "0 auto", display: "flex", flexDirection: "column", gap: "2rem" }}>
      {/* Back Link & Header */}
      <div>
        <Link
          href={`/documents/${documentId}`}
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: "0.4rem",
            color: "var(--text-muted)",
            fontSize: "0.85rem",
            marginBottom: "0.75rem",
          }}
        >
          <ArrowLeft size={14} /> Back to Document Details
        </Link>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div>
            <h1 style={{ fontSize: "1.75rem" }}>Live Processing Monitor</h1>
            <p style={{ marginTop: "0.25rem", color: "var(--text-secondary)" }}>
              Job ID: <span style={{ fontFamily: "var(--font-mono)" }}>{statusInfo?.job_id || "Active"}</span>
            </p>
          </div>
          {statusInfo && <Badge status={statusInfo.status} />}
        </div>
      </div>

      {/* Main Status Card */}
      <Card style={{ padding: "2.5rem 2rem" }}>
        <div style={{ textAlign: "center", marginBottom: "2rem" }}>
          <div
            style={{
              width: "60px",
              height: "60px",
              borderRadius: "50%",
              background: isCompleted
                ? "rgba(16, 185, 129, 0.15)"
                : isFailed
                ? "rgba(244, 63, 94, 0.15)"
                : "rgba(99, 102, 241, 0.15)",
              color: isCompleted
                ? "var(--accent-emerald)"
                : isFailed
                ? "var(--accent-rose)"
                : "var(--accent-primary)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              margin: "0 auto 1rem",
            }}
          >
            {isCompleted ? (
              <CheckCircle2 size={32} />
            ) : isFailed ? (
              <AlertCircle size={32} />
            ) : (
              <Cpu size={32} />
            )}
          </div>
          <h2 style={{ fontSize: "1.3rem" }}>
            {isCompleted
              ? "All Stages Completed Successfully"
              : isFailed
              ? "Pipeline Encountered An Error"
              : `Active Stage: ${statusInfo?.stage || "Processing"}`}
          </h2>
          <p style={{ color: "var(--text-secondary)", fontSize: "0.875rem", marginTop: "0.25rem" }}>
            {statusInfo?.execution_time_ms
              ? `Elapsed: ${(statusInfo.execution_time_ms / 1000).toFixed(2)}s • Retries: ${statusInfo.retry_count} / ${statusInfo.max_retries}`
              : "Asynchronous Celery Execution"}
          </p>
        </div>

        {/* Progress Bar */}
        <div style={{ marginBottom: "2rem" }}>
          <ProgressBar progress={progressPercent} stage={statusInfo?.stage} />
        </div>

        {/* Pipeline Stage Indicators */}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(130px, 1fr))",
            gap: "0.75rem",
            marginBottom: "2rem",
          }}
        >
          {[
            { name: "Uploaded", icon: <UploadCloud size={16} />, active: true },
            {
              name: "Docling AST",
              icon: <FileCode size={16} />,
              active: progressPercent >= 40 || isCompleted,
            },
            {
              name: "Normalizer",
              icon: <FileCheck size={16} />,
              active: progressPercent >= 60 || isCompleted,
            },
            {
              name: "Chunker",
              icon: <Layers size={16} />,
              active: progressPercent >= 80 || isCompleted,
            },
            {
              name: "Vector Store",
              icon: <Sparkles size={16} />,
              active: isCompleted,
            },
          ].map((st) => (
            <div
              key={st.name}
              style={{
                background: st.active
                  ? "rgba(16, 185, 129, 0.08)"
                  : "rgba(255, 255, 255, 0.02)",
                border: `1px solid ${
                  st.active ? "rgba(16, 185, 129, 0.3)" : "var(--border-subtle)"
                }`,
                borderRadius: "var(--radius-md)",
                padding: "0.75rem 0.5rem",
                textAlign: "center",
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                gap: "0.3rem",
              }}
            >
              <div style={{ color: st.active ? "var(--accent-emerald)" : "var(--text-muted)" }}>
                {st.icon}
              </div>
              <div style={{ fontSize: "0.75rem", fontWeight: 600 }}>{st.name}</div>
            </div>
          ))}
        </div>

        {/* Errors Block */}
        {statusInfo?.errors && statusInfo.errors.length > 0 && (
          <div
            style={{
              background: "rgba(244, 63, 94, 0.12)",
              border: "1px solid rgba(244, 63, 94, 0.3)",
              borderRadius: "var(--radius-md)",
              padding: "1rem",
              marginBottom: "1.5rem",
            }}
          >
            <div style={{ color: "#fb7185", fontWeight: 600, marginBottom: "0.4rem" }}>
              Error Trace:
            </div>
            {statusInfo.errors.map((err, i) => (
              <div key={i} style={{ fontSize: "0.85rem", color: "#fca5a5" }}>
                <div><strong>{err.stage}</strong>: {err.error_message}</div>
              </div>
            ))}
          </div>
        )}

        <div style={{ display: "flex", justifyContent: "center", gap: "1rem" }}>
          <Button
            variant="secondary"
            onClick={() => router.push(`/documents/${documentId}`)}
          >
            Document Details
          </Button>
          {(isFailed || isCompleted) && (
            <Button
              variant="primary"
              onClick={handleRetry}
              isLoading={isRetrying}
              icon={<RotateCw size={15} />}
            >
              {isFailed ? "Retry Ingestion Pipeline" : "Re-run Processing"}
            </Button>
          )}
        </div>
      </Card>
    </div>
  );
}
