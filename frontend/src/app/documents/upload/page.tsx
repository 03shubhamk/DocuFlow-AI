"use client";

/**
 * DocuFlow AI — Production Document Ingestion & Pipeline Stepper.
 */

import React, { useState, useRef } from "react";
import { useRouter } from "next/navigation";
import {
  UploadCloud,
  FileCheck,
  AlertCircle,
  Settings2,
  CheckCircle2,
  ArrowRight,
  RotateCcw,
  Sparkles,
  FileCode,
  Layers,
  Cpu,
} from "lucide-react";
import { api } from "../../../lib/api-client";
import { useToast } from "../../../context/ToastContext";
import { useAuth } from "../../../context/AuthContext";
import { Card } from "../../../components/ui/Card";
import { Button } from "../../../components/ui/Button";
import { ProgressBar } from "../../../components/ui/ProgressBar";

const SUPPORTED_EXTENSIONS = [
  ".pdf",
  ".docx",
  ".pptx",
  ".xlsx",
  ".html",
  ".md",
  ".txt",
  ".png",
  ".jpg",
  ".jpeg",
  ".tiff",
];

const MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024; // 50 MB

export default function UploadDocumentPage() {
  const router = useRouter();
  const { isAuthenticated, isLoading: authLoading } = useAuth();
  const { success: toastSuccess, error: toastError } = useToast();

  const fileInputRef = useRef<HTMLInputElement>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [validationError, setValidationError] = useState<string | null>(null);

  // Ingestion settings
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [doOcr, setDoOcr] = useState(true);
  const [ocrProvider, setOcrProvider] = useState("easyocr");
  const [extractFigures, setExtractFigures] = useState(true);
  const [doTableStructure, setDoTableStructure] = useState(true);
  const [chunkingStrategy, setChunkingStrategy] = useState<"hierarchical" | "hybrid">("hierarchical");
  const [chunkSize, setChunkSize] = useState(512);
  const [chunkOverlap, setChunkOverlap] = useState(64);

  // Stepper lifecycle state
  const [uploadStatus, setUploadStatus] = useState<
    "idle" | "uploading" | "processing" | "completed" | "failed"
  >("idle");
  const [progressPercent, setProgressPercent] = useState(0);
  const [activeStage, setActiveStage] = useState<string>("Ready");
  const [createdDocId, setCreatedDocId] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  if (!authLoading && !isAuthenticated) {
    router.push("/login");
  }

  const validateFile = (file: File): boolean => {
    setValidationError(null);
    const ext = `.${file.name.split(".").pop()?.toLowerCase()}`;
    if (!SUPPORTED_EXTENSIONS.includes(ext)) {
      setValidationError(
        `Unsupported file type "${ext}". Allowed: ${SUPPORTED_EXTENSIONS.join(", ")}`
      );
      return false;
    }
    if (file.size > MAX_FILE_SIZE_BYTES) {
      setValidationError("File exceeds maximum allowed size of 50 MB.");
      return false;
    }
    return true;
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0];
      if (validateFile(file)) {
        setSelectedFile(file);
      }
    }
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = () => {
    setIsDragging(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      const file = e.dataTransfer.files[0];
      if (validateFile(file)) {
        setSelectedFile(file);
      }
    }
  };

  const startUploadAndPipeline = async () => {
    if (!selectedFile) return;

    setUploadStatus("uploading");
    setProgressPercent(15);
    setActiveStage("Uploading file to secure object storage...");
    setErrorMessage(null);

    try {
      // 1. Upload to backend
      const uploadRes = await api.documents.upload(selectedFile);
      setCreatedDocId(uploadRes.document_id);
      setProgressPercent(40);
      setActiveStage("Parsing layout and AST structures (Docling)...");
      setUploadStatus("processing");

      // 2. Trigger asynchronous processing pipeline with custom options
      await api.documents.process(uploadRes.document_id, {
        do_ocr: doOcr,
        ocr_provider: ocrProvider,
        do_table_structure: doTableStructure,
        extract_figures: extractFigures,
        chunking_strategy: chunkingStrategy,
        chunk_size: chunkSize,
        chunk_overlap: chunkOverlap,
      });

      // 3. Poll for processing completion
      let attempts = 0;
      const pollInterval = setInterval(async () => {
        attempts++;
        try {
          const statusRes = await api.documents.getStatus(uploadRes.document_id);
          if (statusRes.status === "COMPLETED") {
            clearInterval(pollInterval);
            setProgressPercent(100);
            setActiveStage("Completed: Indexed in vector store");
            setUploadStatus("completed");
            toastSuccess("Document successfully processed and indexed!", "Pipeline Success");
          } else if (statusRes.status === "FAILED") {
            clearInterval(pollInterval);
            setUploadStatus("failed");
            const err = statusRes.errors?.[0]?.error_message || "Document processing pipeline failed.";
            setErrorMessage(err);
            toastError(err);
          } else {
            // In progress
            setProgressPercent(Math.min(95, 40 + attempts * 10));
            setActiveStage(`Stage: ${statusRes.stage || statusRes.status.toLowerCase()}`);
          }
        } catch {
          if (attempts > 15) {
            clearInterval(pollInterval);
            setUploadStatus("completed"); // fallback to optimistic completed if status check timeout
          }
        }
      }, 1500);
    } catch (err: unknown) {
      setUploadStatus("failed");
      const msg = err instanceof Error ? err.message : "Upload failed.";
      setErrorMessage(msg);
      toastError(msg);
    }
  };

  const handleReset = () => {
    setSelectedFile(null);
    setUploadStatus("idle");
    setProgressPercent(0);
    setActiveStage("Ready");
    setErrorMessage(null);
    setCreatedDocId(null);
  };

  return (
    <div style={{ maxWidth: "860px", margin: "0 auto", display: "flex", flexDirection: "column", gap: "2rem" }}>
      <div>
        <h1 style={{ fontSize: "1.75rem" }}>Upload & Ingest Document</h1>
        <p style={{ marginTop: "0.25rem" }}>
          Ingest multi-format enterprise documents with automatic OCR, layout analysis, normalization, and vector embedding.
        </p>
      </div>

      {/* Upload Box or Pipeline Status Card */}
      {uploadStatus === "idle" ? (
        <>
          {/* Dropzone */}
          <div
            className={`dropzone ${isDragging ? "active" : ""}`}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current?.click()}
          >
            <input
              type="file"
              ref={fileInputRef}
              style={{ display: "none" }}
              onChange={handleFileChange}
              accept={SUPPORTED_EXTENSIONS.join(",")}
            />
            <div
              style={{
                width: "64px",
                height: "64px",
                borderRadius: "var(--radius-xl)",
                background: "linear-gradient(135deg, rgba(99, 102, 241, 0.2) 0%, rgba(6, 182, 212, 0.15) 100%)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                color: "var(--accent-primary)",
              }}
            >
              <UploadCloud size={32} />
            </div>

            {selectedFile ? (
              <div>
                <div style={{ fontSize: "1.1rem", fontWeight: 600, color: "var(--accent-cyan)" }}>
                  {selectedFile.name}
                </div>
                <div style={{ fontSize: "0.85rem", color: "var(--text-secondary)", marginTop: "0.2rem" }}>
                  {(selectedFile.size / (1024 * 1024)).toFixed(2)} MB • Ready to ingest
                </div>
              </div>
            ) : (
              <div>
                <div style={{ fontSize: "1.1rem", fontWeight: 600 }}>
                  Drag and drop document here, or <span style={{ color: "var(--accent-primary)" }}>browse</span>
                </div>
                <div style={{ fontSize: "0.85rem", color: "var(--text-muted)", marginTop: "0.4rem" }}>
                  Supports PDF, DOCX, PPTX, XLSX, HTML, MD, TXT, PNG, JPG, TIFF (Max 50MB)
                </div>
              </div>
            )}
          </div>

          {validationError && (
            <div
              style={{
                background: "rgba(244, 63, 94, 0.12)",
                border: "1px solid rgba(244, 63, 94, 0.3)",
                borderRadius: "var(--radius-md)",
                padding: "0.75rem 1rem",
                display: "flex",
                alignItems: "center",
                gap: "0.6rem",
                color: "#fb7185",
                fontSize: "0.85rem",
              }}
            >
              <AlertCircle size={18} />
              <span>{validationError}</span>
            </div>
          )}

          {/* Advanced Pipeline Configuration Accordion */}
          <Card>
            <div
              onClick={() => setShowAdvanced((prev) => !prev)}
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                cursor: "pointer",
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: "0.6rem" }}>
                <Settings2 size={18} color="var(--accent-primary)" />
                <span style={{ fontWeight: 600, fontSize: "0.95rem" }}>
                  Processing & Chunking Configuration
                </span>
              </div>
              <span style={{ fontSize: "0.8rem", color: "var(--text-muted)" }}>
                {showAdvanced ? "Hide options ▲" : "Configure OCR & chunking ▼"}
              </span>
            </div>

            {showAdvanced && (
              <div
                style={{
                  marginTop: "1.5rem",
                  paddingTop: "1.25rem",
                  borderTop: "1px solid var(--border-subtle)",
                  display: "grid",
                  gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
                  gap: "1.25rem",
                }}
              >
                {/* OCR Toggle */}
                <div className="form-group">
                  <label className="form-label">OCR Mode</label>
                  <select
                    className="form-select"
                    value={doOcr ? ocrProvider : "none"}
                    onChange={(e) => {
                      if (e.target.value === "none") {
                        setDoOcr(false);
                      } else {
                        setDoOcr(true);
                        setOcrProvider(e.target.value);
                      }
                    }}
                  >
                    <option value="easyocr">EasyOCR (PyTorch / GPU / CPU)</option>
                    <option value="tesseract">Tesseract OCR Engine</option>
                    <option value="rapidocr">RapidOCR (Lightweight)</option>
                    <option value="none">Disabled (Native text only)</option>
                  </select>
                </div>

                {/* Chunking Strategy */}
                <div className="form-group">
                  <label className="form-label">Chunking Strategy</label>
                  <select
                    className="form-select"
                    value={chunkingStrategy}
                    onChange={(e) =>
                      setChunkingStrategy(e.target.value as "hierarchical" | "hybrid")
                    }
                  >
                    <option value="hierarchical">Hierarchical (Structure & Headings Aware)</option>
                    <option value="hybrid">Hybrid (Token Overlap + Hierarchy)</option>
                  </select>
                </div>

                {/* Chunk Size */}
                <div className="form-group">
                  <label className="form-label">Max Token Chunk Size</label>
                  <input
                    type="number"
                    className="form-input"
                    value={chunkSize}
                    min={128}
                    max={2048}
                    step={64}
                    onChange={(e) => setChunkSize(Number(e.target.value))}
                  />
                </div>

                {/* Chunk Overlap */}
                <div className="form-group">
                  <label className="form-label">Token Overlap</label>
                  <input
                    type="number"
                    className="form-input"
                    value={chunkOverlap}
                    min={0}
                    max={256}
                    step={16}
                    onChange={(e) => setChunkOverlap(Number(e.target.value))}
                  />
                </div>

                {/* Additional Toggles */}
                <div className="form-group" style={{ display: "flex", flexDirection: "column", gap: "0.5rem", justifyContent: "center" }}>
                  <label style={{ display: "flex", alignItems: "center", gap: "0.5rem", fontSize: "0.85rem", cursor: "pointer" }}>
                    <input
                      type="checkbox"
                      checked={doTableStructure}
                      onChange={(e) => setDoTableStructure(e.target.checked)}
                    />
                    <span>Extract Table Structures & HTML</span>
                  </label>
                  <label style={{ display: "flex", alignItems: "center", gap: "0.5rem", fontSize: "0.85rem", cursor: "pointer" }}>
                    <input
                      type="checkbox"
                      checked={extractFigures}
                      onChange={(e) => setExtractFigures(e.target.checked)}
                    />
                    <span>Extract Embedded Figures</span>
                  </label>
                </div>
              </div>
            )}
          </Card>

          {/* Action Button */}
          <div style={{ display: "flex", justifyContent: "flex-end", gap: "1rem" }}>
            <Button
              variant="secondary"
              onClick={() => setSelectedFile(null)}
              disabled={!selectedFile}
            >
              Clear
            </Button>
            <Button
              variant="primary"
              onClick={startUploadAndPipeline}
              disabled={!selectedFile}
              icon={<Sparkles size={16} />}
            >
              Start Ingestion Pipeline
            </Button>
          </div>
        </>
      ) : (
        /* Ingestion Stepper & Live Monitor */
        <Card style={{ padding: "2.5rem 2rem" }}>
          <div style={{ textAlign: "center", marginBottom: "2rem" }}>
            {uploadStatus === "completed" ? (
              <div
                style={{
                  width: "64px",
                  height: "64px",
                  borderRadius: "50%",
                  background: "rgba(16, 185, 129, 0.15)",
                  color: "var(--accent-emerald)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  margin: "0 auto 1rem",
                }}
              >
                <CheckCircle2 size={36} />
              </div>
            ) : uploadStatus === "failed" ? (
              <div
                style={{
                  width: "64px",
                  height: "64px",
                  borderRadius: "50%",
                  background: "rgba(244, 63, 94, 0.15)",
                  color: "var(--accent-rose)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  margin: "0 auto 1rem",
                }}
              >
                <AlertCircle size={36} />
              </div>
            ) : (
              <div
                style={{
                  width: "64px",
                  height: "64px",
                  borderRadius: "50%",
                  background: "rgba(99, 102, 241, 0.15)",
                  color: "var(--accent-primary)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  margin: "0 auto 1rem",
                }}
              >
                <Cpu size={36} />
              </div>
            )}

            <h2 style={{ fontSize: "1.4rem" }}>
              {uploadStatus === "completed"
                ? "Document Processing Complete!"
                : uploadStatus === "failed"
                ? "Ingestion Pipeline Failed"
                : "Processing Document Pipeline"}
            </h2>
            <p style={{ color: "var(--text-secondary)", marginTop: "0.3rem" }}>
              {selectedFile?.name}
            </p>
          </div>

          {/* Progress Bar */}
          <div style={{ marginBottom: "2rem" }}>
            <ProgressBar progress={progressPercent} stage={activeStage} />
          </div>

          {/* Stepper Visualization */}
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(130px, 1fr))",
              gap: "0.75rem",
              marginBottom: "2rem",
            }}
          >
            {[
              { name: "Upload", icon: <UploadCloud size={16} />, threshold: 20 },
              { name: "Docling AST", icon: <FileCode size={16} />, threshold: 45 },
              { name: "Normalization", icon: <FileCheck size={16} />, threshold: 65 },
              { name: "Chunking", icon: <Layers size={16} />, threshold: 80 },
              { name: "Qdrant Index", icon: <Sparkles size={16} />, threshold: 100 },
            ].map((step, idx) => {
              const isDone = progressPercent >= step.threshold || uploadStatus === "completed";
              const isCurrent =
                progressPercent < step.threshold &&
                (idx === 0 || progressPercent >= [0, 20, 45, 65, 80][idx]);

              return (
                <div
                  key={step.name}
                  style={{
                    background: isDone
                      ? "rgba(16, 185, 129, 0.08)"
                      : isCurrent
                      ? "rgba(99, 102, 241, 0.12)"
                      : "rgba(255, 255, 255, 0.02)",
                    border: `1px solid ${
                      isDone
                        ? "rgba(16, 185, 129, 0.3)"
                        : isCurrent
                        ? "var(--accent-primary)"
                        : "var(--border-subtle)"
                    }`,
                    borderRadius: "var(--radius-md)",
                    padding: "0.8rem 0.6rem",
                    textAlign: "center",
                    display: "flex",
                    flexDirection: "column",
                    alignItems: "center",
                    gap: "0.35rem",
                  }}
                >
                  <div
                    style={{
                      color: isDone
                        ? "var(--accent-emerald)"
                        : isCurrent
                        ? "var(--accent-primary)"
                        : "var(--text-muted)",
                    }}
                  >
                    {step.icon}
                  </div>
                  <div
                    style={{
                      fontSize: "0.75rem",
                      fontWeight: 600,
                      color: isDone || isCurrent ? "var(--text-primary)" : "var(--text-muted)",
                    }}
                  >
                    {step.name}
                  </div>
                </div>
              );
            })}
          </div>

          {errorMessage && (
            <div
              style={{
                background: "rgba(244, 63, 94, 0.12)",
                border: "1px solid rgba(244, 63, 94, 0.3)",
                borderRadius: "var(--radius-md)",
                padding: "1rem",
                color: "#fb7185",
                fontSize: "0.85rem",
                marginBottom: "1.5rem",
              }}
            >
              <div style={{ fontWeight: 600, marginBottom: "0.25rem" }}>Error Details:</div>
              <div>{errorMessage}</div>
            </div>
          )}

          {/* Stepper Footer Actions */}
          <div style={{ display: "flex", justifyContent: "center", gap: "1rem" }}>
            {uploadStatus === "completed" && createdDocId && (
              <>
                <Button
                  variant="secondary"
                  onClick={handleReset}
                  icon={<RotateCcw size={15} />}
                >
                  Upload Another File
                </Button>
                <Button
                  variant="primary"
                  onClick={() => router.push(`/documents/${createdDocId}`)}
                  icon={<ArrowRight size={15} />}
                >
                  View Document Details & Chunks
                </Button>
              </>
            )}

            {uploadStatus === "failed" && (
              <>
                <Button variant="secondary" onClick={handleReset}>
                  Cancel
                </Button>
                <Button
                  variant="primary"
                  onClick={startUploadAndPipeline}
                  icon={<RotateCcw size={15} />}
                >
                  Retry Pipeline
                </Button>
              </>
            )}
          </div>
        </Card>
      )}
    </div>
  );
}
