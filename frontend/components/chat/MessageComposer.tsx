"use client";

import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from "react";
import { Mic, Send, Smile } from "lucide-react";

const TYPING_IDLE_MS = 1000;

type MessageComposerProps = {
  onSend: (content: string) => Promise<void>;
  onTypingChange?: (isTyping: boolean) => void;
  disabled?: boolean;
  sending?: boolean;
  error?: string | null;
  onPlaceholder?: (label: string) => void;
};

export function MessageComposer({
  onSend,
  onTypingChange,
  disabled,
  sending = false,
  error = null,
  onPlaceholder,
}: MessageComposerProps) {
  const [value, setValue] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const typingSentRef = useRef(false);
  const idleTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const onTypingChangeRef = useRef(onTypingChange);

  useEffect(() => {
    onTypingChangeRef.current = onTypingChange;
  }, [onTypingChange]);

  function clearIdleTimer() {
    if (idleTimerRef.current != null) {
      clearTimeout(idleTimerRef.current);
      idleTimerRef.current = null;
    }
  }

  function stopTyping() {
    clearIdleTimer();
    if (!typingSentRef.current) {
      return;
    }
    typingSentRef.current = false;
    onTypingChangeRef.current?.(false);
  }

  function handleDraftChange(next: string) {
    setValue(next);
    if (!next.trim()) {
      stopTyping();
      return;
    }
    if (!typingSentRef.current) {
      typingSentRef.current = true;
      onTypingChangeRef.current?.(true);
    }
    clearIdleTimer();
    idleTimerRef.current = setTimeout(() => {
      stopTyping();
    }, TYPING_IDLE_MS);
  }

  useEffect(() => {
    const el = textareaRef.current;
    if (!el) {
      return;
    }
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 128)}px`;
  }, [value]);

  useEffect(() => {
    return () => {
      clearIdleTimer();
      if (typingSentRef.current) {
        typingSentRef.current = false;
        onTypingChangeRef.current?.(false);
      }
    };
  }, []);

  async function submit() {
    const content = value.trim();
    if (!content || disabled || sending) {
      return;
    }
    stopTyping();
    try {
      await onSend(content);
      setValue("");
    } catch {
      // Keep the draft so the user can retry.
    }
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    void submit();
  }

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void submit();
    }
  }

  const blocked = Boolean(disabled || sending);
  const canSend = Boolean(value.trim()) && !blocked;

  return (
    <form
      onSubmit={handleSubmit}
      className="flex shrink-0 flex-col gap-1 bg-[var(--signal-chat)] px-4 pt-1 pb-3 md:px-6"
    >
      {error ? (
        <p role="alert" className="text-sm text-red-600">
          {error}
        </p>
      ) : null}
      <div className="flex items-end">
        <div className="flex min-w-0 flex-1 items-end rounded-[10px] bg-[var(--signal-composer)] px-1 py-0.5">
          <button
            type="button"
            className="icon-btn"
            aria-label="Emoji"
            title="Emoji"
            onClick={() => onPlaceholder?.("Emoji")}
          >
            <Smile className="h-4 w-4" />
          </button>
          <label className="sr-only" htmlFor="message-composer">
            Message
          </label>
          <textarea
            id="message-composer"
            ref={textareaRef}
            rows={1}
            value={value}
            disabled={blocked}
            onChange={(event) => handleDraftChange(event.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={sending ? "Sending…" : "Message"}
            className="max-h-32 min-h-8 flex-1 resize-none overflow-y-auto bg-transparent px-1 py-1.5 text-[14px] leading-5 outline-none placeholder:text-[var(--signal-muted)]"
          />
          {canSend ? (
            <button
              type="submit"
              title="Send message"
              aria-label="Send message"
              className="mb-0.5 inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-[var(--signal-blue)] text-white hover:opacity-90"
            >
              <Send className="h-3.5 w-3.5" />
            </button>
          ) : (
            <button
              type="button"
              className="icon-btn"
              aria-label="Voice message"
              title="Voice message"
              onClick={() => onPlaceholder?.("Voice message")}
            >
              <Mic className="h-4 w-4" />
            </button>
          )}
        </div>
      </div>
    </form>
  );
}
