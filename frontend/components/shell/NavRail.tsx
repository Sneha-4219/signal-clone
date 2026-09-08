"use client";

import { Copy, Menu, MessageCircle, Phone, Settings } from "lucide-react";

export type RailSection = "chats" | "calls" | "stories" | "settings";

type NavRailProps = {
  section: RailSection;
  onSection: (section: RailSection) => void;
  onHideTabs: () => void;
};

export function NavRail({ section, onSection, onHideTabs }: NavRailProps) {
  return (
    <nav
      aria-label="App"
      className="relative z-20 flex h-full w-12 shrink-0 flex-col items-center overflow-visible border-r border-[var(--signal-border)] bg-[var(--signal-rail)] py-2"
    >
      <button
        type="button"
        className="rail-btn"
        aria-label="Hide tabs"
        title="Hide tabs"
        onClick={onHideTabs}
      >
        <Menu className="h-[18px] w-[18px]" strokeWidth={1.75} />
      </button>
      <div className="mt-3 flex flex-col items-center gap-1">
        <button
          type="button"
          className={`rail-btn rail-tip ${section === "chats" ? "rail-btn-active" : ""}`}
          aria-label="Chats"
          data-tip="Chats"
          aria-current={section === "chats" ? "page" : undefined}
          onClick={() => onSection("chats")}
        >
          <MessageCircle className="h-[18px] w-[18px]" strokeWidth={1.75} />
        </button>
        <button
          type="button"
          className={`rail-btn rail-tip ${section === "calls" ? "rail-btn-active" : ""}`}
          aria-label="Calls"
          data-tip="Calls"
          onClick={() => onSection("calls")}
        >
          <Phone className="h-[18px] w-[18px]" strokeWidth={1.75} />
        </button>
        <button
          type="button"
          className={`rail-btn rail-tip ${section === "stories" ? "rail-btn-active" : ""}`}
          aria-label="Stories"
          data-tip="Stories"
          onClick={() => onSection("stories")}
        >
          <Copy className="h-[18px] w-[18px]" strokeWidth={1.75} />
        </button>
      </div>
      <button
        type="button"
        className={`rail-btn mt-auto ${section === "settings" ? "rail-btn-active" : ""}`}
        aria-label="Settings"
        title="Settings"
        onClick={() => onSection("settings")}
      >
        <Settings className="h-[18px] w-[18px]" strokeWidth={1.75} />
      </button>
    </nav>
  );
}
