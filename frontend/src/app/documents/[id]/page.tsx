"use client";

/**
 * DocuFlow AI — Comprehensive Document Intelligence Details Workspace.
 */

import React, { useEffect, useState, use } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  FileText,
  Clock,
  Layers,
  Download,
  Trash2,
  Play,
  RotateCw,
  Copy,
  Check,
  Cpu,
  Table as TableIcon,
  Image as ImageIcon,
  AlertTriangle,
  FileCode,
  FolderTree,
} from "lucide-react";
import { api } from "../../../lib/api-client";
import { useToast } from "../../../context/ToastContext";
import { useAuth } from "../../../context/AuthContext";
import {
  DocumentChunkSummary,
  DocumentDetailResponse,
  DocumentStructureResponse,
  ProcessingStatusResponse,
} from "../../../types/api";
import { Card } from "../../../components/ui/Card";
import { Badge } from "../../../components/ui/Badge";
import { Button } from "../../../components/ui/Button";
import { Tabs } from "../../../components/ui/Tabs";
import { ConfirmDialog } from "../../../components/ui/ConfirmDialog";
import { CardSkeleton } from "../../../components/ui/Skeleton";

export default function DocumentDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const resolvedParams = use(params);
  const documentId = resolvedParams.id;

  const router = useRouter();
  const { isAuthenticated, isLoading: authLoading } = useAuth();
  const { success: toastSuccess, error: toastError } = useToast();

  const [document, setDocument] = useState<DocumentDetailResponse | null>(null);
  const [structure, setStructure] = useState<DocumentStructureResponse | null>(null);
  const [chunks, setChunks] = useState<DocumentChunkSummary[]>([]);
  const [statusInfo, setStatusInfo] = useState<ProcessingStatusResponse | null>(null);
  const [markdownContent, setMarkdownContent] = useState<string>("");

  const [activeTab, setActiveTab] = useState("overview");
  const [loading, setLoading] = useState(true);
  const [copiedMd, setCopiedMd] = useState(false);

  // Actions
  const [isProcessing, setIsProcessing] = useState(false);
  const [isReindexing, setIsReindexing] = useState(false);
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);

  useEffect(() => {
    if (!authLoading && !isAuthenticated) {
      router.push("/login");
      return;
    }

    const loadDocumentData = async () => {
      setLoading(true);
      try {
        const [docRes, structRes, chunkRes, statusRes] = await Promise.allSettled([
          api.documents.getById(documentId),
          api.documents.getStructure(documentId),
          api.documents.getChunks(documentId, { page: 1, page_size: 20 }),
          api.documents.getStatus(documentId),
        ]);

        if (docRes.status === "fulfilled") {
          setDocument(docRes.value);
        }
        if (structRes.status === "fulfilled") {
          setStructure(structRes.value);
        }
        if (chunkRes.status === "fulfilled") {
          setChunks(chunkRes.value.items || []);
        }
        if (statusRes.status === "fulfilled") {
          setStatusInfo(statusRes.value);
        }

        // Try to fetch markdown asset if available
        try {
          const md = await api.documents.fetchAssetText(documentId, "markdown");
          setMarkdownContent(md);
        } catch {
          // No markdown artifact yet
        }
      } catch {
        toastError("Failed to load document details.");
      } finally {
        setLoading(false);
      }
    };

    if (isAuthenticated) {
      loadDocumentData();
    }
  }, [documentId, isAuthenticated, authLoading, router, toastError]);

  const handleProcess = async () => {
    setIsProcessing(true);
    try {
      await api.documents.process(documentId);
      toastSuccess("Processing job triggered.");
      const updatedStatus = await api.documents.getStatus(documentId);
      setStatusInfo(updatedStatus);
    } catch {
      toastError("Failed to trigger processing.");
    } finally {
      setIsProcessing(false);
    }
  };

  const handleReindex = async () => {
    setIsReindexing(true);
    try {
      const res = await api.documents.reindex(documentId);
      toastSuccess(`Reindexed ${res.chunks_indexed} vectors into Qdrant collection.`);
    } catch {
      toastError("Failed to reindex vectors.");
    } finally {
      setIsReindexing(false);
    }
  };

  const handleDelete = async () => {
    setIsDeleting(true);
    try {
      await api.documents.delete(documentId);
      toastSuccess("Document deleted.");
      router.push("/documents");
    } catch {
      toastError("Failed to delete document.");
    } finally {
      setIsDeleting(false);
    }
  };

  const copyMarkdownToClipboard = () => {
    if (!markdownContent) return;
    navigator.clipboard.writeText(markdownContent);
    setCopiedMd(true);
    setTimeout(() => setCopiedMd(false), 2000);
    toastSuccess("Markdown copied to clipboard.");
  };

  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  if (loading || !document) {
    return (
      <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
        <CardSkeleton />
        <CardSkeleton />
      </div>
    );
  }

  const tabs = [
    { id: "overview", label: "Overview & Metadata", icon: <FileText size={15} /> },
    { id: "markdown", label: "Extracted Markdown", icon: <FileCode size={15} /> },
    {
      id: "structure",
      label: "Document Structure",
      icon: <FolderTree size={15} />,
      count: structure?.section_hierarchy?.length,
    },
    {
      id: "chunks",
      label: "Indexed Chunks",
      icon: <Layers size={15} />,
      count: chunks.length,
    },
    {
      id: "assets",
      label: "Tables & Figures",
      icon: <TableIcon size={15} />,
      count: (structure?.table_count || 0) + (structure?.figure_count || 0),
    },
    {
      id: "timeline",
      label: "Processing Timeline",
      icon: <Clock size={15} />,
      count: statusInfo?.errors?.length ? statusInfo.errors.length : undefined,
    },
  ];

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "1.75rem" }}>
      {/* Header Banner */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "flex-start",
          flexWrap: "wrap",
          gap: "1rem",
        }}
      >
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", marginBottom: "0.5rem" }}>
            <Badge status={document.latest_job?.status || "UPLOADED"} />
            <span
              style={{
                background: "rgba(255, 255, 255, 0.06)",
                padding: "0.2rem 0.6rem",
                borderRadius: "4px",
                fontSize: "0.75rem",
                fontWeight: 600,
              }}
            >
              {document.file_type?.toUpperCase()}
            </span>
            <span style={{ fontSize: "0.8rem", color: "var(--text-muted)" }}>
              {formatFileSize(document.file_size_bytes)}
            </span>
          </div>
          <h1 style={{ fontSize: "1.75rem" }}>{document.title || document.original_filename}</h1>
          <p style={{ marginTop: "0.2rem", fontSize: "0.85rem", color: "var(--text-muted)" }}>
            ID: <span style={{ fontFamily: "var(--font-mono)" }}>{document.id}</span> • Created {new Date(document.created_at).toLocaleString()}
          </p>
        </div>

        {/* Action Toolbar */}
        <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
          <Button
            variant="secondary"
            size="sm"
            onClick={handleProcess}
            isLoading={isProcessing}
            icon={<Play size={14} />}
          >
            Process
          </Button>
          <Button
            variant="secondary"
            size="sm"
            onClick={handleReindex}
            isLoading={isReindexing}
            icon={<RotateCw size={14} />}
          >
            Reindex
          </Button>
          <Link
            href={`/documents/${document.id}/status`}
            className="btn btn-secondary btn-sm"
          >
            <Cpu size={14} />
            <span>Monitor Job</span>
          </Link>
          <Button
            variant="danger"
            size="sm"
            onClick={() => setShowDeleteModal(true)}
            icon={<Trash2 size={14} />}
          >
            Delete
          </Button>
        </div>
      </div>

      {/* Workspace Tabs */}
      <Tabs tabs={tabs} activeTab={activeTab} onChange={setActiveTab} />

      {/* Tab 1: Overview & Metadata */}
      {activeTab === "overview" && (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))", gap: "1.5rem" }}>
          <Card title="Document Specifications">
            <div style={{ display: "flex", flexDirection: "column", gap: "0.85rem", fontSize: "0.9rem" }}>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span style={{ color: "var(--text-muted)" }}>Original Filename</span>
                <span style={{ fontWeight: 600 }}>{document.original_filename}</span>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span style={{ color: "var(--text-muted)" }}>File Format</span>
                <span>{document.file_type?.toUpperCase()}</span>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span style={{ color: "var(--text-muted)" }}>Total File Size</span>
                <span>{formatFileSize(document.file_size_bytes)}</span>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span style={{ color: "var(--text-muted)" }}>Page Count</span>
                <span>{structure?.page_count || 1} Pages</span>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span style={{ color: "var(--text-muted)" }}>Extracted Tables</span>
                <span>{structure?.table_count || 0}</span>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span style={{ color: "var(--text-muted)" }}>Extracted Figures</span>
                <span>{structure?.figure_count || 0}</span>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span style={{ color: "var(--text-muted)" }}>Language</span>
                <span>{structure?.language || "English (detected)"}</span>
              </div>
            </div>
          </Card>

          <Card title="Version History & Storage Assets">
            <div style={{ marginBottom: "1.25rem" }}>
              <div style={{ fontSize: "0.8rem", fontWeight: 600, color: "var(--text-muted)", marginBottom: "0.5rem" }}>
                VERSIONS ({document.versions.length})
              </div>
              {document.versions.map((ver) => (
                <div
                  key={ver.id}
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    padding: "0.6rem 0",
                    borderBottom: "1px solid var(--border-subtle)",
                    fontSize: "0.85rem",
                  }}
                >
                  <span>Version {ver.version_number}</span>
                  <span style={{ color: "var(--text-muted)", fontFamily: "var(--font-mono)", fontSize: "0.75rem" }}>
                    {(ver.checksum_sha256 || ver.checksum || "").substring(0, 12)}...
                  </span>
                </div>
              ))}
            </div>

            <div>
              <div style={{ fontSize: "0.8rem", fontWeight: 600, color: "var(--text-muted)", marginBottom: "0.5rem" }}>
                EXTRACTED ARTIFACTS ({document.assets.length})
              </div>
              {document.assets.length === 0 ? (
                <p style={{ fontSize: "0.85rem", color: "var(--text-muted)" }}>
                  No stored artifacts yet. Run the processing pipeline to generate Markdown and ASTs.
                </p>
              ) : (
                <div style={{ display: "flex", flexDirection: "column", gap: "0.4rem" }}>
                  {document.assets.map((ast) => (
                    <div
                      key={ast.id}
                      style={{
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "center",
                        padding: "0.5rem 0.75rem",
                        background: "rgba(255, 255, 255, 0.02)",
                        borderRadius: "var(--radius-sm)",
                        fontSize: "0.85rem",
                      }}
                    >
                      <span style={{ fontWeight: 600 }}>{ast.asset_type}</span>
                      <a
                        href={api.documents.getAssetDownloadUrl(document.id, ast.asset_type)}
                        target="_blank"
                        rel="noreferrer"
                        className="btn btn-ghost btn-sm"
                        style={{ color: "var(--accent-primary)" }}
                      >
                        <Download size={13} />
                        <span>Download</span>
                      </a>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </Card>
        </div>
      )}

      {/* Tab 2: Extracted Markdown */}
      {activeTab === "markdown" && (
        <Card
          title="Extracted Markdown Representation"
          subtitle="Normalized Docling markdown AST output"
          action={
            <Button
              variant="secondary"
              size="sm"
              onClick={copyMarkdownToClipboard}
              icon={copiedMd ? <Check size={14} /> : <Copy size={14} />}
            >
              {copiedMd ? "Copied" : "Copy Markdown"}
            </Button>
          }
        >
          {markdownContent ? (
            <div
              style={{
                background: "rgba(10, 15, 28, 0.9)",
                border: "1px solid var(--border-subtle)",
                borderRadius: "var(--radius-md)",
                padding: "1.5rem",
                fontFamily: "var(--font-mono)",
                fontSize: "0.875rem",
                lineHeight: "1.7",
                color: "#e2e8f0",
                maxHeight: "600px",
                overflowY: "auto",
                whiteSpace: "pre-wrap",
              }}
            >
              {markdownContent}
            </div>
          ) : (
            <div style={{ textAlign: "center", padding: "3rem 1rem", color: "var(--text-muted)" }}>
              <p>No markdown asset found for this document version.</p>
              <Button
                variant="primary"
                size="sm"
                onClick={handleProcess}
                style={{ marginTop: "1rem" }}
              >
                Run Processor Pipeline
              </Button>
            </div>
          )}
        </Card>
      )}

      {/* Tab 3: Document Structure */}
      {activeTab === "structure" && (
        <Card
          title="Document Outline & Structural Hierarchy"
          subtitle="Extracted headings, sections, and structural navigation tree"
          action={
            <Link
              href={`/documents/${document.id}/structure`}
              className="btn btn-secondary btn-sm"
            >
              Dedicated View
            </Link>
          }
        >
          {structure && structure.section_hierarchy?.length > 0 ? (
            <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
              {structure.section_hierarchy.map((sec, idx) => (
                <div
                  key={idx}
                  style={{
                    padding: "0.75rem 1rem",
                    background: "rgba(255, 255, 255, 0.02)",
                    borderLeft: `3px solid ${
                      sec.level === 1 ? "var(--accent-primary)" : "var(--accent-cyan)"
                    }`,
                    borderRadius: "var(--radius-sm)",
                    marginLeft: `${(sec.level - 1) * 1.5}rem`,
                  }}
                >
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                    <span style={{ fontWeight: 600, fontSize: "0.95rem" }}>{sec.title}</span>
                    <span style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>
                      Page {sec.page || 1} • Level H{sec.level}
                    </span>
                  </div>
                  {sec.section_path && (
                    <div style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginTop: "0.2rem" }}>
                      {sec.section_path}
                    </div>
                  )}
                </div>
              ))}
            </div>
          ) : (
            <p style={{ color: "var(--text-muted)", padding: "2rem", textAlign: "center" }}>
              No structural hierarchy parsed yet.
            </p>
          )}
        </Card>
      )}

      {/* Tab 4: Indexed Chunks */}
      {activeTab === "chunks" && (
        <Card
          title={`Document Chunks (${chunks.length})`}
          subtitle="Semantic vector chunks stored and indexed in Qdrant"
          action={
            <Link
              href={`/documents/${document.id}/chunks`}
              className="btn btn-secondary btn-sm"
            >
              Deep Chunk Browser
            </Link>
          }
        >
          {chunks.length === 0 ? (
            <p style={{ color: "var(--text-muted)", padding: "2rem", textAlign: "center" }}>
              No indexed chunks available.
            </p>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
              {chunks.slice(0, 10).map((chunk) => (
                <div
                  key={chunk.id}
                  style={{
                    background: "rgba(10, 15, 28, 0.8)",
                    border: "1px solid var(--border-subtle)",
                    borderRadius: "var(--radius-md)",
                    padding: "1rem 1.25rem",
                  }}
                >
                  <div
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "center",
                      marginBottom: "0.5rem",
                      fontSize: "0.8rem",
                    }}
                  >
                    <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                      <span
                        style={{
                          background: "rgba(99, 102, 241, 0.15)",
                          color: "#a5b4fc",
                          padding: "0.15rem 0.5rem",
                          borderRadius: "4px",
                          fontWeight: 700,
                        }}
                      >
                        Chunk #{chunk.chunk_index}
                      </span>
                      <span style={{ color: "var(--text-muted)" }}>
                        Page {chunk.page_number}
                      </span>
                    </div>
                    <span style={{ color: "var(--accent-purple)", fontWeight: 600 }}>
                      {chunk.token_count} Tokens
                    </span>
                  </div>

                  {chunk.heading_hierarchy?.length > 0 && (
                    <div
                      style={{
                        fontSize: "0.75rem",
                        color: "var(--accent-cyan)",
                        marginBottom: "0.5rem",
                        display: "flex",
                        gap: "0.3rem",
                      }}
                    >
                      {chunk.heading_hierarchy.join(" > ")}
                    </div>
                  )}

                  <p
                    style={{
                      fontSize: "0.875rem",
                      color: "var(--text-primary)",
                      lineHeight: "1.6",
                    }}
                  >
                    {chunk.content}
                  </p>
                </div>
              ))}
            </div>
          )}
        </Card>
      )}

      {/* Tab 5: Tables & Figures */}
      {activeTab === "assets" && (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))", gap: "1.5rem" }}>
          <Card title="Extracted Tables" subtitle="Preserved tabular markdown structures">
            <div style={{ padding: "1.5rem", textAlign: "center", color: "var(--text-muted)" }}>
              <TableIcon size={32} style={{ marginBottom: "0.75rem" }} />
              <div>Total Tables: {structure?.table_count || 0}</div>
              <p style={{ fontSize: "0.8rem", marginTop: "0.25rem" }}>
                Tables are parsed atomically and preserved with Markdown grid headers.
              </p>
            </div>
          </Card>

          <Card title="Extracted Figures & Diagrams" subtitle="Image assets with layout provenance">
            <div style={{ padding: "1.5rem", textAlign: "center", color: "var(--text-muted)" }}>
              <ImageIcon size={32} style={{ marginBottom: "0.75rem" }} />
              <div>Total Figures: {structure?.figure_count || 0}</div>
              <p style={{ fontSize: "0.8rem", marginTop: "0.25rem" }}>
                Figures and charts extracted into PNG asset storage.
              </p>
            </div>
          </Card>
        </div>
      )}

      {/* Tab 6: Processing Timeline */}
      {activeTab === "timeline" && (
        <Card title="Ingestion Pipeline Execution Log">
          {statusInfo?.errors && statusInfo.errors.length > 0 ? (
            <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
              <div
                style={{
                  background: "rgba(244, 63, 94, 0.12)",
                  border: "1px solid rgba(244, 63, 94, 0.3)",
                  borderRadius: "var(--radius-md)",
                  padding: "1rem",
                  color: "#fb7185",
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", fontWeight: 600 }}>
                  <AlertTriangle size={18} />
                  <span>Pipeline Errors ({statusInfo.errors.length})</span>
                </div>
                {statusInfo.errors.map((err, idx) => (
                  <div key={idx} style={{ marginTop: "0.5rem", fontSize: "0.85rem" }}>
                    <div><strong>Stage:</strong> {err.stage} ({err.error_type})</div>
                    <div>{err.error_message}</div>
                    {err.traceback_snippet && (
                      <pre
                        style={{
                          marginTop: "0.4rem",
                          background: "rgba(0, 0, 0, 0.3)",
                          padding: "0.5rem",
                          borderRadius: "4px",
                          fontSize: "0.75rem",
                          overflowX: "auto",
                        }}
                      >
                        {err.traceback_snippet}
                      </pre>
                    )}
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <div style={{ padding: "1rem 0" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", color: "var(--accent-emerald)" }}>
                <Check size={18} />
                <span style={{ fontWeight: 600 }}>Pipeline completed with 0 errors</span>
              </div>
              <p style={{ color: "var(--text-muted)", fontSize: "0.85rem", marginTop: "0.4rem" }}>
                Execution Time: {statusInfo?.execution_time_ms ? `${(statusInfo.execution_time_ms / 1000).toFixed(2)}s` : "Normal"} • Status: {statusInfo?.status}
              </p>
            </div>
          )}
        </Card>
      )}

      {/* Delete Confirmation Modal */}
      <ConfirmDialog
        isOpen={showDeleteModal}
        onClose={() => setShowDeleteModal(false)}
        onConfirm={handleDelete}
        isLoading={isDeleting}
        title="Delete Document"
        message={`Are you sure you want to permanently delete "${document.title || document.original_filename}"? All vectors and extracted assets will be removed.`}
        confirmLabel="Confirm Deletion"
        variant="danger"
      />
    </div>
  );
}
