"use client";

import { Check, CheckCheck, Clock } from "lucide-react";
import { isOwnMessage } from "@/lib/message-ownership";
import type { ChatMessage } from "@/lib/types";

type MessageBubbleProps = {
  message: ChatMessage;
  currentUserId: number;
  senderLabel?: string | null;
  clustered?: boolean;
};

const NAME_COLORS = ["#8e44ad", "#b8860b", "#c0392b", "#2471a3", "#1e8449"];

function nameColor(label: string): string {
  let sum = 0;
  for (let i = 0; i < label.length; i += 1) {
    sum += label.charCodeAt(i);
  }
  return NAME_COLORS[sum % NAME_COLORS.length] ?? NAME_COLORS[0];
}

function StatusIcon({ status }: { status: ChatMessage["status"] }) {
  if (status === "sending") {
    return <Clock className="h-3 w-3" aria-label="Sending" />;
  }
  if (status === "delivered" || status === "read") {
    return <CheckCheck className="h-3 w-3" aria-label={status === "read" ? "Read" : "Delivered"} />;
  }
  return <Check className="h-3 w-3" aria-label="Sent" />;
}

export function MessageBubble({
  message,
  currentUserId,
  senderLabel = null,
  clustered = false,
}: MessageBubbleProps) {
  const outgoing = isOwnMessage(message.senderId, currentUserId);
  const name = !outgoing && senderLabel && !clustered ? senderLabel : null;
  return (
    <div
      className={`flex w-full min-w-0 ${outgoing ? "justify-end" : "justify-start"} ${
        clustered ? "mt-0.5" : "mt-2.5"
      } first:mt-0`}
    >
      <div className={`flex max-w-[min(26rem,68%)] min-w-0 flex-col ${outgoing ? "items-end" : "items-start"}`}>
        <div
          className={`min-w-0 rounded-[10px] px-2.5 py-[5px] text-[14px] leading-5 ${
            outgoing
              ? "bg-[var(--signal-blue)] text-white"
              : "bg-[var(--signal-bubble-in)] text-[var(--signal-text)]"
          }`}
        >
          {name ? (
            <p
              className="mb-0.5 text-[11px] leading-4 font-medium"
              style={{ color: nameColor(name) }}
            >
              {name}
            </p>
          ) : null}
          {message.replyTo ? (
            <div className={outgoing ? "message-quote message-quote-out" : "message-quote message-quote-in"}>
              {message.replyTo.senderName ? (
                <p className="truncate text-[11px] leading-4 font-medium">{message.replyTo.senderName}</p>
              ) : null}
              <p className="line-clamp-2 text-[12px] leading-4">{message.replyTo.content}</p>
            </div>
          ) : null}
          <p className="whitespace-pre-wrap break-words">
            {message.content}
            <span
              className={`ml-1.5 inline-flex translate-y-px items-center gap-0.5 align-bottom text-[10px] leading-none ${
                outgoing ? "text-white/75" : "text-[var(--signal-muted)]"
              }`}
            >
              <time>{message.timestamp}</time>
              {outgoing ? <StatusIcon status={message.status} /> : null}
            </span>
          </p>
        </div>
      </div>
    </div>
  );
}
