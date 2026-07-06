"use client";

import { useQuery } from "@tanstack/react-query";
import { LogOut } from "lucide-react";

import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { getMe, logout } from "@/lib/api-client";

function initialsFor(name: string | undefined): string {
  if (!name) return "?";
  return name
    .split(" ")
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase())
    .join("");
}

export function Header() {
  const { data: me } = useQuery({ queryKey: ["me"], queryFn: getMe });

  async function handleLogout() {
    await logout();
    window.location.href = "/login";
  }

  return (
    <header className="flex h-16 shrink-0 items-center justify-end border-b bg-background px-6">
      <DropdownMenu>
        <DropdownMenuTrigger
          render={
            <Button variant="ghost" className="flex items-center gap-2 px-2">
              <Avatar className="h-7 w-7">
                <AvatarFallback className="text-xs">{initialsFor(me?.name)}</AvatarFallback>
              </Avatar>
              <span className="hidden text-sm font-medium sm:inline">{me?.name ?? "…"}</span>
            </Button>
          }
        />
        <DropdownMenuContent align="end" className="w-56">
          <DropdownMenuLabel>
            <p className="text-sm font-medium">{me?.name}</p>
            <p className="text-xs font-normal text-muted-foreground">{me?.email}</p>
          </DropdownMenuLabel>
          <DropdownMenuSeparator />
          <DropdownMenuItem onClick={handleLogout}>
            <LogOut className="mr-2 h-4 w-4" /> Log out
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    </header>
  );
}
