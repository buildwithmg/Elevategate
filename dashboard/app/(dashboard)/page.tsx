import { RecentRequests } from "@/components/dashboard/recent-requests";
import { SummaryCards } from "@/components/dashboard/summary-cards";

export default function DashboardPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Dashboard</h1>
        <p className="text-sm text-muted-foreground">
          Overview of elevation requests and enrolled devices.
        </p>
      </div>
      <SummaryCards />
      <RecentRequests />
    </div>
  );
}
