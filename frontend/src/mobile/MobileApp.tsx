import { Suspense } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider } from "react-router-dom";
import { AuthProvider } from "@/contexts/AuthContext";
import { EnterpriseProvider } from "@/contexts/EnterpriseContext";
import { ToastProvider } from "@/mobile/components/ui/Toast";
import { mobileRouter } from "@/mobile/routes";
import Spinner from "@/mobile/components/ui/Spinner";
import "@/mobile/styles/tokens.css";
import "@/mobile/styles/base.css";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      staleTime: 30_000,
      refetchOnWindowFocus: false,
      networkMode: "offlineFirst",
    },
    mutations: {
      networkMode: "offlineFirst",
    },
  },
});

function LoadingFallback() {
  return (
    <div className="flex items-center justify-center h-dvh bg-white">
      <Spinner size="lg" />
    </div>
  );
}

export default function MobileApp() {
  return (
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <AuthProvider>
          <EnterpriseProvider>
            <Suspense fallback={<LoadingFallback />}>
              <RouterProvider router={mobileRouter} />
            </Suspense>
          </EnterpriseProvider>
        </AuthProvider>
      </ToastProvider>
    </QueryClientProvider>
  );
}
