import React, { useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";

interface BottomSheetProps {
  open: boolean;
  onClose: () => void;
  children: React.ReactNode;
  height?: "auto" | "40%" | "60%" | "90%";
  showHandle?: boolean;
}

const heightMap: Record<string, string> = {
  auto: "auto",
  "40%": "40dvh",
  "60%": "60dvh",
  "90%": "90dvh",
};

export default function BottomSheet({
  open,
  onClose,
  children,
  height = "auto",
  showHandle = true,
}: BottomSheetProps) {
  useEffect(() => {
    if (open) {
      document.body.style.overflow = "hidden";
    } else {
      document.body.style.overflow = "";
    }
    return () => {
      document.body.style.overflow = "";
    };
  }, [open]);

  return (
    <AnimatePresence>
      {open && (
        <div className="fixed inset-0 z-50">
          {/* 遮罩 */}
          <motion.div
            className="absolute inset-0 bg-black/30"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            onClick={onClose}
          />

          {/* 面板 */}
          <motion.div
            className="absolute bottom-0 left-0 right-0 bg-white rounded-t-lg flex flex-col overflow-hidden"
            style={{
              maxHeight: heightMap[height],
              paddingBottom: "var(--safe-bottom)",
            }}
            initial={{ y: "100%" }}
            animate={{ y: 0 }}
            exit={{ y: "100%" }}
            transition={{ type: "spring", damping: 30, stiffness: 300 }}
          >
            {showHandle && (
              <div className="flex justify-center pt-3 pb-2">
                <div className="w-9 h-1 bg-neutral-300 rounded-full" />
              </div>
            )}
            <div className="flex-1 overflow-y-auto">{children}</div>
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  );
}
