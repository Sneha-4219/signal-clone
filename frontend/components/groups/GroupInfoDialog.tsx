"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { X } from "lucide-react";
import { contactsApi, conversationsApi, type GroupMemberOut, type PublicUser } from "@/lib/api";
import { Avatar } from "@/components/common/Avatar";
import { useDismissOnEscape } from "@/components/common/use-dismiss-on-escape";
import { initialsFromName } from "@/lib/map-conversation";
import type { Conversation } from "@/lib/types";

type GroupInfoDialogProps = {
  conversation: Conversation;
  currentUserId: number;
  onClose: () => void;
  onMemberCountChange: (count: number) => void;
  onLeftGroup: () => void;
  onToast?: (message: string) => void;
};

export function GroupInfoDialog({
  conversation,
  currentUserId,
  onClose,
  onMemberCountChange,
  onLeftGroup,
  onToast,
}: GroupInfoDialogProps) {
  useDismissOnEscape(onClose);
  const [members, setMembers] = useState<GroupMemberOut[]>([]);
  const [contacts, setContacts] = useState<PublicUser[]>([]);
  const [addUserId, setAddUserId] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);

  const conversationId = Number(conversation.id);
  const myRole = members.find((member) => member.user_id === currentUserId)?.role
    ?? conversation.myRole;
  const isAdmin = myRole === "admin";
  const adminCount = members.filter((member) => member.role === "admin").length;

  async function reload() {
    const rows = await conversationsApi.listMembers(conversationId);
    setMembers(rows);
    onMemberCountChange(rows.length);
  }

  const onMemberCountChangeRef = useRef(onMemberCountChange);

  useEffect(() => {
    onMemberCountChangeRef.current = onMemberCountChange;
  }, [onMemberCountChange]);

  useEffect(() => {
    let cancelled = false;
    conversationsApi
      .listMembers(conversationId)
      .then((rows) => {
        if (!cancelled) {
          setMembers(rows);
          onMemberCountChangeRef.current(rows.length);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Could not load members");
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });
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
  }, [conversationId]);

  const addable = useMemo(
    () =>
      contacts.filter(
        (user) => !members.some((member) => member.user_id === user.id),
      ),
    [contacts, members],
  );

  async function addMember() {
    const userId = Number(addUserId);
    if (!Number.isInteger(userId) || userId < 1) {
      setError("Select a user to add");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await conversationsApi.addMember(conversationId, userId);
      setAddUserId("");
      await reload();
      onToast?.("Member added");
      setNotice("Member added");
    } catch (err) {
      const message = err instanceof Error ? err.message : "Could not add member";
      setError(message);
      onToast?.(message);
    } finally {
      setBusy(false);
    }
  }

  async function removeMember(userId: number) {
    setBusy(true);
    setError(null);
    try {
      await conversationsApi.removeMember(conversationId, userId);
      if (userId === currentUserId) {
        onLeftGroup();
        onClose();
        return;
      }
      await reload();
      onToast?.("Member removed");
      setNotice("Member removed");
    } catch (err) {
      const message = err instanceof Error ? err.message : "Could not remove member";
      setError(message);
      onToast?.(message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div
      className="fixed inset-0 z-30 flex items-center justify-center bg-black/30 px-4"
      onClick={(event) => {
        if (event.target === event.currentTarget) {
          onClose();
        }
      }}
    >
      <div
        role="dialog"
        aria-labelledby="group-info-title"
        className="w-full max-w-md rounded-lg border border-[var(--signal-border)] bg-[var(--signal-panel)] p-4 shadow-sm"
      >
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <h2 id="group-info-title" className="truncate text-[15px] font-semibold">
              {conversation.name}
            </h2>
            <p className="text-xs text-[var(--signal-muted)]">
              {members.length || conversation.memberCount || 0} members
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="icon-btn"
            aria-label="Close"
            title="Close"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
        <div className="mt-3 max-h-64 overflow-y-auto">
          {loading ? (
            <p className="py-4 text-sm text-[var(--signal-muted)]">Loading members…</p>
          ) : (
            members.map((member) => {
              const canRemoveOther = isAdmin && member.user_id !== currentUserId;
              const canLeave =
                member.user_id === currentUserId &&
                !(member.role === "admin" && adminCount <= 1);
              return (
                <div
                  key={member.user_id}
                  className="flex items-center gap-3 py-2"
                >
                  <Avatar
                    initials={initialsFromName(member.display_name)}
                    accent="#7c4dff"
                    size="sm"
                    src={member.avatar_url}
                  />
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium">
                      {member.display_name}
                      {member.user_id === currentUserId ? " (you)" : ""}
                    </p>
                    <p className="truncate text-xs text-[var(--signal-muted)]">
                      {member.username ? `@${member.username} · ` : ""}
                      {member.role === "admin" ? "Admin" : "Member"}
                    </p>
                  </div>
                  {canRemoveOther ? (
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() => void removeMember(member.user_id)}
                      className="text-xs font-medium text-red-600 disabled:opacity-40"
                    >
                      Remove
                    </button>
                  ) : null}
                  {canLeave ? (
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() => void removeMember(member.user_id)}
                      className="text-xs font-medium text-[var(--signal-blue)] disabled:opacity-40"
                    >
                      Leave
                    </button>
                  ) : null}
                </div>
              );
            })
          )}
        </div>
        {isAdmin ? (
          <div className="mt-3 border-t border-[var(--signal-border)] pt-3">
            <p className="text-xs font-medium text-[var(--signal-muted)]">Add member</p>
            {addable.length === 0 ? (
              <p className="mt-1 text-sm text-[var(--signal-muted)]">
                No additional contacts to add.
              </p>
            ) : (
              <div className="mt-2 flex gap-2">
                <select
                  value={addUserId}
                  onChange={(event) => setAddUserId(event.target.value)}
                  className="h-9 min-w-0 flex-1 rounded-lg border border-[var(--signal-border)] bg-[var(--signal-search)] px-2 text-sm"
                >
                  <option value="">Select a contact</option>
                  {addable.map((user) => (
                    <option key={user.id} value={user.id}>
                      {user.display_name}
                    </option>
                  ))}
                </select>
                <button
                  type="button"
                  disabled={busy || !addUserId}
                  onClick={() => void addMember()}
                  className="rounded-lg bg-[var(--signal-blue)] px-3 text-sm font-medium text-white disabled:opacity-40"
                >
                  Add
                </button>
              </div>
            )}
          </div>
        ) : null}
        {error ? <p className="mt-2 text-sm text-red-600">{error}</p> : null}
        {notice ? <p className="mt-2 text-sm text-[var(--signal-blue)]">{notice}</p> : null}
        <div className="mt-4 flex justify-end">
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg px-3 py-1.5 text-sm hover:bg-[var(--signal-hover)]"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
