"use client";

/**
 * DocuFlow AI — Authentication Context & State Provider.
 */

import React, { createContext, useCallback, useContext, useEffect, useState } from "react";
import { api, clearStoredTokens, getStoredAccessToken } from "../lib/api-client";
import { User, UserRole } from "../types/api";

interface AuthContextType {
  user: User | null;
  token: string | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  isAdmin: boolean;
  login: (credentials: { email: string; password: string }) => Promise<void>;
  register: (data: {
    email: string;
    password: string;
    full_name: string;
    tenant_name?: string;
  }) => Promise<void>;
  logout: () => Promise<void>;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const refreshUser = useCallback(async () => {
    try {
      const currentUser = await api.auth.me();
      setUser(currentUser);
      if (typeof window !== "undefined") {
        localStorage.setItem("docuflow_user", JSON.stringify(currentUser));
      }
    } catch {
      // Try refresh
      const refreshed = await api.auth.refresh();
      if (refreshed) {
        setToken(refreshed.access_token);
        const currentUser = await api.auth.me();
        setUser(currentUser);
      } else {
        clearStoredTokens();
        setUser(null);
        setToken(null);
      }
    }
  }, []);

  useEffect(() => {
    const initAuth = async () => {
      const storedToken = getStoredAccessToken();
      if (storedToken) {
        setToken(storedToken);
        const cachedUser = localStorage.getItem("docuflow_user");
        if (cachedUser) {
          try {
            setUser(JSON.parse(cachedUser));
          } catch {
            // invalid json
          }
        }
        await refreshUser();
      }
      setIsLoading(false);
    };

    initAuth();
  }, [refreshUser]);

  const login = async (credentials: { email: string; password: string }) => {
    const res = await api.auth.login(credentials);
    setUser(res.user);
    setToken(res.access_token);
  };

  const register = async (data: {
    email: string;
    password: string;
    full_name: string;
    tenant_name?: string;
  }) => {
    const res = await api.auth.register(data);
    setUser(res.user);
    setToken(res.access_token);
  };

  const logout = async () => {
    try {
      await api.auth.logout();
    } finally {
      setUser(null);
      setToken(null);
      if (typeof window !== "undefined") {
        // eslint-disable-next-line @next/next/no-location-assign-relative-destination
        window.location.href = "/login";
      }
    }
  };

  const isAdmin = user?.role === ("ADMIN" as UserRole);

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        isLoading,
        isAuthenticated: !!user && !!token,
        isAdmin,
        login,
        register,
        logout,
        refreshUser,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextType {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
