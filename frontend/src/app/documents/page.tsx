"use client";

/**
 * DocuFlow AI — Documents Catalog & Management Page.
 */

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  FileText,
  Search,
  Upload,
  Trash2,
  Play,
  RotateCw,
  ExternalLink,
  ChevronLeft,
  ChevronRight,
  RefreshCw,
} from "lucide-react";
import { api } from "../../lib/api-client";
import { useToast } from "../../context/ToastContext";
import { useAuth } from "../../context/AuthContext";
import { DocumentSummary, PaginationMetadata } from "../../types/api";
import { Card } from "../../components/ui/Card";
import { Badge } from "../../components/ui/Badge";
import { Button } from "../../components/ui/Button";
import { TableSkeleton } from "../../components/ui/Skeleton";
import { EmptyState } from "../../components/ui/EmptyState";
import { ConfirmDialog } from "../../components/ui/ConfirmDialog";

export default function DocumentsPage() {
  const router = useRouter();
  const { isAuthenticated, isLoading: authLoading } = useAuth();
  const { success: toastSuccess, error: toastError } = useToast();

  const [documents, setDocuments] = useState<DocumentSummary[]>([]);
  const [pagination, setPagination] = useState<PaginationMetadata>({
    page: 1,
    page_size: 10,
    total_items: 0,
    total_pages: 1,
    has_next: false,
    has_prev: false,
  });

  const [searchQuery, setSearchQuery] = useState("");
  const [fileTypeFilter, setFileTypeFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState("all");
  const [sortBy, setSortBy] = useState("created_at");
  const [sortDesc, setSortDesc] = useState(true);
  const [loading, setLoading] = useState(true);

  // Modal states
  const [deleteDocId, setDeleteDocId] = useState<string | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);

  useEffect(() => {
    if (!authLoading && !isAuthenticated) {
      router.push("/login");
      return;
    }
    if (!isAuthenticated) return;

    let mounted = true;
    const loadDocs = async () => {
      try {
        const res = await api.documents.list({
          page: pagination.page,
          page_size: pagination.page_size,
          search: searchQuery || undefined,
          file_type: fileTypeFilter !== "all" ? fileTypeFilter : undefined,
          status: statusFilter !== "all" ? statusFilter : undefined,
          sort_by: sortBy,
          sort_desc: sortDesc,
        });
        if (mounted) {
          setDocuments(res.items || []);
          if (res.pagination) {
            setPagination(res.pagination);
          }
          setLoading(false);
        }
      } catch {
        if (mounted) {
          toastError("Failed to fetch documents list.");
          setLoading(false);
        }
      }
    };

    loadDocs();
    return () => {
      mounted = false;
    };
  }, [
    isAuthenticated,
    authLoading,
    router,
    pagination.page,
    pagination.page_size,
    searchQuery,
    fileTypeFilter,
    statusFilter,
    sortBy,
    sortDesc,
    toastError,
  ]);

  const handleRefresh = async () => {
    setLoading(true);
    try {
      const res = await api.documents.list({
        page: pagination.page,
        page_size: pagination.page_size,
        search: searchQuery || undefined,
        file_type: fileTypeFilter !== "all" ? fileTypeFilter : undefined,
        status: statusFilter !== "all" ? statusFilter : undefined,
        sort_by: sortBy,
        sort_desc: sortDesc,
      });
      setDocuments(res.items || []);
      if (res.pagination) {
        setPagination(res.pagination);
      }
    } catch {
      toastError("Failed to fetch documents list.");
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteConfirm = async () => {
    if (!deleteDocId) return;
    setIsDeleting(true);
    try {
      await api.documents.delete(deleteDocId);
      toastSuccess("Document deleted successfully.");
      setDeleteDocId(null);
      handleRefresh();
    } catch {
      toastError("Failed to delete document.");
    } finally {
      setIsDeleting(false);
    }
  };

  const handleTriggerProcess = async (docId: string) => {
    try {
      await api.documents.process(docId);
      toastSuccess("Processing queued asynchronously.");
      handleRefresh();
    } catch {
      toastError("Failed to queue document processing.");
    }
  };

  const handleReindex = async (docId: string) => {
    try {
      const res = await api.documents.reindex(docId);
      toastSuccess(`Reindexed ${res.chunks_indexed} chunks into vector store.`);
      handleRefresh();
    } catch {
      toastError("Failed to reindex document.");
    }
  };

  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "1.75rem" }}>
      {/* Header */}
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
          <h1 style={{ fontSize: "1.75rem" }}>Documents Catalog</h1>
          <p style={{ marginTop: "0.25rem" }}>
            Manage, filter, re-process, and inspect ingested multi-format assets.
          </p>
        </div>
        <div style={{ display: "flex", gap: "0.75rem" }}>
          <Button
            variant="secondary"
            onClick={handleRefresh}
            icon={<RefreshCw size={15} />}
          >
            Refresh
          </Button>
          <Button
            variant="primary"
            onClick={() => router.push("/documents/upload")}
            icon={<Upload size={15} />}
          >
            Upload New File
          </Button>
        </div>
      </div>

      {/* Filter & Search Bar */}
      <Card style={{ padding: "1.25rem" }}>
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
            gap: "1rem",
            alignItems: "center",
          }}
        >
          {/* Search Input */}
          <div style={{ position: "relative", gridColumn: "span 2" }}>
            <span
              style={{
                position: "absolute",
                left: "0.85rem",
                top: "50%",
                transform: "translateY(-50%)",
                color: "var(--text-muted)",
              }}
            >
              <Search size={16} />
            </span>
            <input
              type="text"
              placeholder="Search filename or title..."
              className="form-input"
              style={{ paddingLeft: "2.4rem" }}
              value={searchQuery}
              onChange={(e) => {
                setSearchQuery(e.target.value);
                setPagination((prev) => ({ ...prev, page: 1 }));
              }}
            />
          </div>

          {/* Format Filter */}
          <div>
            <select
              className="form-select"
              value={fileTypeFilter}
              onChange={(e) => {
                setFileTypeFilter(e.target.value);
                setPagination((prev) => ({ ...prev, page: 1 }));
              }}
            >
              <option value="all">All Formats</option>
              <option value="pdf">PDF (.pdf)</option>
              <option value="docx">Word (.docx)</option>
              <option value="pptx">PowerPoint (.pptx)</option>
              <option value="xlsx">Excel (.xlsx)</option>
              <option value="html">HTML (.html)</option>
              <option value="md">Markdown (.md)</option>
              <option value="txt">Plain Text (.txt)</option>
              <option value="png">PNG Image (.png)</option>
              <option value="jpg">JPEG Image (.jpg)</option>
              <option value="tiff">TIFF Image (.tiff)</option>
            </select>
          </div>

          {/* Status Filter */}
          <div>
            <select
              className="form-select"
              value={statusFilter}
              onChange={(e) => {
                setStatusFilter(e.target.value);
                setPagination((prev) => ({ ...prev, page: 1 }));
              }}
            >
              <option value="all">All Statuses</option>
              <option value="COMPLETED">Completed</option>
              <option value="PROCESSING">Processing</option>
              <option value="QUEUED">Queued</option>
              <option value="FAILED">Failed</option>
            </select>
          </div>

          {/* Sort By */}
          <div>
            <select
              className="form-select"
              value={`${sortBy}:${sortDesc ? "desc" : "asc"}`}
              onChange={(e) => {
                const [sb, sd] = e.target.value.split(":");
                setSortBy(sb);
                setSortDesc(sd === "desc");
              }}
            >
              <option value="created_at:desc">Newest Uploads</option>
              <option value="created_at:asc">Oldest Uploads</option>
              <option value="title:asc">Title (A-Z)</option>
              <option value="file_size_bytes:desc">Size (Largest)</option>
            </select>
          </div>
        </div>
      </Card>

      {/* Document Table */}
      {loading ? (
        <TableSkeleton rows={8} />
      ) : documents.length === 0 ? (
        <Card>
          <EmptyState
            icon={<FileText />}
            title="No matching documents found"
            description="Adjust your search criteria or upload a new document to begin extraction."
            actionLabel="Upload Document"
            onAction={() => router.push("/documents/upload")}
          />
        </Card>
      ) : (
        <div className="table-container">
          <table className="table">
            <thead>
              <tr>
                <th>Document</th>
                <th>Format</th>
                <th>File Size</th>
                <th>Status</th>
                <th>Uploaded</th>
                <th>Execution</th>
                <th style={{ textAlign: "right" }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {documents.map((doc) => (
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
                  <td style={{ fontSize: "0.8rem", color: "var(--text-muted)" }}>
                    {doc.latest_job?.execution_time_ms
                      ? `${(doc.latest_job.execution_time_ms / 1000).toFixed(2)}s`
                      : "—"}
                  </td>
                  <td style={{ textAlign: "right" }}>
                    <div
                      style={{
                        display: "inline-flex",
                        gap: "0.35rem",
                        alignItems: "center",
                      }}
                    >
                      <Link
                        href={`/documents/${doc.id}`}
                        className="btn btn-secondary btn-sm"
                        title="View Details"
                      >
                        <ExternalLink size={14} />
                      </Link>
                      <button
                        onClick={() => handleTriggerProcess(doc.id)}
                        className="btn btn-ghost btn-sm"
                        title="Run Processing Pipeline"
                      >
                        <Play size={14} />
                      </button>
                      <button
                        onClick={() => handleReindex(doc.id)}
                        className="btn btn-ghost btn-sm"
                        title="Reindex Vectors"
                      >
                        <RotateCw size={14} />
                      </button>
                      <button
                        onClick={() => setDeleteDocId(doc.id)}
                        className="btn btn-ghost btn-sm"
                        style={{ color: "var(--accent-rose)" }}
                        title="Delete Document"
                      >
                        <Trash2 size={14} />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          {/* Pagination Controls */}
          {pagination.total_pages > 1 && (
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                padding: "1rem 1.5rem",
                borderTop: "1px solid var(--border-subtle)",
                fontSize: "0.85rem",
                color: "var(--text-secondary)",
              }}
            >
              <div>
                Showing Page {pagination.page} of {pagination.total_pages} ({pagination.total_items} total)
              </div>
              <div style={{ display: "flex", gap: "0.5rem" }}>
                <Button
                  variant="secondary"
                  size="sm"
                  disabled={!pagination.has_prev}
                  onClick={() =>
                    setPagination((prev) => ({ ...prev, page: prev.page - 1 }))
                  }
                  icon={<ChevronLeft size={14} />}
                >
                  Previous
                </Button>
                <Button
                  variant="secondary"
                  size="sm"
                  disabled={!pagination.has_next}
                  onClick={() =>
                    setPagination((prev) => ({ ...prev, page: prev.page + 1 }))
                  }
                >
                  Next <ChevronRight size={14} />
                </Button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Delete Confirmation Dialog */}
      <ConfirmDialog
        isOpen={!!deleteDocId}
        onClose={() => setDeleteDocId(null)}
        onConfirm={handleDeleteConfirm}
        isLoading={isDeleting}
        title="Delete Document"
        message="Are you sure you want to delete this document? This will soft-delete the document record, remove all associated chunks and embeddings from the vector store, and delete extracted assets."
        confirmLabel="Delete Permanently"
        variant="danger"
      />
    </div>
  );
}
