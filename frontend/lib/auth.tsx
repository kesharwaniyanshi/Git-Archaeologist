"use client";

import React, { createContext, useContext, useState, useEffect } from "react";
import { AuthStatusResponse, authApi } from "./api";
import { toast } from "sonner";

interface AuthContextType {
  user: AuthStatusResponse["user"] | null;
  loading: boolean;
  loginToken: (token: string) => void;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType>({
  user: null,
  loading: true,
  loginToken: () => {},
  logout: () => {},
});

export const useAuth = () => useContext(AuthContext);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<AuthStatusResponse["user"] | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const urlToken = params.get("token");

    if (urlToken) {
      localStorage.setItem("gitarch_token", urlToken);
      window.history.replaceState({}, document.title, window.location.pathname);
      // Wait a tiny fraction of a second to ensure the React <Toaster /> element has fully mounted 
      // into the physical DOM before we fire the event!
      setTimeout(() => {
        toast.success("Successfully authenticated!");
      }, 150);
    }

    // Check local storage for token and fetch profile
    const token = localStorage.getItem("gitarch_token");
    if (token) {
      authApi.getMe()
        .then((res) => {
          if (res.authenticated) {
            setUser(res.user);
          } else {
            localStorage.removeItem("gitarch_token");
          }
        })
        .catch(() => {
          localStorage.removeItem("gitarch_token");
        })
        .finally(() => setLoading(false));
    } else {
      setLoading(false);
    }
  }, []);

  const loginToken = (token: string) => {
    localStorage.setItem("gitarch_token", token);
    setLoading(true);
    authApi.getMe()
      .then((res) => {
        if (res.authenticated) {
          setUser(res.user);
        }
      })
      .finally(() => setLoading(false));
  };

  const logout = () => {
    localStorage.removeItem("gitarch_token");
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, loading, loginToken, logout }}>
      {children}
    </AuthContext.Provider>
  );
}
