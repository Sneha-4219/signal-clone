"use client";

import { Modal } from "@/components/common/Modal";
import { Avatar } from "@/components/common/Avatar";
import type { AuthUser } from "@/lib/api";

type ProfileDialogProps = {
  user: AuthUser;
  onClose: () => void;
};

export function ProfileDialog({ user, onClose }: ProfileDialogProps) {
  const initials = user.display_name.trim().slice(0, 1).toUpperCase() || "Y";
  return (
    <Modal title="Profile" onClose={onClose}>
      <div className="flex items-center gap-3">
        <Avatar
          initials={initials}
          accent="#3a76f0"
          size="lg"
          src={user.avatar_url}
        />
        <div className="min-w-0">
          <p className="truncate font-semibold">{user.display_name}</p>
          {user.username ? (
            <p className="truncate text-sm text-[var(--signal-muted)]">@{user.username}</p>
          ) : null}
        </div>
      </div>
      <dl className="mt-4 space-y-2 text-sm">
        <div>
          <dt className="text-xs text-[var(--signal-muted)]">Phone</dt>
          <dd>{user.phone ?? "Not set"}</dd>
        </div>
        <div>
          <dt className="text-xs text-[var(--signal-muted)]">Status</dt>
          <dd>{user.is_online ? "Online" : "Offline"}</dd>
        </div>
      </dl>
      <p className="mt-4 text-xs text-[var(--signal-muted)]">
        Profile editing — Coming Soon
      </p>
      <div className="mt-4 flex justify-end">
        <button
          type="button"
          onClick={onClose}
          className="rounded-lg px-3 py-1.5 text-sm hover:bg-[var(--signal-hover)]"
        >
          Close
        </button>
      </div>
    </Modal>
  );
}
