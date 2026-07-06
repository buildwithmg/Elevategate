import { Header } from "@/components/layout/header";
import { Sidebar } from "@/components/layout/sidebar";
import { PendingRequestsProvider } from "@/lib/pending-requests-context";

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return (
    <PendingRequestsProvider>
      <div className="flex h-screen w-full overflow-hidden">
        <Sidebar />
        <div className="flex min-w-0 flex-1 flex-col">
          <Header />
          <main className="flex-1 overflow-y-auto overflow-x-auto p-6">{children}</main>
        </div>
      </div>
    </PendingRequestsProvider>
  );
}
