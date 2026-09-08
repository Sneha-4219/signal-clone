"use client";

import { useState, type FormEvent } from "react";
import { splitIdentifier } from "@/lib/api";
import { useAuth } from "@/components/auth/AuthProvider";

type Mode = "login" | "register";

export function AuthScreen() {
  const { login, register } = useAuth();
  const [mode, setMode] = useState<Mode>("login");
  const [identifier, setIdentifier] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [avatarUrl, setAvatarUrl] = useState("");
  const [otp, setOtp] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    const ids = splitIdentifier(identifier);
    if (!ids.username && !ids.phone) {
      setError("Provide a username or a phone number");
      return;
    }
    setSubmitting(true);
    try {
      if (mode === "login") {
        await login({ ...ids, otp });
      } else {
        await register({
          ...ids,
          display_name: displayName,
          avatar_url: avatarUrl.trim() || null,
          otp,
        });
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="flex h-dvh items-center justify-center bg-[var(--signal-chat)] px-4">
      <div className="w-full max-w-sm rounded-xl border border-[var(--signal-border)] bg-[var(--signal-panel)] p-6">
        <p className="text-center text-lg font-semibold text-[var(--signal-blue)]">
          Signal
        </p>
        <h1 className="mt-1 text-center text-xl font-semibold text-[var(--signal-text)]">
          {mode === "login" ? "Sign in" : "Create account"}
        </h1>
        <p className="mt-1 text-center text-sm text-[var(--signal-muted)]">
          Use OTP 123456
        </p>
        <form onSubmit={handleSubmit} className="mt-5 flex flex-col gap-3">
          <label className="text-sm">
            <span className="mb-1 block text-[var(--signal-muted)]">
              Username or phone
            </span>
            <input
              required
              value={identifier}
              onChange={(event) => setIdentifier(event.target.value)}
              autoComplete="username"
              className="h-10 w-full rounded-lg border border-[var(--signal-border)] bg-[var(--signal-search)] px-3 text-sm text-[var(--signal-text)] outline-none focus:border-[var(--signal-blue)]"
            />
          </label>
          {mode === "register" ? (
            <>
              <label className="text-sm">
                <span className="mb-1 block text-[var(--signal-muted)]">
                  Display name
                </span>
                <input
                  required
                  value={displayName}
                  onChange={(event) => setDisplayName(event.target.value)}
                  autoComplete="name"
                  className="h-10 w-full rounded-lg border border-[var(--signal-border)] bg-[var(--signal-search)] px-3 text-sm text-[var(--signal-text)] outline-none focus:border-[var(--signal-blue)]"
                />
              </label>
              <label className="text-sm">
                <span className="mb-1 block text-[var(--signal-muted)]">
                  Avatar URL (optional)
                </span>
                <input
                  value={avatarUrl}
                  onChange={(event) => setAvatarUrl(event.target.value)}
                  placeholder="https://…"
                  className="h-10 w-full rounded-lg border border-[var(--signal-border)] bg-[var(--signal-search)] px-3 text-sm text-[var(--signal-text)] outline-none focus:border-[var(--signal-blue)]"
                />
              </label>
            </>
          ) : null}
          <label className="text-sm">
            <span className="mb-1 block text-[var(--signal-muted)]">OTP</span>
            <input
              required
              value={otp}
              onChange={(event) => setOtp(event.target.value)}
              inputMode="numeric"
              autoComplete="one-time-code"
              className="h-10 w-full rounded-lg border border-[var(--signal-border)] bg-[var(--signal-search)] px-3 text-sm text-[var(--signal-text)] outline-none focus:border-[var(--signal-blue)]"
            />
          </label>
          {error ? (
            <p role="alert" className="text-sm text-red-600">
              {error}
            </p>
          ) : null}
          <button
            type="submit"
            disabled={submitting}
            className="mt-1 h-10 rounded-lg bg-[var(--signal-blue)] text-sm font-medium text-white hover:opacity-90 disabled:opacity-50"
          >
            {submitting
              ? "Please wait…"
              : mode === "login"
                ? "Log in"
                : "Register"}
          </button>
        </form>
        <p className="mt-4 text-center text-sm text-[var(--signal-muted)]">
          {mode === "login" ? "New here?" : "Already have an account?"}{" "}
          <button
            type="button"
            className="font-medium text-[var(--signal-blue)]"
            onClick={() => {
              setMode(mode === "login" ? "register" : "login");
              setError(null);
            }}
          >
            {mode === "login" ? "Create an account" : "Sign in"}
          </button>
        </p>
      </div>
    </div>
  );
}
