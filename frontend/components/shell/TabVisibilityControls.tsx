"use client";

import { Menu } from "lucide-react";

type TabVisibilityControlsProps = {
  tabsVisible: boolean;
  onShow: () => void;
  onHide: () => void;
};

export function TabVisibilityControls({
  tabsVisible,
  onShow,
}: TabVisibilityControlsProps) {
  if (tabsVisible) {
    return null;
  }
  return (
    <>
      <button
        type="button"
        className="icon-btn"
        aria-label="Show tabs"
        title="Show tabs"
        onClick={onShow}
      >
        <Menu className="h-[18px] w-[18px]" />
      </button>
      <button type="button" className="tabs-chip" onClick={onShow}>
        Show Tabs
      </button>
    </>
  );
}
