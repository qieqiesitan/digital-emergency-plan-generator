import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";
import Spinner from "@/mobile/components/ui/Spinner";
import SafeArea from "@/mobile/components/ui/SafeArea";
import { AlertCircle } from "lucide-react";
import Button from "@/mobile/components/ui/Button";

export default function SplashScreen() {
  const navigate = useNavigate();
  const { isAuthenticated, isLoading } = useAuth();
  const [showBrand, setShowBrand] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (isLoading) return;

    const timer = setTimeout(() => {
      if (isAuthenticated) {
        navigate("/m/dashboard", { replace: true });
      } else {
        navigate("/m/login", { replace: true });
      }
    }, 1500);

    return () => clearTimeout(timer);
  }, [isAuthenticated, isLoading, navigate]);

  if (error) {
    return (
      <SafeArea>
        <div className="flex flex-col items-center justify-center h-dvh px-md text-center">
          <AlertCircle size={48} className="text-danger mb-md" />
          <h1 className="text-h2 text-neutral-900 mb-sm">启动失败</h1>
          <p className="text-body-sm text-neutral-600 mb-lg">{error}</p>
          <Button
            variant="primary"
            onClick={() => {
              setError(null);
              window.location.reload();
            }}
          >
            重试
          </Button>
        </div>
      </SafeArea>
    );
  }

  return (
    <SafeArea>
      <div className="flex flex-col items-center justify-center h-dvh bg-white">
        {/* Logo */}
        <div
          className="mb-xl"
          style={{
            animation: showBrand ? "scale-in 400ms ease-out both" : undefined,
          }}
        >
          <svg
            width="50"
            height="50"
            viewBox="0 0 50 50"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
          >
            <rect width="50" height="50" rx="12" fill="#1A56DB" />
            <path
              d="M14 28 L22 16 L30 28 L38 16"
              stroke="white"
              strokeWidth="3"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
            <path
              d="M14 34 L38 34"
              stroke="white"
              strokeWidth="3"
              strokeLinecap="round"
            />
          </svg>
        </div>

        {/* 标题 */}
        <h1 className="text-h1 text-neutral-900 mb-sm">应急预案生成系统</h1>
        <p className="text-caption text-neutral-400 mb-xl">
          GB/T 29639-2020 标准合规
        </p>

        {/* 加载指示器 */}
        <div className="flex gap-1.5">
          {[0, 1, 2].map((i) => (
            <span
              key={i}
              className="w-2 h-2 rounded-full bg-primary-600"
              style={{
                animation: `skeleton-pulse 1.2s ease-in-out ${i * 0.15}s infinite`,
              }}
            />
          ))}
        </div>
      </div>
    </SafeArea>
  );
}
