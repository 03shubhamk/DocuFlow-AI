"use client";

/**
 * DocuFlow AI — Dedicated Document Structure Hierarchy Explorer.
 */

import React, { useEffect, useState, use } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  FileText,
  ArrowLeft,
  Table as TableIcon,
  Image as ImageIcon,
  Hash,
} from "lucide-react";
import { api } from "../../../../lib/api-client";
import { useToast } from "../../../../context/ToastContext";
import { useAuth } from "../../../../context/AuthContext";
import { DocumentStructureResponse } from "../../../../types/api";
import { Card } from "../../../../components/ui/Card";
import { CardSkeleton } from "../../../../components/ui/Skeleton";

export default function DocumentStructurePage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const resolvedParams = use(params);
  const documentId = resolvedParams.id;

  const router = useRouter();
  const { isAuthenticated, isLoading: authLoading } = useAuth();
  const { error: toastError } = useToast();

  const [structure, setStructure] = useState<DocumentStructureResponse | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!authLoading && !isAuthenticated) {
      router.push("/login");
      return;
    }

    const fetchStructure = async () => {
      try {
        const res = await api.documents.getStructure(documentId);
        setStructure(res);
      } catch {
        toastError("Failed to fetch document structure.");
      } finally {
        setLoading(false);
      }
    };

    fetchStructure();
  }, [documentId, isAuthenticated, authLoading, router, toastError]);

  if (loading) {
    return <CardSkeleton />;
  }

  return (
    <div style={{ maxWidth: "1000px", margin: "0 auto", display: "flex", flexDirection: "column", gap: "2rem" }}>
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
        <h1 style={{ fontSize: "1.75rem" }}>Document Structure & Outline Tree</h1>
        <p style={{ marginTop: "0.25rem", color: "var(--text-secondary)" }}>
          {structure?.title || "Document Hierarchy"} • Extracted by IBM Docling 2.x
        </p>
      </div>

      {/* Structure Metrics */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: "1rem" }}>
        <Card>
          <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
            <FileText size={20} color="var(--accent-primary)" />
            <div>
              <div style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>PAGES</div>
              <div style={{ fontSize: "1.4rem", fontWeight: 700 }}>{structure?.page_count || 1}</div>
            </div>
          </div>
        </Card>

        <Card>
          <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
            <TableIcon size={20} color="var(--accent-emerald)" />
            <div>
              <div style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>TABLES</div>
              <div style={{ fontSize: "1.4rem", fontWeight: 700 }}>{structure?.table_count || 0}</div>
            </div>
          </div>
        </Card>

        <Card>
          <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
            <ImageIcon size={20} color="var(--accent-cyan)" />
            <div>
              <div style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>FIGURES</div>
              <div style={{ fontSize: "1.4rem", fontWeight: 700 }}>{structure?.figure_count || 0}</div>
            </div>
          </div>
        </Card>

        <Card>
          <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
            <Hash size={20} color="var(--accent-purple)" />
            <div>
              <div style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>WORD COUNT</div>
              <div style={{ fontSize: "1.4rem", fontWeight: 700 }}>{structure?.word_count || 0}</div>
            </div>
          </div>
        </Card>
      </div>

      {/* Hierarchy Outline Tree */}
      <Card title="Structural Section Outline">
        {structure && structure.section_hierarchy?.length > 0 ? (
          <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
            {structure.section_hierarchy.map((node, i) => (
              <div
                key={i}
                style={{
                  padding: "1rem 1.25rem",
                  background: "rgba(10, 15, 28, 0.7)",
                  border: "1px solid var(--border-subtle)",
                  borderLeft: `4px solid ${
                    node.level === 1
                      ? "var(--accent-primary)"
                      : node.level === 2
                      ? "var(--accent-cyan)"
                      : "var(--accent-purple)"
                  }`,
                  borderRadius: "var(--radius-md)",
                  marginLeft: `${Math.max(0, (node.level - 1) * 1.5)}rem`,
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                }}
              >
                <div>
                  <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                    <span
                      style={{
                        background: "rgba(255, 255, 255, 0.08)",
                        padding: "0.1rem 0.4rem",
                        borderRadius: "4px",
                        fontSize: "0.7rem",
                        fontWeight: 700,
                      }}
                    >
                      H{node.level}
                    </span>
                    <span style={{ fontWeight: 600, fontSize: "1rem" }}>{node.title}</span>
                  </div>
                  {node.section_path && (
                    <div style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginTop: "0.3rem" }}>
                      Path: {node.section_path}
                    </div>
                  )}
                </div>

                <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                  <span
                    style={{
                      background: "rgba(6, 182, 212, 0.12)",
                      color: "var(--accent-cyan)",
                      padding: "0.2rem 0.6rem",
                      borderRadius: "var(--radius-full)",
                      fontSize: "0.75rem",
                      fontWeight: 600,
                    }}
                  >
                    Page {node.page || 1}
                  </span>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p style={{ color: "var(--text-muted)", textAlign: "center", padding: "3rem" }}>
            No structural headings or section outline extracted for this document.
          </p>
        )}
      </Card>
    </div>
  );
}
