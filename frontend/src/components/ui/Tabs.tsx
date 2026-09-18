"use client";

/**
 * DocuFlow AI — Tabs Component.
 */

import React from "react";

export interface TabItem {
  id: string;
  label: string;
  count?: number;
  icon?: React.ReactNode;
}

interface TabsProps {
  tabs: TabItem[];
  activeTab: string;
  onChange: (id: string) => void;
}

export function Tabs({ tabs, activeTab, onChange }: TabsProps) {
  return (
    <div className="tabs-header" role="tablist">
      {tabs.map((tab) => {
        const isActive = tab.id === activeTab;
        return (
          <button
            key={tab.id}
            role="tab"
            aria-selected={isActive}
            className={`tab-btn ${isActive ? "active" : ""}`}
            onClick={() => onChange(tab.id)}
          >
            <span style={{ display: "inline-flex", alignItems: "center", gap: "0.4rem" }}>
              {tab.icon}
              {tab.label}
              {tab.count !== undefined && (
                <span
                  style={{
                    background: isActive ? "rgba(99, 102, 241, 0.25)" : "rgba(255, 255, 255, 0.08)",
                    color: isActive ? "#a5b4fc" : "var(--text-muted)",
                    padding: "0.1rem 0.45rem",
                    borderRadius: "999px",
                    fontSize: "0.75rem",
                    fontWeight: 700,
                  }}
                >
                  {tab.count}
                </span>
              )}
            </span>
          </button>
        );
      })}
    </div>
  );
}
