"use client";

import { useEffect, useState } from "react";
import styles from "./page.module.css";

interface HealthStatus {
  status: string;
  checks?: Record<string, { status: string; detail?: string }>;
}

interface BuildInfo {
  project: string;
  environment: string;
  api_version: string;
}

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000/api/v1";
const HEALTH_BASE = API_BASE.replace("/api/v1", "");

export default function HomePage() {
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [buildInfo, setBuildInfo] = useState<BuildInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchStatus() {
      try {
        const [healthRes, infoRes] = await Promise.allSettled([
          fetch(`${HEALTH_BASE}/health/ready`),
          fetch(`${HEALTH_BASE}/health/info`),
        ]);

        if (healthRes.status === "fulfilled" && healthRes.value.ok) {
          setHealth(await healthRes.value.json());
        } else if (healthRes.status === "fulfilled") {
          setHealth(await healthRes.value.json());
        }

        if (infoRes.status === "fulfilled" && infoRes.value.ok) {
          setBuildInfo(await infoRes.value.json());
        }
      } catch {
        setError("Backend API is not reachable. Is the server running?");
      } finally {
        setLoading(false);
      }
    }

    fetchStatus();
    const interval = setInterval(fetchStatus, 10000);
    return () => clearInterval(interval);
  }, []);

  return (
    <main className={styles.main}>
      <div className={styles.hero}>
        <div className={styles.glowOrb} />
        <h1 className={styles.title}>
          <span className={styles.titleAccent}>DocuFlow</span> AI
        </h1>
        <p className={styles.subtitle}>
          Document Intelligence &amp; AI Ingestion Platform
        </p>
        <p className={styles.description}>
          Parse, structure, embed, and search enterprise documents with semantic
          precision. Powered by Docling, Qdrant, and FastAPI.
        </p>
      </div>

      <div className={styles.statusGrid}>
        {/* System Status Card */}
        <div className={styles.card}>
          <div className={styles.cardHeader}>
            <div className={styles.cardIcon}>⚡</div>
            <h2>System Status</h2>
          </div>
          <div className={styles.cardBody}>
            {loading ? (
              <div className={styles.skeleton} />
            ) : error ? (
              <div className={styles.statusBadge} data-status="error">
                Offline
              </div>
            ) : (
              <div
                className={styles.statusBadge}
                data-status={health?.status === "healthy" ? "ok" : "warning"}
              >
                {health?.status === "healthy" ? "All Systems Operational" : "Degraded"}
              </div>
            )}
          </div>
        </div>

        {/* Services Card */}
        <div className={styles.card}>
          <div className={styles.cardHeader}>
            <div className={styles.cardIcon}>🔌</div>
            <h2>Service Health</h2>
          </div>
          <div className={styles.cardBody}>
            {loading ? (
              <>
                <div className={styles.skeleton} />
                <div className={styles.skeleton} style={{ width: "80%" }} />
              </>
            ) : health?.checks ? (
              <ul className={styles.serviceList}>
                {Object.entries(health.checks).map(([name, check]) => (
                  <li key={name} className={styles.serviceItem}>
                    <span
                      className={styles.dot}
                      data-status={check.status}
                    />
                    <span className={styles.serviceName}>{name}</span>
                    <span className={styles.serviceStatus}>
                      {check.status}
                    </span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className={styles.muted}>No health data available</p>
            )}
          </div>
        </div>

        {/* Build Info Card */}
        <div className={styles.card}>
          <div className={styles.cardHeader}>
            <div className={styles.cardIcon}>📦</div>
            <h2>Build Info</h2>
          </div>
          <div className={styles.cardBody}>
            {loading ? (
              <div className={styles.skeleton} />
            ) : buildInfo ? (
              <div className={styles.infoGrid}>
                <div className={styles.infoItem}>
                  <span className={styles.infoLabel}>Project</span>
                  <span className={styles.infoValue}>{buildInfo.project}</span>
                </div>
                <div className={styles.infoItem}>
                  <span className={styles.infoLabel}>Environment</span>
                  <span className={styles.infoValue}>
                    {buildInfo.environment}
                  </span>
                </div>
                <div className={styles.infoItem}>
                  <span className={styles.infoLabel}>API Version</span>
                  <span className={styles.infoValue}>
                    {buildInfo.api_version}
                  </span>
                </div>
              </div>
            ) : (
              <p className={styles.muted}>Backend not connected</p>
            )}
          </div>
        </div>

        {/* Quick Links Card */}
        <div className={styles.card}>
          <div className={styles.cardHeader}>
            <div className={styles.cardIcon}>🚀</div>
            <h2>Quick Links</h2>
          </div>
          <div className={styles.cardBody}>
            <div className={styles.linkList}>
              <a
                href={`${HEALTH_BASE}/api/docs`}
                target="_blank"
                rel="noopener noreferrer"
                className={styles.linkItem}
              >
                <span>API Documentation</span>
                <span className={styles.arrow}>→</span>
              </a>
              <a
                href={`${HEALTH_BASE}/health/ready`}
                target="_blank"
                rel="noopener noreferrer"
                className={styles.linkItem}
              >
                <span>Health Check</span>
                <span className={styles.arrow}>→</span>
              </a>
            </div>
          </div>
        </div>
      </div>
    </main>
  );
}
