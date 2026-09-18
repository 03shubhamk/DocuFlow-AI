"use client";

/**
 * DocuFlow AI — Application Shell Layout Wrapper.
 */

import React, { useState } from "react";
import { usePathname } from "next/navigation";
import { Navbar } from "./Navbar";
import { Sidebar } from "./Sidebar";

interface AppShellProps {
  children: React.ReactNode;
}

export function AppShell({ children }: AppShellProps) {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const pathname = usePathname();

  // Auth pages (login, register) use a dedicated clean layout without sidebar
  const isAuthPage = pathname === "/login" || pathname === "/register";

  if (isAuthPage) {
    return <>{children}</>;
  }

  return (
    <div className="app-layout">
      <Sidebar isOpen={sidebarOpen} />
      <div className="main-content">
        <Navbar onMenuToggle={() => setSidebarOpen((prev) => !prev)} />
        <main className="page-container">{children}</main>
      </div>
    </div>
  );
}
