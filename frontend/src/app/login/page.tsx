"use client";

/**
 * DocuFlow AI — User Login Page.
 */

import React, { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Sparkles, Lock, Mail, ArrowRight, AlertCircle } from "lucide-react";
import { useAuth } from "../../context/AuthContext";
import { useToast } from "../../context/ToastContext";
import { Button } from "../../components/ui/Button";

export default function LoginPage() {
  const router = useRouter();
  const { login } = useAuth();
  const { success } = useToast();

  const [email, setEmail] = useState("admin@docuflow.ai");
  const [password, setPassword] = useState("DocuFlow2026!Secure");
  const [isLoading, setIsLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setErrorMsg(null);

    try {
      await login({ email, password });
      success("Welcome back to DocuFlow AI!", "Authenticated");
      router.push("/dashboard");
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Invalid email or password.";
      setErrorMsg(msg);
    } finally {
      setIsLoading(false);
    }
  };

  const fillDemoAdmin = () => {
    setEmail("admin@docuflow.ai");
    setPassword("DocuFlow2026!Secure");
  };

  const fillDemoEditor = () => {
    setEmail("analyst@docuflow.ai");
    setPassword("Analyst2026!Secure");
  };

  return (
    <div
      style={{
        minHeight: "100vh",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: "2rem",
        background: "radial-gradient(ellipse at top, #0f172a 0%, #070a13 100%)",
      }}
    >
      <div
        style={{
          width: "100%",
          maxWidth: "440px",
          background: "var(--bg-card)",
          backdropFilter: "blur(24px)",
          border: "1px solid var(--border-medium)",
          borderRadius: "var(--radius-xl)",
          padding: "2.5rem",
          boxShadow: "var(--shadow-lg), 0 0 40px rgba(99, 102, 241, 0.15)",
        }}
      >
        <div style={{ textAlign: "center", marginBottom: "2rem" }}>
          <div
            className="logo-badge"
            style={{ width: "48px", height: "48px", margin: "0 auto 1rem" }}
          >
            <Sparkles size={26} />
          </div>
          <h1 style={{ fontSize: "1.6rem", marginBottom: "0.4rem" }}>
            Sign in to <span className="text-gradient">DocuFlow</span>
          </h1>
          <p style={{ fontSize: "0.875rem", color: "var(--text-secondary)" }}>
            Enterprise Document Intelligence & Semantic Search
          </p>
        </div>

        {errorMsg && (
          <div
            style={{
              background: "rgba(244, 63, 94, 0.12)",
              border: "1px solid rgba(244, 63, 94, 0.3)",
              borderRadius: "var(--radius-md)",
              padding: "0.75rem 1rem",
              marginBottom: "1.5rem",
              display: "flex",
              alignItems: "center",
              gap: "0.6rem",
              color: "#fb7185",
              fontSize: "0.85rem",
            }}
          >
            <AlertCircle size={18} />
            <span>{errorMsg}</span>
          </div>
        )}

        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label className="form-label" htmlFor="email">
              Email Address
            </label>
            <div style={{ position: "relative" }}>
              <span
                style={{
                  position: "absolute",
                  left: "0.85rem",
                  top: "50%",
                  transform: "translateY(-50%)",
                  color: "var(--text-muted)",
                }}
              >
                <Mail size={16} />
              </span>
              <input
                id="email"
                type="email"
                required
                className="form-input"
                style={{ paddingLeft: "2.5rem" }}
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="name@company.com"
              />
            </div>
          </div>

          <div className="form-group">
            <label className="form-label" htmlFor="password">
              Password
            </label>
            <div style={{ position: "relative" }}>
              <span
                style={{
                  position: "absolute",
                  left: "0.85rem",
                  top: "50%",
                  transform: "translateY(-50%)",
                  color: "var(--text-muted)",
                }}
              >
                <Lock size={16} />
              </span>
              <input
                id="password"
                type="password"
                required
                className="form-input"
                style={{ paddingLeft: "2.5rem" }}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••••••"
              />
            </div>
          </div>

          <Button
            type="submit"
            variant="primary"
            isLoading={isLoading}
            style={{ width: "100%", marginTop: "1rem" }}
            icon={<ArrowRight size={16} />}
          >
            Sign In
          </Button>
        </form>

        <div
          style={{
            marginTop: "1.5rem",
            paddingTop: "1.25rem",
            borderTop: "1px solid var(--border-subtle)",
            fontSize: "0.8rem",
            color: "var(--text-muted)",
          }}
        >
          <div style={{ marginBottom: "0.5rem" }}>Demo quick-fill:</div>
          <div style={{ display: "flex", gap: "0.5rem" }}>
            <button
              type="button"
              onClick={fillDemoAdmin}
              className="btn btn-secondary btn-sm"
              style={{ flex: 1, fontSize: "0.75rem" }}
            >
              Admin Demo
            </button>
            <button
              type="button"
              onClick={fillDemoEditor}
              className="btn btn-secondary btn-sm"
              style={{ flex: 1, fontSize: "0.75rem" }}
            >
              Analyst Demo
            </button>
          </div>
        </div>

        <div
          style={{
            marginTop: "1.5rem",
            textAlign: "center",
            fontSize: "0.85rem",
            color: "var(--text-secondary)",
          }}
        >
          Don&apos;t have an account?{" "}
          <Link
            href="/register"
            style={{ color: "var(--accent-primary)", fontWeight: 600 }}
          >
            Create Organization
          </Link>
        </div>
      </div>
    </div>
  );
}
