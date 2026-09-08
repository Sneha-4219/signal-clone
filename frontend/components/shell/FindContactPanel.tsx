"use client";

import { useState } from "react";
import { contactsApi } from "@/lib/api";

type FindContactPanelProps = {
  mode: "username" | "phone";
  onBack: () => void;
  onPickUser: (userId: number) => Promise<void>;
};

export function FindContactPanel({ mode, onBack, onPickUser }: FindContactPanelProps) {
  const [value, setValue] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const title = mode === "username" ? "Find by username" : "Find by phone number";
  const hint =
    mode === "username"
      ? "Enter a username followed by a dot and its set of numbers."
      : "Enter a phone number to find a user.";

  async function next() {
    const term = value.trim();
    if (!term) {
      setError(mode === "username" ? "Enter a username" : "Enter a phone number");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const rows = await contactsApi.search(term);
      if (rows.length === 0) {
        setError("No users found");
        return;
      }
      await onPickUser(rows[0].id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not find user");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col bg-[var(--signal-chat)]">
      <header className="flex h-12 shrink-0 items-center gap-1 bg-[var(--signal-panel)] px-2">
        <button type="button" className="icon-btn" aria-label="Back" title="Back" onClick={onBack}>
          ‹
        </button>
        <h2 className="text-[16px] font-semibold">{title}</h2>
      </header>
      <div className="px-3 pt-3">
        <input
          value={value}
          onChange={(event) => setValue(event.target.value)}
          placeholder={mode === "username" ? "username" : "phone number"}
          className="h-9 w-full rounded-lg border-0 bg-[var(--signal-composer)] px-3 text-[14px] outline-none placeholder:text-[var(--signal-muted)]"
        />
        <p className="mt-2 text-[12px] leading-4 text-[var(--signal-muted)]">{hint}</p>
        {error ? <p className="mt-2 text-[13px] text-red-600">{error}</p> : null}
      </div>
      <div className="mt-auto flex justify-end p-3">
        <button
          type="button"
          disabled={busy}
          onClick={() => void next()}
          className="rounded-md bg-[var(--signal-blue)] px-4 py-1.5 text-[14px] font-medium text-white disabled:opacity-40"
        >
          {busy ? "…" : "Next"}
        </button>
      </div>
    </div>
  );
}
