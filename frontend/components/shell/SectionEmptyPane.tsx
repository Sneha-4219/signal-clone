"use client";

import { type ReactNode } from "react";

type SectionEmptyPaneProps = {
  icon: ReactNode;
  message: ReactNode;
};

export function SectionEmptyPane({ icon, message }: SectionEmptyPaneProps) {
  return (
    <section className="hidden min-w-0 flex-1 flex-col items-center justify-center bg-[var(--signal-chat)] md:flex">
      <div className="flex max-w-sm flex-col items-center px-6 text-center">
        <span className="text-[var(--signal-muted)]">{icon}</span>
        <p className="mt-3 text-[13px] leading-5 text-[var(--signal-muted)]">{message}</p>
      </div>
    </section>
  );
}
