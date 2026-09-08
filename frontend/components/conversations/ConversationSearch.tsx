"use client";

import { ListFilter, Search, X } from "lucide-react";

type ConversationSearchProps = {
  value: string;
  onChange: (value: string) => void;
  onFilter?: () => void;
};

export function ConversationSearch({ value, onChange, onFilter }: ConversationSearchProps) {
  return (
    <div className="flex shrink-0 items-center gap-1 px-3 py-2">
      <label className="sr-only" htmlFor="conversation-search">
        Search conversations
      </label>
      <div className="relative min-w-0 flex-1">
        <Search
          className="pointer-events-none absolute top-1/2 left-2.5 h-4 w-4 -translate-y-1/2 text-[var(--signal-muted)]"
          aria-hidden
        />
        <input
          id="conversation-search"
          type="search"
          value={value}
          onChange={(event) => onChange(event.target.value)}
          placeholder="Search"
          className="h-8 w-full rounded-lg border-0 bg-[var(--signal-search)] py-1.5 pr-8 pl-8 text-[13px] text-[var(--signal-text)] outline-none placeholder:text-[var(--signal-muted)] [&::-webkit-search-cancel-button]:hidden"
        />
        {value ? (
          <button
            type="button"
            aria-label="Clear search"
            title="Clear search"
            onClick={() => onChange("")}
            className="absolute top-1/2 right-1 inline-flex h-6 w-6 -translate-y-1/2 items-center justify-center rounded-full text-[var(--signal-muted)] hover:bg-[var(--signal-panel)]"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        ) : null}
      </div>
      <button
        type="button"
        className="icon-btn"
        aria-label="Filter"
        title="Filter"
        onClick={onFilter}
      >
        <ListFilter className="h-4 w-4" />
      </button>
    </div>
  );
}
