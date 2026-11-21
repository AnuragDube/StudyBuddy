import React, { useState } from "react";
import { AlertTriangle, GraduationCap, LoaderCircle, LogIn, UserPlus } from "lucide-react";
import { api, ApiError, setAuthToken } from "../api/client";
import type { AuthUser } from "../types/api";

interface AuthViewProps {
  onAuthenticated: (user: AuthUser) => void;
}

export const AuthView: React.FC<AuthViewProps> = ({ onAuthenticated }) => {
  const [mode, setMode] = useState<"login" | "register">("login");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      const res =
        mode === "register"
          ? await api.register({ name: name.trim(), email: email.trim(), password })
          : await api.login({ email: email.trim(), password });
      setAuthToken(res.access_token);
      onAuthenticated(res.user);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="auth-shell">
      <div className="auth-card">
        <div className="auth-brand">
          <div className="brand-mark">
            <GraduationCap size={22} />
          </div>
          <div>
            <b>Study Buddy</b>
            <span>MULTI-SUBJECT AI PLANNER</span>
          </div>
        </div>

        <div className="auth-tabs" role="tablist">
          <button
            type="button"
            role="tab"
            aria-selected={mode === "login"}
            className={mode === "login" ? "active" : ""}
            onClick={() => {
              setMode("login");
              setError("");
            }}
          >
            Sign In
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={mode === "register"}
            className={mode === "register" ? "active" : ""}
            onClick={() => {
              setMode("register");
              setError("");
            }}
          >
            Create Account
          </button>
        </div>

        <h1>{mode === "login" ? "Welcome back" : "Create your study space"}</h1>
        <p className="auth-sub">
          {mode === "login"
            ? "Sign in to access your saved subjects, capacity limits, and schedule."
            : "Each account keeps its own private subjects, daily capacity, and timetable."}
        </p>

        {error && (
          <div className="error-banner" role="alert" style={{ marginBottom: 14 }}>
            <AlertTriangle size={15} /> {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="auth-form">
          {mode === "register" && (
            <div className="field">
              <label className="field-label">Full name</label>
              <input
                type="text"
                required
                placeholder="e.g. Anurag Dube"
                value={name}
                onChange={(e) => setName(e.target.value)}
              />
            </div>
          )}

          <div className="field">
            <label className="field-label">Email address</label>
            <input
              type="email"
              required
              placeholder="student@university.edu"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </div>

          <div className="field">
            <label className="field-label">
              Password {mode === "register" && <span>Min 6 characters</span>}
            </label>
            <input
              type="password"
              required
              minLength={mode === "register" ? 6 : 1}
              placeholder="••••••••"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </div>

          <button type="submit" className="primary-btn auth-submit" disabled={busy}>
            {busy ? (
              <LoaderCircle size={15} className="spin" />
            ) : mode === "login" ? (
              <LogIn size={15} />
            ) : (
              <UserPlus size={15} />
            )}
            {busy
              ? "Please wait…"
              : mode === "login"
              ? "Sign In"
              : "Create Account"}
          </button>
        </form>
      </div>
    </div>
  );
};
