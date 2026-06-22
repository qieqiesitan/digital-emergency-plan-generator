import React, { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Plus, X } from "lucide-react";

interface SpeedDialAction {
  icon: React.ReactNode;
  label: string;
  onPress: () => void;
}

interface FABProps {
  icon?: React.ReactNode;
  onClick?: () => void;
  mini?: boolean;
  extended?: boolean;
  label?: string;
  speedDialActions?: SpeedDialAction[];
  className?: string;
}

export default function FAB({
  icon,
  onClick,
  mini = false,
  extended = false,
  label,
  speedDialActions,
  className = "",
}: FABProps) {
  const [open, setOpen] = useState(false);
  const hasSpeedDial = speedDialActions && speedDialActions.length > 0;

  const size = mini ? "w-10 h-10" : "w-14 h-14";
  const iconSize = mini ? 20 : 24;

  const handlePress = () => {
    if (hasSpeedDial) {
      setOpen(!open);
    } else {
      onClick?.();
    }
  };

  return (
    <>
      {/* Speed Dial 遮罩 */}
      <AnimatePresence>
        {open && (
          <motion.div
            className="fixed inset-0 z-40 bg-black/20"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={() => setOpen(false)}
          />
        )}
      </AnimatePresence>

      {/* Speed Dial 菜单项 */}
      <AnimatePresence>
        {open &&
          hasSpeedDial &&
          speedDialActions!.map((action, i) => (
            <motion.button
              key={i}
              className="fixed right-4 z-50 flex items-center gap-sm bg-white rounded-full shadow-fab h-12 px-4"
              style={{
                bottom: `calc(16px + var(--safe-bottom) + var(--tabbar-height) + ${(speedDialActions!.length - i) * 60 + 72}px)`,
              }}
              initial={{ opacity: 0, y: 10, scale: 0.8 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: 10, scale: 0.8 }}
              transition={{ delay: i * 0.03 }}
              onClick={() => {
                action.onPress();
                setOpen(false);
              }}
            >
              <span className="text-neutral-600">{action.icon}</span>
              <span className="text-body-sm font-medium text-neutral-900 whitespace-nowrap">
                {action.label}
              </span>
            </motion.button>
          ))}

        {/* FAB 按钮 */}
        <motion.button
          className={`fixed right-4 z-50 ${size} rounded-full bg-primary-600 shadow-fab flex items-center justify-center text-white active:scale-95 transition-transform ${extended ? "px-5 w-auto gap-sm" : ""} ${className}`}
          style={{
            bottom: `calc(16px + var(--safe-bottom) + var(--tabbar-height))`,
          }}
          onClick={handlePress}
          animate={{ rotate: open ? 45 : 0 }}
          transition={{ duration: 0.2 }}
        >
          {open ? <X size={iconSize} /> : icon ?? <Plus size={iconSize} />}
          {extended && label && (
            <span className="text-body font-semibold">{label}</span>
          )}
        </motion.button>
      </AnimatePresence>
    </>
  );
}
