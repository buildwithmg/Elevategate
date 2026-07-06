"use client";

import { useQuery } from "@tanstack/react-query";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { ErrorState } from "@/components/shared/state-views";
import { getMe, logout } from "@/lib/api-client";

export default function SettingsPage() {
  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["me"],
    queryFn: getMe,
  });

  async function handleLogout() {
    await logout();
    window.location.href = "/login";
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Settings</h1>
        <p className="text-sm text-muted-foreground">Your account details.</p>
      </div>

      <Card className="max-w-lg">
        <CardHeader>
          <CardTitle>Account</CardTitle>
          <CardDescription>Signed in to ElevateGate Dashboard.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {isError ? (
            <ErrorState
              message={error instanceof Error ? error.message : "Failed to load your profile."}
              onRetry={() => refetch()}
            />
          ) : isLoading || !data ? (
            <div className="space-y-2">
              <Skeleton className="h-5 w-40" />
              <Skeleton className="h-5 w-56" />
            </div>
          ) : (
            <dl className="space-y-3 text-sm">
              <div className="flex justify-between">
                <dt className="text-muted-foreground">Name</dt>
                <dd className="font-medium">{data.name}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-muted-foreground">Email</dt>
                <dd className="font-medium">{data.email}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-muted-foreground">Role</dt>
                <dd>
                  <Badge variant="outline" className="capitalize">
                    {data.role}
                  </Badge>
                </dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-muted-foreground">Account created</dt>
                <dd className="font-medium">{new Date(data.created_at).toLocaleDateString()}</dd>
              </div>
            </dl>
          )}

          <Button variant="outline" onClick={handleLogout} className="w-full">
            Log out
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
