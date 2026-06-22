import React, { useState, useEffect, useRef, useCallback } from "react";
import {
  Bold, Italic, Heading, List,
  Link, Undo, Redo,
} from "lucide-react";

interface EditorToolbarProps {
  visible: boolean;
  onBold: () => void;
  onItalic: () => void;
  onHeading: () => void;
  onBulletList: () => void;
  onUndo: () => void;
  onRedo: () => void;
  activeStates: {
    bold: boolean;
    italic: boolean;
    heading: boolean;
    list: boolean;
  };
}

const BTN_BASE = "w-9 h-9 flex items-center justify-center rounded-md transition-colors";
const BTN_ACTIVE = "bg-primary-100 text-primary-600";
const BTN_INACTIVE = "text-neutral-600 active:bg-neutral-100";

export default function EditorToolbar({
  visible,
  onBold, onItalic, onHeading,
  onBulletList, onUndo, onRedo,
  activeStates,
}: EditorToolbarProps) {
  if (!visible) return null;

  return (
    <div className="fixed bottom-0 left-0 right-0 z-50 bg-white border-t border-neutral-200"
         style={{ paddingBottom: "var(--safe-bottom, 0px)" }}>
      <div className="flex items-center justify-center h-11 gap-1 px-sm">
        <button
          className={`${BTN_BASE} ${activeStates.bold ? BTN_ACTIVE : BTN_INACTIVE}`}
          onClick={onBold}
        >
          <Bold size={18} />
        </button>
        <button
          className={`${BTN_BASE} ${activeStates.italic ? BTN_ACTIVE : BTN_INACTIVE}`}
          onClick={onItalic}
        >
          <Italic size={18} />
        </button>
        <button
          className={`${BTN_BASE} ${activeStates.heading ? BTN_ACTIVE : BTN_INACTIVE}`}
          onClick={onHeading}
        >
          <Heading size={18} />
        </button>
        <button
          className={`${BTN_BASE} ${activeStates.list ? BTN_ACTIVE : BTN_INACTIVE}`}
          onClick={onBulletList}
        >
          <List size={18} />
        </button>
        <div className="w-px h-5 bg-neutral-200 mx-1" />
        <button className={`${BTN_BASE} ${BTN_INACTIVE}`} onClick={onUndo}>
          <Undo size={18} />
        </button>
        <button className={`${BTN_BASE} ${BTN_INACTIVE}`} onClick={onRedo}>
          <Redo size={18} />
        </button>
      </div>
    </div>
  );
}
