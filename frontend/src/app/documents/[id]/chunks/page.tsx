"use client";

/**
 * DocuFlow AI — Dedicated Document Chunks Deep Browser.
 */

import React, { useEffect, useState, use } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  ArrowLeft,
  Copy,
  Check,
  Search,
  ChevronLeft,
  ChevronRight,
} from "lucide-react";
import { api } from "../../../../lib/api-client";
import { useToast } from "../../../../context/ToastContext";
import { useAuth } from "../../../../context/AuthContext";
import { DocumentChunkSummary, PaginationMetadata } from "../../../../types/api";
import { Card } from "../../../../components/ui/Card";
import { Button } from "../../../../components/ui/Button";
import { TableSkeleton } from "../../../../components/ui/Skeleton";

export default function DocumentChunksPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const resolvedParams = use(params);
  const documentId = resolvedParams.id;

  const router = useRouter();
  const { isAuthenticated, isLoading: authLoading } = useAuth();
  const { success: toastSuccess, error: toastError } = useToast();

  const [chunks, setChunks] = useState<DocumentChunkSummary[]>([]);
  const [pagination, setPagination] = useState<PaginationMetadata>({
    page: 1,
    page_size: 15,
    total_items: 0,
    total_pages: 1,
    has_next: false,
    has_prev: false,
  });

  const [filterQuery, setFilterQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [copiedId, setCopiedId] = useState<string | null>(null);

  useEffect(() => {
    if (!authLoading && !isAuthenticated) {
      router.push("/login");
      return;
    }

    const fetchChunks = async () => {
      setLoading(true);
      try {
        const res = await api.documents.getChunks(documentId, {
          page: pagination.page,
          page_size: pagination.page_size,
        });
        setChunks(res.items || []);
        if (res.pagination) {
          setPagination(res.pagination);
        }
      } catch {
        toastError("Failed to fetch document chunks.");
      } finally {
        setLoading(false);
      }
    };

    fetchChunks();
  }, [documentId, pagination.page, pagination.page_size, isAuthenticated, authLoading, router, toastError]);

  const copyChunk = (chunk: DocumentChunkSummary) => {
    navigator.clipboard.writeText(chunk.content);
    setCopiedId(chunk.id);
    toastSuccess(`Chunk #${chunk.chunk_index} copied to clipboard.`);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const filteredChunks = filterQuery
    ? chunks.filter(
        (c) =>
          c.content.toLowerCase().includes(filterQuery.toLowerCase()) ||
          c.heading_hierarchy?.some((h) =>
            h.toLowerCase().includes(filterQuery.toLowerCase())
          )
      )
    : chunks;

  return (
    <div style={{ maxWidth: "1100px", margin: "0 auto", display: "flex", flexDirection: "column", gap: "2rem" }}>
      {/* Header */}
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
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "1rem" }}>
          <div>
            <h1 style={{ fontSize: "1.75rem" }}>Document Chunk Explorer</h1>
            <p style={{ marginTop: "0.25rem", color: "var(--text-secondary)" }}>
              Indexed vector fragments, tokens, and structural metadata.
            </p>
          </div>
          <div style={{ position: "relative", width: "260px" }}>
            <span
              style={{
                position: "absolute",
                left: "0.75rem",
                top: "50%",
                transform: "translateY(-50%)",
                color: "var(--text-muted)",
              }}
            >
              <Search size={15} />
            </span>
            <input
              type="text"
              placeholder="Filter chunks..."
              className="form-input"
              style={{ paddingLeft: "2.3rem", fontSize: "0.85rem" }}
              value={filterQuery}
              onChange={(e) => setFilterQuery(e.target.value)}
            />
          </div>
        </div>
      </div>

      {loading ? (
        <TableSkeleton rows={8} />
      ) : filteredChunks.length === 0 ? (
        <Card>
          <p style={{ color: "var(--text-muted)", textAlign: "center", padding: "3rem" }}>
            No chunks found matching filter.
          </p>
        </Card>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
          {filteredChunks.map((chunk) => (
            <Card key={chunk.id} style={{ padding: "1.25rem 1.5rem" }}>
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "flex-start",
                  marginBottom: "0.75rem",
                  flexWrap: "wrap",
                  gap: "0.5rem",
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: "0.6rem" }}>
                  <span
                    style={{
                      background: "rgba(99, 102, 241, 0.15)",
                      color: "#a5b4fc",
                      padding: "0.2rem 0.6rem",
                      borderRadius: "4px",
                      fontWeight: 700,
                      fontSize: "0.8rem",
                    }}
                  >
                    Chunk #{chunk.chunk_index}
                  </span>
                  <span
                    style={{
                      background: "rgba(6, 182, 212, 0.12)",
                      color: "var(--accent-cyan)",
                      padding: "0.2rem 0.55rem",
                      borderRadius: "4px",
                      fontSize: "0.75rem",
                      fontWeight: 600,
                    }}
                  >
                    Page {chunk.page_number}
                  </span>
                  <span style={{ fontSize: "0.8rem", color: "var(--text-muted)" }}>
                    {chunk.token_count} Tokens
                  </span>
                </div>

                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => copyChunk(chunk)}
                  icon={copiedId === chunk.id ? <Check size={14} /> : <Copy size={14} />}
                >
                  {copiedId === chunk.id ? "Copied" : "Copy Content"}
                </Button>
              </div>

              {chunk.heading_hierarchy && chunk.heading_hierarchy.length > 0 && (
                <div
                  style={{
                    fontSize: "0.75rem",
                    color: "var(--accent-primary)",
                    fontWeight: 600,
                    marginBottom: "0.6rem",
                  }}
                >
                  {chunk.heading_hierarchy.join(" > ")}
                </div>
              )}

              <p
                style={{
                  fontSize: "0.9rem",
                  color: "var(--text-primary)",
                  lineHeight: "1.65",
                  whiteSpace: "pre-wrap",
                }}
              >
                {chunk.content}
              </p>
            </Card>
          ))}

          {/* Pagination */}
          {pagination.total_pages > 1 && (
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                padding: "1rem 0",
              }}
            >
              <div style={{ fontSize: "0.85rem", color: "var(--text-muted)" }}>
                Page {pagination.page} of {pagination.total_pages} ({pagination.total_items} chunks)
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
    </div>
  );
}
