"use client";

import { MessageCircle } from "lucide-react";

type WelcomePaneProps = {
  onPlaceholder?: (label: string) => void;
};

export function WelcomePane({ onPlaceholder }: WelcomePaneProps) {
  return (
    <section className="relative hidden min-w-0 flex-1 flex-col items-center justify-center bg-[var(--signal-chat)] md:flex">
      <div className="flex flex-col items-center px-6">
        <span className="inline-flex h-16 w-16 items-center justify-center rounded-full bg-[var(--signal-blue)] text-white">
          <MessageCircle className="h-8 w-8" strokeWidth={2} />
        </span>
        <h1 className="mt-4 text-[20px] font-semibold text-[var(--signal-text)]">
          Welcome to Signal
        </h1>
        <p className="mt-1 text-[13px] text-[var(--signal-muted)]">
          See{" "}
          <button
            type="button"
            className="text-[var(--signal-blue)] hover:underline"
            onClick={() => onPlaceholder?.("What's new")}
          >
            what&apos;s new
          </button>{" "}
          in this update
        </p>
      </div>
      <p className="absolute bottom-4 text-[11px] text-[var(--signal-muted)]">
        Signal is a 501c3 nonprofit
      </p>
    </section>
  );
}
