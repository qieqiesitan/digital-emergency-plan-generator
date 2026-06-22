import { Navigate } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";
import Spinner from "@/mobile/components/ui/Spinner";

export function AuthGuard({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isLoading } = useAuth();

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-dvh bg-white">
        <Spinner size="lg" />
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/m/login" replace />;
  }

  return <>{children}</>;
}
