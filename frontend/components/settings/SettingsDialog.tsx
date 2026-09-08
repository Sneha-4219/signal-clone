"use client";

import { useState } from "react";
import {
  Bell,
  Heart,
  LineChart,
  Lock,
  LogOut,
  MessageCircle,
  Palette,
  Phone,
  RotateCcw,
  Settings,
} from "lucide-react";
import { Avatar } from "@/components/common/Avatar";
import { TabVisibilityControls } from "@/components/shell/TabVisibilityControls";
import { useTheme, type ThemeName } from "@/components/theme/ThemeProvider";
import type { AuthUser } from "@/lib/api";

const NAV = [
  { id: "profile", label: "Profile", icon: null },
  { id: "general", label: "General", icon: Settings },
  { id: "appearance", label: "Appearance", icon: Palette },
  { id: "chats", label: "Chats", icon: MessageCircle },
  { id: "calls", label: "Calls", icon: Phone },
  { id: "notifications", label: "Notifications", icon: Bell },
  { id: "privacy", label: "Privacy", icon: Lock },
  { id: "data", label: "Data usage", icon: LineChart },
  { id: "backups", label: "Backups", icon: RotateCcw },
  { id: "donate", label: "Donate to Signal", icon: Heart },
] as const;

type SettingsDialogProps = {
  user?: AuthUser | null;
  tabsVisible: boolean;
  onShowTabs: () => void;
  onHideTabs: () => void;
  onLogout: () => void;
  onClose: () => void;
};

export function SettingsDialog({
  user,
  tabsVisible,
  onShowTabs,
  onHideTabs,
  onLogout,
}: SettingsDialogProps) {
  const [section, setSection] = useState<(typeof NAV)[number]["id"]>("profile");
  const { theme, setTheme } = useTheme();
  const initials = user?.display_name.trim().slice(0, 1).toUpperCase() || "Y";

  return (
    <div className="flex min-h-0 min-w-0 flex-1 bg-[var(--signal-chat)]">
      <aside className="flex w-[280px] shrink-0 flex-col overflow-y-auto border-r border-[var(--signal-border)] bg-[var(--signal-panel)]">
        <div className="flex items-center gap-2 px-3 pt-3 pb-1">
          <TabVisibilityControls
            tabsVisible={tabsVisible}
            onShow={onShowTabs}
            onHide={onHideTabs}
          />
          {tabsVisible ? <h2 className="text-[18px] font-semibold">Settings</h2> : null}
        </div>
        {tabsVisible ? null : <h2 className="px-4 pb-2 text-[18px] font-semibold">Settings</h2>}
        {user ? (
          <button
            type="button"
            onClick={() => setSection("profile")}
            className={`mx-3 mb-2 flex items-center gap-3 rounded-lg px-2 py-2 text-left ${
              section === "profile" ? "bg-[var(--signal-search)]" : "hover:bg-[var(--signal-hover)]"
            }`}
          >
            <Avatar initials={initials} accent="#3a76f0" size="sm" src={user.avatar_url} />
            <span className="min-w-0">
              <span className="block truncate text-[14px]">{user.display_name}</span>
              <span className="block truncate text-[12px] text-[var(--signal-muted)]">
                {user.phone ?? (user.username ? `@${user.username}` : "")}
              </span>
            </span>
          </button>
        ) : null}
        <ul className="pb-4">
          {NAV.filter((item) => item.id !== "profile").map((item) => {
            const Icon = item.icon;
            return (
              <li key={item.id}>
                <button
                  type="button"
                  onClick={() => setSection(item.id)}
                  className={`flex w-full items-center gap-3 px-4 py-2.5 text-left text-[14px] ${
                    section === item.id ? "bg-[var(--signal-search)]" : "hover:bg-[var(--signal-hover)]"
                  }`}
                >
                  {Icon ? <Icon className="h-4 w-4 text-[var(--signal-muted)]" /> : null}
                  {item.label}
                </button>
              </li>
            );
          })}
        </ul>
      </aside>
      <section className="min-w-0 flex-1 overflow-y-auto px-10 py-8">
        {section === "profile" && user ? (
          <div className="mx-auto max-w-md">
            <h3 className="text-center text-[18px] font-semibold">Profile</h3>
            <div className="mt-6 flex flex-col items-center">
              <Avatar initials={initials} accent="#3a76f0" size="lg" src={user.avatar_url} />
              <p className="mt-2 text-[13px] text-[var(--signal-blue)]">Edit photo — Coming Soon</p>
            </div>
            <div className="mt-8 space-y-5 text-[14px]">
              <div>
                <p>{user.display_name}</p>
              </div>
              <div>
                <p>About</p>
                <p className="mt-1 text-[12px] text-[var(--signal-muted)]">
                  Your profile and changes to it will be visible to people you message, contacts and
                  groups.
                </p>
              </div>
              <div>
                <p>Username</p>
                <p className="text-[13px] text-[var(--signal-muted)]">
                  {user.username ? `@${user.username}` : "Not set"}
                </p>
                <p className="mt-1 text-[12px] text-[var(--signal-muted)]">
                  People can now message you using your optional username so you don&apos;t have to
                  give out your phone number.
                </p>
              </div>
              {user.phone ? (
                <div>
                  <p>Phone</p>
                  <p className="text-[13px] text-[var(--signal-muted)]">{user.phone}</p>
                </div>
              ) : null}
              <p className="text-[12px] text-[var(--signal-muted)]">Profile editing — Coming Soon</p>
              <button
                type="button"
                onClick={onLogout}
                className="mt-4 inline-flex items-center gap-2 text-[14px] text-[var(--signal-muted)] hover:text-[var(--signal-text)]"
              >
                <LogOut className="h-4 w-4" />
                Log out
              </button>
            </div>
          </div>
        ) : section === "appearance" ? (
          <div className="mx-auto max-w-md pt-4">
            <h3 className="text-[18px] font-semibold">Appearance</h3>
            <fieldset className="mt-5 space-y-3">
              <legend className="sr-only">Theme</legend>
              {(["light", "dark"] as ThemeName[]).map((option) => (
                <label key={option} className="flex cursor-pointer items-center gap-3 text-[14px]">
                  <input
                    type="radio"
                    name="appearance-theme"
                    value={option}
                    checked={theme === option}
                    onChange={() => setTheme(option)}
                    className="accent-[var(--signal-blue)]"
                  />
                  <span className="capitalize">{option}</span>
                </label>
              ))}
            </fieldset>
          </div>
        ) : (
          <div className="mx-auto max-w-md pt-10">
            <h3 className="text-[18px] font-semibold capitalize">{section}</h3>
            <p className="mt-2 text-[13px] text-[var(--signal-muted)]">Coming Soon</p>
          </div>
        )}
      </section>
    </div>
  );
}
