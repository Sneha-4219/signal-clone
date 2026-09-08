"use client";

import { useEffect, useState } from "react";
import { Search } from "lucide-react";
import { contactsApi, type PublicUser } from "@/lib/api";
import { Avatar } from "@/components/common/Avatar";
import { initialsFromName } from "@/lib/map-conversation";

type NewGroupDialogProps = {
  onClose: () => void;
  onCreated: (name: string, memberIds: number[]) => Promise<void>;
};

export function NewGroupDialog({ onClose, onCreated }: NewGroupDialogProps) {
  const [name, setName] = useState("");
  const [contacts, setContacts] = useState<PublicUser[]>([]);
  const [selected, setSelected] = useState<number[]>([]);
  const [query, setQuery] = useState("");
  const [searchHits, setSearchHits] = useState<PublicUser[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    contactsApi
      .list()
      .then((rows) => {
        if (!cancelled) {
          setContacts(rows.map((row) => row.user));
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Could not load contacts");
          setContacts([]);
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    const term = query.trim();
    if (!term) {
      return;
    }
    let cancelled = false;
    const timer = setTimeout(() => {
      void contactsApi
        .search(term)
        .then((rows) => {
          if (!cancelled) {
            setSearchHits(rows);
          }
        })
        .catch(() => {
          if (!cancelled) {
            setSearchHits([]);
          }
        });
    }, 250);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [query]);

  const picker = [...contacts];
  const searchTerm = query.trim();
  const extraHits = searchTerm ? searchHits : [];
  for (const hit of extraHits) {
    if (!picker.some((user) => user.id === hit.id)) {
      picker.push(hit);
    }
  }

  function toggle(userId: number) {
    setSelected((current) =>
      current.includes(userId)
        ? current.filter((id) => id !== userId)
        : [...current, userId],
    );
  }

  async function submit() {
    const trimmed = name.trim();
    if (!trimmed) {
      setError("Group name is required");
      return;
    }
    if (selected.length < 1) {
      setError("Select at least one member");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await onCreated(trimmed, selected);
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not create group");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col bg-[var(--signal-panel)]">
      <header className="flex h-14 shrink-0 items-center gap-1 px-2">
        <button type="button" className="icon-btn" aria-label="Back" title="Back" onClick={onClose}>
          ‹
        </button>
        <h2 id="new-group-title" className="text-[16px] font-semibold">
          Choose members
        </h2>
      </header>
      <div className="px-3 pb-2">
        <input
          id="group-name"
          value={name}
          onChange={(event) => setName(event.target.value)}
          className="mb-2 h-8 w-full rounded-full border-0 bg-[var(--signal-search)] px-3 text-[13px] outline-none placeholder:text-[var(--signal-muted)]"
          placeholder="Group name"
        />
        <div className="relative">
          <Search
            className="pointer-events-none absolute top-1/2 left-2.5 h-4 w-4 -translate-y-1/2 text-[var(--signal-muted)]"
            aria-hidden
          />
          <input
            id="group-member-search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            className="h-8 w-full rounded-full border-0 bg-[var(--signal-search)] py-1.5 pr-3 pl-8 text-[13px] outline-none placeholder:text-[var(--signal-muted)]"
            placeholder="Name, username, or number"
          />
        </div>
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto">
        {loading ? (
          <p className="px-4 py-6 text-[13px] text-[var(--signal-muted)]">Loading contacts…</p>
        ) : picker.length === 0 ? (
          <p className="px-4 py-6 text-center text-[13px] text-[var(--signal-muted)]">
            No contacts found
          </p>
        ) : (
          picker.map((user) => (
            <label
              key={user.id}
              className="flex cursor-pointer items-center gap-3 px-4 py-2 hover:bg-[var(--signal-hover)]"
            >
              <input
                type="checkbox"
                checked={selected.includes(user.id)}
                onChange={() => toggle(user.id)}
              />
              <Avatar
                initials={initialsFromName(user.display_name)}
                accent="#3a76f0"
                size="sm"
                src={user.avatar_url}
              />
              <span className="min-w-0">
                <span className="block truncate text-[14px]">{user.display_name}</span>
                {user.username ? (
                  <span className="block truncate text-[12px] text-[var(--signal-muted)]">
                    @{user.username}
                  </span>
                ) : null}
              </span>
            </label>
          ))
        )}
      </div>
      {error ? <p className="px-4 text-[13px] text-red-600">{error}</p> : null}
      <div className="flex justify-end p-3">
        <button
          type="button"
          disabled={saving}
          onClick={() => {
            if (selected.length < 1) {
              onClose();
              return;
            }
            void submit();
          }}
          className="rounded-md bg-[var(--signal-blue)] px-4 py-1.5 text-[14px] font-medium text-white disabled:opacity-40"
        >
          {saving ? "Creating…" : selected.length < 1 ? "Skip" : "Create"}
        </button>
      </div>
    </div>
  );
}
