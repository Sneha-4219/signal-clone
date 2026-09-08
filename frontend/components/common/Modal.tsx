"use client";

import { type ReactNode, type MouseEvent } from "react";
import { X } from "lucide-react";
import { useDismissOnEscape } from "@/components/common/use-dismiss-on-escape";

type ModalProps = {
  title: string;
  onClose: () => void;
  children: ReactNode;
  wide?: boolean;
};

export function Modal({ title, onClose, children, wide = false }: ModalProps) {
  useDismissOnEscape(onClose);

  function onBackdrop(event: MouseEvent<HTMLDivElement>) {
    if (event.target === event.currentTarget) {
      onClose();
    }
  }

  return (
    <div
      className="fixed inset-0 z-30 flex items-center justify-center bg-black/30 px-4"
      onClick={onBackdrop}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="modal-title"
        className={`w-full rounded-lg border border-[var(--signal-border)] bg-[var(--signal-panel)] p-4 shadow-sm ${
          wide ? "max-w-md" : "max-w-sm"
        }`}
      >
        <div className="flex items-start justify-between gap-3">
          <h2 id="modal-title" className="text-[15px] font-semibold">
            {title}
          </h2>
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
        <div className="mt-3">{children}</div>
      </div>
    </div>
  );
}
