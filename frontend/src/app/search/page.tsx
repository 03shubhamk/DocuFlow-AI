"use client";

/**
 * DocuFlow AI — Universal Semantic Search & Grounded AI Document Q&A Intelligence.
 */

import React, { useState, useEffect, useCallback, useRef } from "react";
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
  MessageSquare,
  Send,
  Trash2,
  Bot,
  User,
  BookOpen,
  ArrowDownCircle,
  HelpCircle,
} from "lucide-react";
import { api } from "../../lib/api-client";
import { useToast } from "../../context/ToastContext";
import { useAuth } from "../../context/AuthContext";
import {
  DocumentSummary,
  SearchResultItem,
  SearchStrategy,
  QACitation,
  ChatMessage,
} from "../../types/api";
import { Card } from "../../components/ui/Card";
import { Button } from "../../components/ui/Button";
import { EmptyState } from "../../components/ui/EmptyState";
import { Skeleton } from "../../components/ui/Skeleton";

export default function SearchPage() {
  const router = useRouter();
  const { isAuthenticated, isLoading: authLoading } = useAuth();
  const { success: toastSuccess, error: toastError } = useToast();

  // Tab mode: "search" vs "chat"
  const [activeTab, setActiveTab] = useState<"search" | "chat">("search");

  // Search Mode State
  const [query, setQuery] = useState("");
  const [strategy, setStrategy] = useState<SearchStrategy>("dense");
  const [topK, setTopK] = useState(10);
  const [scoreThreshold, setScoreThreshold] = useState<number>(0.0);
  const [selectedDocId, setSelectedDocId] = useState<string>("all");
  const [pageFilter, setPageFilter] = useState<string>("");

  const [documents, setDocuments] = useState<DocumentSummary[]>([]);
  const [results, setResults] = useState<SearchResultItem[]>([]);
  const [aiAnswer, setAiAnswer] = useState<string | null>(null);
  const [citations, setCitations] = useState<QACitation[]>([]);
  const [totalResults, setTotalResults] = useState(0);
  const [durationMs, setDurationMs] = useState<number | null>(null);
  const [isSearching, setIsSearching] = useState(false);
  const [hasSearched, setHasSearched] = useState(false);
  const [showFilters, setShowFilters] = useState(false);
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [copiedAiAnswer, setCopiedAiAnswer] = useState(false);

  // Chat Mode State
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const [chatInput, setChatInput] = useState("");
  const [isChatSending, setIsChatSending] = useState(false);
  const chatEndRef = useRef<HTMLDivElement>(null);

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

  useEffect(() => {
    if (activeTab === "chat") {
      chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  }, [chatMessages, activeTab]);

  const handleSearch = useCallback(
    async (e?: React.FormEvent) => {
      if (e) e.preventDefault();
      if (!query.trim()) return;

      setIsSearching(true);
      setHasSearched(true);
      setAiAnswer(null);
      setCitations([]);

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
        setAiAnswer(res.ai_answer || null);
        setCitations(res.citations || []);
        setTotalResults(res.total_results || 0);
        setDurationMs(res.duration_ms || 0);
      } catch {
        toastError("Search query failed. Check backend connection.");
      } finally {
        setIsSearching(false);
      }
    },
    [query, strategy, topK, scoreThreshold, selectedDocId, pageFilter, toastError]
  );

  const copyResultText = (item: SearchResultItem) => {
    navigator.clipboard.writeText(item.text);
    setCopiedId(item.chunk_id);
    toastSuccess("Snippet copied to clipboard.");
    setTimeout(() => setCopiedId(null), 2000);
  };

  const copyAiAnswerText = () => {
    if (!aiAnswer) return;
    navigator.clipboard.writeText(aiAnswer);
    setCopiedAiAnswer(true);
    toastSuccess("AI synthesized answer copied to clipboard.");
    setTimeout(() => setCopiedAiAnswer(false), 2000);
  };

  const scrollToChunk = (chunkId?: string | null) => {
    if (!chunkId) return;
    const el = document.getElementById(`chunk-${chunkId}`);
    if (el) {
      el.scrollIntoView({ behavior: "smooth", block: "center" });
      el.style.boxShadow = "0 0 0 2px var(--accent-primary), 0 0 20px rgba(99, 102, 241, 0.4)";
      setTimeout(() => {
        el.style.boxShadow = "none";
      }, 2500);
    }
  };

  // Chat Submission Handler
  const handleSendChat = async (messageText?: string) => {
    const textToSend = messageText || chatInput;
    if (!textToSend.trim() || isChatSending) return;

    const userMessage: ChatMessage = {
      role: "user",
      content: textToSend.trim(),
    };

    const newHistory = [...chatMessages, userMessage];
    setChatMessages(newHistory);
    setChatInput("");
    setIsChatSending(true);

    try {
      const res = await api.search.chat({
        messages: newHistory,
        document_ids: selectedDocId !== "all" ? [selectedDocId] : undefined,
        top_k: 8,
      });

      const assistantMessage: ChatMessage = {
        role: "assistant",
        content: res.message,
        citations: res.citations,
      };

      setChatMessages([...newHistory, assistantMessage]);
    } catch {
      toastError("Failed to generate response. Please try again.");
    } finally {
      setIsChatSending(false);
    }
  };

  /** Format text paragraphs & bullet points */
  const renderFormattedAnswer = (text: string) => {
    const lines = text.split("\n");
    return lines.map((line, idx) => {
      const trimmed = line.trim();
      if (!trimmed) return <div key={idx} style={{ height: "0.5rem" }} />;
      if (trimmed.startsWith("•") || trimmed.startsWith("-") || trimmed.startsWith("*")) {
        return (
          <div
            key={idx}
            style={{
              display: "flex",
              gap: "0.5rem",
              alignItems: "flex-start",
              marginLeft: "0.5rem",
              marginBottom: "0.35rem",
              color: "var(--text-primary)",
            }}
          >
            <span style={{ color: "var(--accent-primary)", fontWeight: 700 }}>•</span>
            <span>{trimmed.replace(/^[-•*]\s*/, "")}</span>
          </div>
        );
      }
      return (
        <p key={idx} style={{ marginBottom: "0.5rem", lineHeight: "1.65", color: "var(--text-primary)" }}>
          {trimmed}
        </p>
      );
    });
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

  const sampleQuestions = [
    "What are the main security requirements and data retention policies?",
    "Summarize the key architectural pillars and deployment model.",
    "What are the primary business objectives and financial ROI metrics?",
    "What is Infrastructure as a Service and how is it used?",
  ];

  return (
    <div style={{ maxWidth: "1100px", margin: "0 auto", display: "flex", flexDirection: "column", gap: "1.75rem" }}>
      {/* Page Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end", flexWrap: "wrap", gap: "1rem" }}>
        <div>
          <h1 style={{ fontSize: "1.75rem" }}>
            <span className="text-gradient">AI Search & Intelligence</span>
          </h1>
          <p style={{ marginTop: "0.25rem", color: "var(--text-secondary)" }}>
            Extract direct answers and semantic passages across all ingested documents with verified citations.
          </p>
        </div>

        {/* Tab Switcher */}
        <div
          style={{
            display: "inline-flex",
            padding: "0.3rem",
            background: "var(--bg-card)",
            border: "1px solid var(--border-medium)",
            borderRadius: "var(--radius-lg)",
            gap: "0.25rem",
          }}
        >
          <button
            onClick={() => setActiveTab("search")}
            style={{
              display: "flex",
              alignItems: "center",
              gap: "0.5rem",
              padding: "0.45rem 1rem",
              borderRadius: "var(--radius-md)",
              fontSize: "0.875rem",
              fontWeight: 600,
              cursor: "pointer",
              border: "none",
              background: activeTab === "search" ? "var(--accent-primary)" : "transparent",
              color: activeTab === "search" ? "#ffffff" : "var(--text-secondary)",
              transition: "all 0.2s ease",
            }}
          >
            <Search size={15} />
            Search & Answers
          </button>
          <button
            onClick={() => setActiveTab("chat")}
            style={{
              display: "flex",
              alignItems: "center",
              gap: "0.5rem",
              padding: "0.45rem 1rem",
              borderRadius: "var(--radius-md)",
              fontSize: "0.875rem",
              fontWeight: 600,
              cursor: "pointer",
              border: "none",
              background: activeTab === "chat" ? "var(--accent-primary)" : "transparent",
              color: activeTab === "chat" ? "#ffffff" : "var(--text-secondary)",
              transition: "all 0.2s ease",
            }}
          >
            <MessageSquare size={15} />
            Conversational Chat
          </button>
        </div>
      </div>

      {activeTab === "search" ? (
        <>
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
                    placeholder="Ask a question or enter keywords (e.g. 'What is the deployment strategy?', 'operating margins')..."
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
                      <option value="all">All Documents ({documents.length})</option>
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

          {/* AI Synthesized Answer Card */}
          {aiAnswer && (
            <div
              style={{
                position: "relative",
                background: "linear-gradient(135deg, rgba(30, 27, 75, 0.85) 0%, rgba(15, 23, 42, 0.9) 100%)",
                border: "1px solid rgba(129, 140, 248, 0.4)",
                borderRadius: "var(--radius-xl)",
                padding: "1.75rem",
                boxShadow: "0 10px 35px -5px rgba(99, 102, 241, 0.25), inset 0 1px 0 rgba(255, 255, 255, 0.1)",
                backdropFilter: "blur(16px)",
              }}
            >
              {/* Header */}
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  marginBottom: "1rem",
                  flexWrap: "wrap",
                  gap: "0.5rem",
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: "0.6rem" }}>
                  <div
                    style={{
                      width: "32px",
                      height: "32px",
                      borderRadius: "8px",
                      background: "linear-gradient(135deg, var(--accent-primary), var(--accent-cyan))",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      color: "#fff",
                      boxShadow: "0 0 12px rgba(99, 102, 241, 0.6)",
                    }}
                  >
                    <Sparkles size={18} />
                  </div>
                  <div>
                    <h3 style={{ fontSize: "1.1rem", fontWeight: 700, color: "#ffffff", margin: 0 }}>
                      AI Synthesized Answer
                    </h3>
                    <span style={{ fontSize: "0.75rem", color: "#a5b4fc" }}>
                      Grounded in {citations.length} document source{citations.length === 1 ? "" : "s"}
                    </span>
                  </div>
                </div>

                <Button
                  variant="ghost"
                  size="sm"
                  onClick={copyAiAnswerText}
                  icon={copiedAiAnswer ? <Check size={14} /> : <Copy size={14} />}
                >
                  {copiedAiAnswer ? "Copied" : "Copy Answer"}
                </Button>
              </div>

              {/* Answer Content */}
              <div style={{ fontSize: "0.95rem", color: "#f1f5f9", marginBottom: "1.25rem" }}>
                {renderFormattedAnswer(aiAnswer)}
              </div>

              {/* Citations Footer */}
              {citations.length > 0 && (
                <div
                  style={{
                    paddingTop: "1rem",
                    borderTop: "1px solid rgba(255, 255, 255, 0.08)",
                    display: "flex",
                    flexDirection: "column",
                    gap: "0.5rem",
                  }}
                >
                  <span style={{ fontSize: "0.75rem", fontWeight: 700, color: "var(--text-muted)", textTransform: "uppercase" }}>
                    Sources & Citations
                  </span>
                  <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
                    {citations.map((cite) => (
                      <button
                        key={cite.citation_id}
                        onClick={() => scrollToChunk(cite.chunk_id)}
                        title={`View passage in ${cite.document_name} (p. ${cite.page_number})`}
                        style={{
                          display: "inline-flex",
                          alignItems: "center",
                          gap: "0.35rem",
                          background: "rgba(99, 102, 241, 0.18)",
                          border: "1px solid rgba(129, 140, 248, 0.35)",
                          color: "#c7d2fe",
                          padding: "0.25rem 0.65rem",
                          borderRadius: "var(--radius-md)",
                          fontSize: "0.8rem",
                          cursor: "pointer",
                          transition: "all 0.15s ease",
                        }}
                      >
                        <strong style={{ color: "#a5b4fc" }}>[{cite.citation_id}]</strong>
                        <span>{cite.document_name}</span>
                        <span style={{ opacity: 0.7 }}>p.{cite.page_number}</span>
                        <ArrowDownCircle size={12} style={{ marginLeft: "2px" }} />
                      </button>
                    ))}
                  </div>
                </div>
              )}
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
                const matchingCitation = citations.find((c) => c.chunk_id === item.chunk_id);

                return (
                  <Card
                    key={item.chunk_id || idx}
                    id={`chunk-${item.chunk_id}`}
                    style={{
                      padding: "1.5rem",
                      borderLeft: `4px solid ${
                        isHighScore ? "var(--accent-primary)" : "var(--border-medium)"
                      }`,
                      transition: "box-shadow 0.3s ease",
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
                        {matchingCitation && (
                          <span
                            style={{
                              background: "var(--accent-primary)",
                              color: "#fff",
                              padding: "0.15rem 0.5rem",
                              borderRadius: "4px",
                              fontSize: "0.75rem",
                              fontWeight: 700,
                            }}
                          >
                            Source [{matchingCitation.citation_id}]
                          </span>
                        )}

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
        </>
      ) : (
        /* Conversational Document Chat Interface */
        <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
          {/* Chat Scope Selector */}
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              background: "var(--bg-card)",
              border: "1px solid var(--border-medium)",
              padding: "0.75rem 1.25rem",
              borderRadius: "var(--radius-lg)",
              flexWrap: "wrap",
              gap: "0.75rem",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
              <BookOpen size={16} color="var(--accent-primary)" />
              <span style={{ fontSize: "0.875rem", color: "var(--text-secondary)" }}>Scope:</span>
              <select
                className="form-select"
                style={{ width: "auto", minWidth: "220px", height: "36px", fontSize: "0.85rem" }}
                value={selectedDocId}
                onChange={(e) => setSelectedDocId(e.target.value)}
              >
                <option value="all">Entire Document Library ({documents.length})</option>
                {documents.map((doc) => (
                  <option key={doc.id} value={doc.id}>
                    {doc.title || doc.original_filename}
                  </option>
                ))}
              </select>
            </div>

            {chatMessages.length > 0 && (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setChatMessages([])}
                icon={<Trash2 size={14} />}
              >
                Clear History
              </Button>
            )}
          </div>

          {/* Chat Messages Box */}
          <Card
            style={{
              minHeight: "450px",
              maxHeight: "600px",
              overflowY: "auto",
              padding: "1.5rem",
              display: "flex",
              flexDirection: "column",
              gap: "1.25rem",
            }}
          >
            {chatMessages.length === 0 ? (
              <div
                style={{
                  display: "flex",
                  flexDirection: "column",
                  alignItems: "center",
                  justifyContent: "center",
                  height: "350px",
                  textAlign: "center",
                  gap: "1rem",
                }}
              >
                <div
                  style={{
                    width: "48px",
                    height: "48px",
                    borderRadius: "50%",
                    background: "rgba(99, 102, 241, 0.15)",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    color: "var(--accent-primary)",
                  }}
                >
                  <Bot size={24} />
                </div>
                <div>
                  <h3 style={{ fontSize: "1.2rem", fontWeight: 700 }}>Ask Anything About Your Documents</h3>
                  <p style={{ color: "var(--text-secondary)", fontSize: "0.9rem", maxWidth: "480px", margin: "0.35rem auto 0" }}>
                    Get grounded, multi-turn answers synthesized with precise page-level citations from your indexed documents.
                  </p>
                </div>

                {/* Suggested Questions */}
                <div style={{ marginTop: "1rem", display: "flex", flexDirection: "column", gap: "0.5rem", width: "100%", maxWidth: "560px" }}>
                  <span style={{ fontSize: "0.8rem", color: "var(--text-muted)", fontWeight: 600 }}>Suggested Questions:</span>
                  {sampleQuestions.map((sq, i) => (
                    <button
                      key={i}
                      onClick={() => handleSendChat(sq)}
                      style={{
                        background: "rgba(255, 255, 255, 0.03)",
                        border: "1px solid var(--border-medium)",
                        borderRadius: "var(--radius-md)",
                        padding: "0.6rem 1rem",
                        color: "var(--text-primary)",
                        fontSize: "0.85rem",
                        textAlign: "left",
                        cursor: "pointer",
                        display: "flex",
                        alignItems: "center",
                        gap: "0.5rem",
                        transition: "all 0.15s ease",
                      }}
                      onMouseEnter={(e) => {
                        e.currentTarget.style.borderColor = "var(--accent-primary)";
                        e.currentTarget.style.background = "rgba(99, 102, 241, 0.08)";
                      }}
                      onMouseLeave={(e) => {
                        e.currentTarget.style.borderColor = "var(--border-medium)";
                        e.currentTarget.style.background = "rgba(255, 255, 255, 0.03)";
                      }}
                    >
                      <HelpCircle size={14} color="var(--accent-primary)" />
                      <span>{sq}</span>
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              chatMessages.map((msg, idx) => (
                <div
                  key={idx}
                  style={{
                    display: "flex",
                    flexDirection: "column",
                    alignItems: msg.role === "user" ? "flex-end" : "flex-start",
                    gap: "0.35rem",
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", gap: "0.4rem", fontSize: "0.75rem", color: "var(--text-muted)" }}>
                    {msg.role === "user" ? (
                      <>
                        <span>You</span>
                        <User size={13} />
                      </>
                    ) : (
                      <>
                        <Bot size={13} color="var(--accent-primary)" />
                        <span style={{ color: "var(--accent-primary)", fontWeight: 600 }}>DocuFlow Assistant</span>
                      </>
                    )}
                  </div>

                  <div
                    style={{
                      maxWidth: "85%",
                      padding: "1rem 1.25rem",
                      borderRadius: "var(--radius-lg)",
                      background:
                        msg.role === "user"
                          ? "var(--accent-primary)"
                          : "linear-gradient(135deg, rgba(30, 27, 75, 0.5) 0%, rgba(15, 23, 42, 0.8) 100%)",
                      color: msg.role === "user" ? "#ffffff" : "var(--text-primary)",
                      border: msg.role === "assistant" ? "1px solid rgba(129, 140, 248, 0.3)" : "none",
                      boxShadow: msg.role === "assistant" ? "0 4px 20px rgba(0,0,0,0.2)" : "none",
                    }}
                  >
                    {renderFormattedAnswer(msg.content)}

                    {/* Grounded Citations in Chat */}
                    {msg.citations && msg.citations.length > 0 && (
                      <div
                        style={{
                          marginTop: "0.75rem",
                          paddingTop: "0.75rem",
                          borderTop: "1px solid rgba(255, 255, 255, 0.1)",
                          display: "flex",
                          flexDirection: "column",
                          gap: "0.35rem",
                        }}
                      >
                        <span style={{ fontSize: "0.7rem", color: "var(--text-muted)", fontWeight: 700 }}>
                          Sources:
                        </span>
                        <div style={{ display: "flex", gap: "0.4rem", flexWrap: "wrap" }}>
                          {msg.citations.map((c) => (
                            <Link
                              key={c.citation_id}
                              href={`/documents/${c.document_id}`}
                              style={{
                                display: "inline-flex",
                                alignItems: "center",
                                gap: "0.3rem",
                                background: "rgba(99, 102, 241, 0.2)",
                                border: "1px solid rgba(129, 140, 248, 0.3)",
                                color: "#c7d2fe",
                                padding: "0.2rem 0.5rem",
                                borderRadius: "4px",
                                fontSize: "0.75rem",
                                textDecoration: "none",
                              }}
                            >
                              <strong>[{c.citation_id}]</strong>
                              <span>{c.document_name}</span>
                              <span style={{ opacity: 0.7 }}>p.{c.page_number}</span>
                            </Link>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              ))
            )}

            {isChatSending && (
              <div style={{ display: "flex", alignItems: "center", gap: "0.6rem", color: "var(--text-secondary)", fontSize: "0.9rem" }}>
                <Bot size={16} color="var(--accent-primary)" />
                <span className="text-gradient" style={{ fontWeight: 600 }}>Synthesizing answer from documents...</span>
              </div>
            )}
            <div ref={chatEndRef} />
          </Card>

          {/* Chat Input Bar */}
          <div style={{ display: "flex", gap: "0.75rem", alignItems: "center" }}>
            <input
              type="text"
              placeholder="Ask a follow-up question..."
              className="form-input"
              style={{ height: "48px", fontSize: "1rem", flex: 1 }}
              value={chatInput}
              onChange={(e) => setChatInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  handleSendChat();
                }
              }}
            />
            <Button
              variant="primary"
              size="lg"
              onClick={() => handleSendChat()}
              isLoading={isChatSending}
              disabled={!chatInput.trim()}
              icon={<Send size={16} />}
            >
              Send
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
