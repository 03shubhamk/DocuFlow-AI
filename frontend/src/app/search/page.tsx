"use client";

/**
 * DocuFlow AI — Universal Semantic & Hybrid Document Search Interface.
 */

import React, { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  Search,
  Sparkles,
  SlidersHorizontal,
  FileText,
  Copy,
  Check,
  Zap,
  ExternalLink,
  ChevronRight,
} from "lucide-react";
import { api } from "../../lib/api-client";
import { useToast } from "../../context/ToastContext";
import { useAuth } from "../../context/AuthContext";
import {
  DocumentSummary,
  SearchResultItem,
  SearchStrategy,
} from "../../types/api";
import { Card } from "../../components/ui/Card";
import { Button } from "../../components/ui/Button";
import { EmptyState } from "../../components/ui/EmptyState";
import { Skeleton } from "../../components/ui/Skeleton";

export default function SearchPage() {
  const router = useRouter();
  const { isAuthenticated, isLoading: authLoading } = useAuth();
  const { success: toastSuccess, error: toastError } = useToast();

  const [query, setQuery] = useState("");
  const [strategy, setStrategy] = useState<SearchStrategy>("dense");
  const [topK, setTopK] = useState(10);
  const [scoreThreshold, setScoreThreshold] = useState<number>(0.0);
  const [selectedDocId, setSelectedDocId] = useState<string>("all");
  const [pageFilter, setPageFilter] = useState<string>("");

  const [documents, setDocuments] = useState<DocumentSummary[]>([]);
  const [results, setResults] = useState<SearchResultItem[]>([]);
  const [totalResults, setTotalResults] = useState(0);
  const [durationMs, setDurationMs] = useState<number | null>(null);
  const [isSearching, setIsSearching] = useState(false);
  const [hasSearched, setHasSearched] = useState(false);
  const [showFilters, setShowFilters] = useState(false);
  const [copiedId, setCopiedId] = useState<string | null>(null);

  useEffect(() => {
    if (!authLoading && !isAuthenticated) {
      router.push("/login");
      return;
    }

    const loadDocuments = async () => {
      try {
        const res = await api.documents.list({ page: 1, page_size: 50 });
        setDocuments(res.items || []);
      } catch {
        // failed to load doc list
      }
    };

    if (isAuthenticated) {
      loadDocuments();
    }
  }, [isAuthenticated, authLoading, router]);

  const handleSearch = useCallback(async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!query.trim()) return;

    setIsSearching(true);
    setHasSearched(true);

    try {
      const res = await api.search.query({
        query: query.trim(),
        strategy,
        top_k: topK,
        score_threshold: scoreThreshold > 0 ? scoreThreshold : undefined,
        document_ids: selectedDocId !== "all" ? [selectedDocId] : undefined,
        page: pageFilter ? parseInt(pageFilter, 10) : undefined,
      });

      setResults(res.results || []);
      setTotalResults(res.total_results || 0);
      setDurationMs(res.duration_ms || 0);
    } catch {
      toastError("Search query failed. Check backend connection.");
    } finally {
      setIsSearching(false);
    }
  }, [query, strategy, topK, scoreThreshold, selectedDocId, pageFilter, toastError]);

  const copyResultText = (item: SearchResultItem) => {
    navigator.clipboard.writeText(item.text);
    setCopiedId(item.chunk_id);
    toastSuccess("Snippet copied to clipboard.");
    setTimeout(() => setCopiedId(null), 2000);
  };

  /** Highlight query terms in extracted text snippets */
  const renderHighlightedText = (text: string, searchTerms: string) => {
    if (!searchTerms.trim()) return text;
    const terms = searchTerms
      .trim()
      .split(/\s+/)
      .filter((t) => t.length > 2);
    if (terms.length === 0) return text;

    const regex = new RegExp(`(${terms.map((t) => t.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("|")})`, "gi");
    const parts = text.split(regex);

    return parts.map((part, i) =>
      regex.test(part) ? (
        <mark
          key={i}
          style={{
            background: "rgba(99, 102, 241, 0.35)",
            color: "#fff",
            padding: "0.1rem 0.25rem",
            borderRadius: "3px",
            fontWeight: 600,
          }}
        >
          {part}
        </mark>
      ) : (
        part
      )
    );
  };

  return (
    <div style={{ maxWidth: "1100px", margin: "0 auto", display: "flex", flexDirection: "column", gap: "2rem" }}>
      {/* Header */}
      <div>
        <h1 style={{ fontSize: "1.75rem" }}>
          <span className="text-gradient">Semantic & Hybrid</span> Document Search
        </h1>
        <p style={{ marginTop: "0.25rem", color: "var(--text-secondary)" }}>
          Query across embeddings using dense cosine vectors or hybrid BM25 lexical fusion with metadata scoping.
        </p>
      </div>

      {/* Main Search Bar & Controls */}
      <Card style={{ padding: "1.5rem" }}>
        <form onSubmit={handleSearch}>
          <div style={{ display: "flex", gap: "0.75rem", alignItems: "center" }}>
            <div style={{ position: "relative", flex: 1 }}>
              <span
                style={{
                  position: "absolute",
                  left: "1rem",
                  top: "50%",
                  transform: "translateY(-50%)",
                  color: "var(--text-muted)",
                }}
              >
                <Search size={18} />
              </span>
              <input
                type="text"
                placeholder="Ask questions or search conceptual keywords (e.g. 'operating margins Q3', 'financial risk factors')..."
                className="form-input"
                style={{
                  paddingLeft: "2.75rem",
                  paddingRight: "1rem",
                  height: "48px",
                  fontSize: "1rem",
                }}
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                autoFocus
              />
            </div>

            <Button
              type="submit"
              variant="primary"
              size="lg"
              isLoading={isSearching}
              icon={<Sparkles size={16} />}
            >
              Search
            </Button>

            <Button
              type="button"
              variant={showFilters ? "secondary" : "ghost"}
              onClick={() => setShowFilters((prev) => !prev)}
              title="Toggle Advanced Search Filters"
              icon={<SlidersHorizontal size={16} />}
            >
              Filters
            </Button>
          </div>

          {/* Advanced Filter Drawer */}
          {showFilters && (
            <div
              style={{
                marginTop: "1.25rem",
                paddingTop: "1.25rem",
                borderTop: "1px solid var(--border-subtle)",
                display: "grid",
                gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
                gap: "1.25rem",
              }}
            >
              {/* Strategy */}
              <div className="form-group">
                <label className="form-label">Retrieval Strategy</label>
                <select
                  className="form-select"
                  value={strategy}
                  onChange={(e) => setStrategy(e.target.value as SearchStrategy)}
                >
                  <option value="dense">Dense Vector Search (Cosine)</option>
                  <option value="hybrid">Hybrid Search (Dense + BM25 RRF)</option>
                </select>
              </div>

              {/* Scope to Document */}
              <div className="form-group">
                <label className="form-label">Scope to Document</label>
                <select
                  className="form-select"
                  value={selectedDocId}
                  onChange={(e) => setSelectedDocId(e.target.value)}
                >
                  <option value="all">All Documents</option>
                  {documents.map((doc) => (
                    <option key={doc.id} value={doc.id}>
                      {doc.title || doc.original_filename}
                    </option>
                  ))}
                </select>
              </div>

              {/* Top K */}
              <div className="form-group">
                <label className="form-label">Top Results (k)</label>
                <select
                  className="form-select"
                  value={topK}
                  onChange={(e) => setTopK(Number(e.target.value))}
                >
                  <option value={5}>Top 5 chunks</option>
                  <option value={10}>Top 10 chunks</option>
                  <option value={20}>Top 20 chunks</option>
                  <option value={50}>Top 50 chunks</option>
                </select>
              </div>

              {/* Page Filter */}
              <div className="form-group">
                <label className="form-label">Page Number (Optional)</label>
                <input
                  type="number"
                  placeholder="e.g. 1"
                  min="1"
                  className="form-input"
                  value={pageFilter}
                  onChange={(e) => setPageFilter(e.target.value)}
                />
              </div>

              {/* Score Threshold */}
              <div className="form-group">
                <label className="form-label">
                  Score Threshold: {scoreThreshold > 0 ? scoreThreshold.toFixed(2) : "None"}
                </label>
                <input
                  type="range"
                  min="0.0"
                  max="0.9"
                  step="0.05"
                  value={scoreThreshold}
                  onChange={(e) => setScoreThreshold(parseFloat(e.target.value))}
                  style={{ width: "100%", accentColor: "var(--accent-primary)" }}
                />
              </div>
            </div>
          )}
        </form>
      </Card>

      {/* Results Header / Metric Banner */}
      {hasSearched && (
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            fontSize: "0.85rem",
            color: "var(--text-secondary)",
          }}
        >
          <div>
            Found <strong style={{ color: "var(--text-primary)" }}>{totalResults}</strong> matches for &quot;{query}&quot;
          </div>
          <div style={{ display: "flex", gap: "0.6rem", alignItems: "center" }}>
            <span
              style={{
                background: "rgba(99, 102, 241, 0.12)",
                color: "#a5b4fc",
                padding: "0.2rem 0.55rem",
                borderRadius: "4px",
                fontSize: "0.75rem",
                fontWeight: 600,
                textTransform: "uppercase",
              }}
            >
              {strategy}
            </span>
            {durationMs !== null && (
              <span style={{ color: "var(--text-muted)", fontSize: "0.8rem" }}>
                <Zap size={12} style={{ display: "inline", marginRight: "2px" }} />
                {durationMs.toFixed(1)}ms
              </span>
            )}
          </div>
        </div>
      )}

      {/* Results Feed */}
      {isSearching ? (
        <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
          {Array.from({ length: 4 }).map((_, i) => (
            <Card key={i}>
              <Skeleton height="24px" width="40%" />
              <div style={{ marginTop: "0.75rem" }}>
                <Skeleton height="16px" width="100%" />
                <div style={{ height: "0.5rem" }} />
                <Skeleton height="16px" width="80%" />
              </div>
            </Card>
          ))}
        </div>
      ) : hasSearched && results.length === 0 ? (
        <Card>
          <EmptyState
            icon={<Search />}
            title="No relevant passages found"
            description="Try expanding your query keywords, lowering the score threshold, or switching between Dense and Hybrid retrieval strategies."
          />
        </Card>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: "1.25rem" }}>
          {results.map((item, idx) => {
            const scorePercent = Math.min(100, Math.round(item.score * 100));
            const isHighScore = scorePercent >= 70;

            return (
              <Card
                key={item.chunk_id || idx}
                style={{
                  padding: "1.5rem",
                  borderLeft: `4px solid ${
                    isHighScore ? "var(--accent-primary)" : "var(--border-medium)"
                  }`,
                }}
              >
                {/* Result Top Bar */}
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
                  <div style={{ display: "flex", alignItems: "center", gap: "0.6rem", flexWrap: "wrap" }}>
                    <Link
                      href={`/documents/${item.document_id}`}
                      style={{
                        fontWeight: 700,
                        fontSize: "1rem",
                        color: "var(--accent-cyan)",
                        display: "inline-flex",
                        alignItems: "center",
                        gap: "0.35rem",
                      }}
                    >
                      <FileText size={16} />
                      {item.document_name}
                      <ExternalLink size={12} />
                    </Link>

                    <span
                      style={{
                        background: "rgba(255, 255, 255, 0.06)",
                        padding: "0.15rem 0.5rem",
                        borderRadius: "4px",
                        fontSize: "0.75rem",
                        color: "var(--text-muted)",
                      }}
                    >
                      Page {item.page_number}
                    </span>
                  </div>

                  <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
                    {/* Relevance Score Badge */}
                    <div
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: "0.35rem",
                        background: isHighScore
                          ? "rgba(16, 185, 129, 0.12)"
                          : "rgba(99, 102, 241, 0.12)",
                        color: isHighScore ? "var(--accent-emerald)" : "#a5b4fc",
                        border: `1px solid ${
                          isHighScore ? "rgba(16, 185, 129, 0.3)" : "rgba(99, 102, 241, 0.3)"
                        }`,
                        padding: "0.2rem 0.6rem",
                        borderRadius: "var(--radius-full)",
                        fontSize: "0.75rem",
                        fontWeight: 700,
                      }}
                    >
                      <span>Score: {item.score.toFixed(3)}</span>
                    </div>

                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => copyResultText(item)}
                      icon={copiedId === item.chunk_id ? <Check size={14} /> : <Copy size={14} />}
                    >
                      {copiedId === item.chunk_id ? "Copied" : "Copy"}
                    </Button>
                  </div>
                </div>

                {/* Section / Heading Hierarchy Path */}
                {item.heading_hierarchy && item.heading_hierarchy.length > 0 && (
                  <div
                    style={{
                      fontSize: "0.8rem",
                      color: "var(--accent-primary)",
                      fontWeight: 600,
                      marginBottom: "0.75rem",
                      display: "flex",
                      alignItems: "center",
                      gap: "0.3rem",
                      flexWrap: "wrap",
                    }}
                  >
                    {item.heading_hierarchy.map((heading, hIdx) => (
                      <React.Fragment key={hIdx}>
                        <span>{heading}</span>
                        {hIdx < item.heading_hierarchy.length - 1 && (
                          <ChevronRight size={12} color="var(--text-muted)" />
                        )}
                      </React.Fragment>
                    ))}
                  </div>
                )}

                {/* Text Content Snippet with Highlighting */}
                <p
                  style={{
                    fontSize: "0.925rem",
                    color: "var(--text-primary)",
                    lineHeight: "1.7",
                    whiteSpace: "pre-wrap",
                  }}
                >
                  {renderHighlightedText(item.text, query)}
                </p>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}
