"use client";

import type { AdminStats } from "@wearx/api-types";
import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

import { Login } from "@/components/Login";
import { useAuth } from "@/lib/auth";
import { useStaffQuery } from "@/lib/queries";

const NAV: ReadonlyArray<{ href: string; label: string; admin?: boolean }> = [
  { href: "/", label: "Panoramica" },
  { href: "/queue", label: "Coda" },
  { href: "/appeals", label: "Reclami" },
  { href: "/users", label: "Persone" },
  { href: "/domains", label: "Domini bloccati" },
  { href: "/votes", label: "Voti sospetti" },
  { href: "/feedback", label: "Feedback" },
  { href: "/styles", label: "Stili", admin: true },
  { href: "/staff", label: "Staff", admin: true },
  { href: "/audit", label: "Registro", admin: true },
];

export function Shell({ children }: { children: ReactNode }) {
  const { status, me, signOut } = useAuth();
  const pathname = usePathname();
  const stats = useStaffQuery<AdminStats>(status === "ready" ? "/v1/admin/stats" : null, { refetchInterval: 60_000 });

  if (status !== "ready" || !me) return <Login />;

  const open = stats.data ? stats.data.reports.p0 + stats.data.reports.p1 + stats.data.reports.p2 : 0;
  const counts: Record<string, { value: number; danger: boolean } | undefined> = {
    "/queue": open ? { value: open, danger: (stats.data?.reports.p0 ?? 0) > 0 || (stats.data?.reports.overdue ?? 0) > 0 } : undefined,
    "/appeals": stats.data?.appeals_open ? { value: stats.data.appeals_open, danger: false } : undefined,
  };

  return (
    <div className="shell">
      <nav className="side" aria-label="Sezioni">
        <div className="logo">
          WEAR<b>X</b>
        </div>
        <div className="side-kicker">STAFF · {me.role === "admin" ? "AMMINISTRATORE" : "MODERATORE"}</div>
        {NAV.filter((item) => !item.admin || me.role === "admin").map((item) => {
          const active = item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
          const count = counts[item.href];
          return (
            <Link key={item.href} href={item.href} className="nav" aria-current={active ? "page" : undefined}>
              {item.label}
              {count ? <span className={`count${count.danger ? " danger" : ""}`}>{count.value}</span> : null}
            </Link>
          );
        })}
        <div className="side-foot">
          <span>@{me.nickname ?? "staff"}</span>
          <button className="btn" type="button" onClick={() => void signOut()}>
            Esci
          </button>
        </div>
      </nav>
      <main className="main">{children}</main>
    </div>
  );
}
