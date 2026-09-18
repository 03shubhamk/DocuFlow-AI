"use client";

/**
 * DocuFlow AI — Collapsible Navigation Sidebar.
 */

import React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  FileText,
  UploadCloud,
  Search,
  Settings,
  ShieldCheck,
  User as UserIcon,
  Sparkles,
} from "lucide-react";
import { useAuth } from "../../context/AuthContext";

export function Sidebar({ isOpen }: { isOpen?: boolean }) {
  const pathname = usePathname();
  const { user, isAdmin } = useAuth();

  const navItems = [
    { label: "Dashboard", href: "/dashboard", icon: <LayoutDashboard size={18} /> },
    { label: "Documents", href: "/documents", icon: <FileText size={18} /> },
    { label: "Upload Document", href: "/documents/upload", icon: <UploadCloud size={18} /> },
    { label: "Search Intelligence", href: "/search", icon: <Search size={18} /> },
  ];

  const secondaryItems = [
    { label: "User Profile", href: "/profile", icon: <UserIcon size={18} /> },
    { label: "Settings", href: "/settings", icon: <Settings size={18} /> },
  ];

  return (
    <aside className={`sidebar ${isOpen ? "open" : ""}`}>
      <div className="sidebar-header">
        <div className="logo-badge">
          <Sparkles size={20} />
        </div>
        <div>
          <div className="sidebar-title">
            <span className="text-gradient">DocuFlow</span> AI
          </div>
          <div style={{ fontSize: "0.7rem", color: "var(--text-muted)", fontWeight: 500 }}>
            Document Intelligence
          </div>
        </div>
      </div>

      <nav className="sidebar-nav">
        <div className="nav-section-label">Workspace</div>
        {navItems.map((item) => {
          const isActive =
            pathname === item.href ||
            (item.href !== "/dashboard" && pathname?.startsWith(item.href));
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`nav-link ${isActive ? "active" : ""}`}
            >
              {item.icon}
              <span>{item.label}</span>
            </Link>
          );
        })}

        {isAdmin && (
          <>
            <div className="nav-section-label">Administration</div>
            <Link
              href="/admin"
              className={`nav-link ${pathname?.startsWith("/admin") ? "active" : ""}`}
            >
              <ShieldCheck size={18} />
              <span>Admin Dashboard</span>
            </Link>
          </>
        )}

        <div className="nav-section-label">Preferences</div>
        {secondaryItems.map((item) => {
          const isActive = pathname === item.href;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`nav-link ${isActive ? "active" : ""}`}
            >
              {item.icon}
              <span>{item.label}</span>
            </Link>
          );
        })}
      </nav>

      {user && (
        <div className="sidebar-footer">
          <div className="user-snippet">
            <div className="user-avatar">
              {user.full_name?.charAt(0).toUpperCase() || "U"}
            </div>
            <div style={{ overflow: "hidden" }}>
              <div
                style={{
                  fontSize: "0.85rem",
                  fontWeight: 600,
                  whiteSpace: "nowrap",
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                }}
              >
                {user.full_name}
              </div>
              <div
                style={{
                  fontSize: "0.7rem",
                  color: "var(--text-muted)",
                  textTransform: "capitalize",
                }}
              >
                {user.role?.toLowerCase()}
              </div>
            </div>
          </div>
        </div>
      )}
    </aside>
  );
}
