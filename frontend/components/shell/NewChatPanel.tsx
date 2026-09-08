"use client";

import { useEffect, useState } from "react";
import { AtSign, Hash, Search, Users } from "lucide-react";
import { contactsApi, type PublicUser } from "@/lib/api";
import { Avatar } from "@/components/common/Avatar";
import { initialsFromName } from "@/lib/map-conversation";

type NewChatPanelProps = {
  onBack: () => void;
  onNewGroup: () => void;
  onFindUsername: () => void;
  onFindPhone: () => void;
  onPickUser: (userId: number) => Promise<void>;
};

export function NewChatPanel({
  onBack,
  onNewGroup,
  onFindUsername,
  onFindPhone,
  onPickUser,
}: NewChatPanelProps) {
  const [query, setQuery] = useState("");
  const [contacts, setContacts] = useState<PublicUser[]>([]);
  const [hits, setHits] = useState<PublicUser[]>([]);
  const [busyId, setBusyId] = useState<number | null>(null);

  useEffect(() => {
    let cancelled = false;
    contactsApi
      .list()
      .then((rows) => {
        if (!cancelled) {
          setContacts(rows.map((row) => row.user));
        }
      })
      .catch(() => {
        if (!cancelled) {
          setContacts([]);
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
            setHits(rows);
          }
        })
        .catch(() => {
          if (!cancelled) {
            setHits([]);
          }
        });
    }, 250);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [query]);

  const rows = query.trim() ? hits : contacts;

  return (
    <div className="flex min-h-0 flex-1 flex-col bg-[var(--signal-panel)]">
      <header className="flex h-14 shrink-0 items-center gap-1 px-2">
        <button type="button" className="icon-btn" aria-label="Back" title="Back" onClick={onBack}>
          ‹
        </button>
        <h2 className="text-[16px] font-semibold">New chat</h2>
      </header>
      <div className="px-3 pb-2">
        <div className="relative">
          <Search
            className="pointer-events-none absolute top-1/2 left-2.5 h-4 w-4 -translate-y-1/2 text-[var(--signal-muted)]"
            aria-hidden
          />
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Name, username, or number"
            className="h-8 w-full rounded-full border-0 bg-[var(--signal-search)] py-1.5 pr-3 pl-8 text-[13px] outline-none placeholder:text-[var(--signal-muted)]"
          />
        </div>
      </div>
      <button
        type="button"
        className="flex items-center gap-3 px-4 py-2.5 text-left text-[14px] hover:bg-[var(--signal-hover)]"
        onClick={onNewGroup}
      >
        <Users className="h-5 w-5 text-[var(--signal-muted)]" />
        New group
      </button>
      <button
        type="button"
        className="flex items-center gap-3 px-4 py-2.5 text-left text-[14px] hover:bg-[var(--signal-hover)]"
        onClick={onFindUsername}
      >
        <AtSign className="h-5 w-5 text-[var(--signal-muted)]" />
        Find by username
      </button>
      <button
        type="button"
        className="flex items-center gap-3 px-4 py-2.5 text-left text-[14px] hover:bg-[var(--signal-hover)]"
        onClick={onFindPhone}
      >
        <Hash className="h-5 w-5 text-[var(--signal-muted)]" />
        Find by phone number
      </button>
      <p className="mt-3 px-4 text-[12px] font-medium text-[var(--signal-muted)]">Contacts</p>
      <div className="min-h-0 flex-1 overflow-y-auto">
        {rows.length === 0 ? (
          <p className="px-4 py-6 text-[13px] text-[var(--signal-muted)]">No contacts found</p>
        ) : (
          rows.map((user) => (
            <button
              key={user.id}
              type="button"
              disabled={busyId != null}
              className="flex w-full items-center gap-3 px-4 py-2 text-left hover:bg-[var(--signal-hover)] disabled:opacity-50"
              onClick={() => {
                setBusyId(user.id);
                void onPickUser(user.id).finally(() => setBusyId(null));
              }}
            >
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
            </button>
          ))
        )}
      </div>
    </div>
  );
}
