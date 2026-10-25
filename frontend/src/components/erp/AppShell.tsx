import { useEffect, useMemo, useState, type ReactNode } from "react";
import { Link, useNavigate, useRouterState } from "@tanstack/react-router";
import {
  Activity,
  Bell,
  Boxes,
  ChevronDown,
  ClipboardList,
  FileStack,
  FlaskConical,
  Folders,
  Gauge,
  Info,
  Import,
  KeyRound,
  Layers,
  ListChecks,
  LogOut,
  PackageCheck,
  Receipt,
  Search,
  Settings2,
  ShieldCheck,
  Truck,
  UserCog,
  Warehouse,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { ScrollArea } from "@/components/ui/scroll-area";
import { StatusBadge } from "./StatusBadge";
import { appInfo, footerSignature, poweredByText } from "@/lib/erp/appInfo";
import { BrandLogo } from "@/components/erp/BrandLogo";
import { useSession } from "@/lib/erp/session";
import type { Capability } from "@/lib/erp/rbac";
import {
  customerDeliveries,
  deliveryInstructions,
  materials,
  isBelowThreshold,
  projects,
  purchaseOrders,
  roles,
  simulations,
  users,
} from "@/lib/erp/data";
import { cn } from "@/lib/utils";

interface NavItem {
  label: string;
  to: string;
  icon: typeof Gauge;
  caps: Capability[];
}
interface NavGroup {
  label: string;
  items: NavItem[];
}

const NAV: NavGroup[] = [
  {
    label: "Monitoring",
    items: [
      { label: "Dashboard", to: "/", icon: Gauge, caps: ["dashboard.all", "dashboard.own"] },
      { label: "Projects", to: "/projects", icon: Folders, caps: ["project.view"] },
    ],
  },
  {
    label: "Order intake",
    items: [
      {
        label: "Purchase Orders",
        to: "/purchase-orders",
        icon: ClipboardList,
        caps: ["po.view"],
      },
      { label: "PO Intake", to: "/po-intake", icon: Import, caps: ["po.write"] },
    ],
  },
  {
    label: "Planning",
    items: [
      { label: "Simulations", to: "/simulations", icon: FlaskConical, caps: ["simulation.view"] },
      { label: "Bill of Material", to: "/bom", icon: Layers, caps: ["bom.view"] },
    ],
  },
  {
    label: "Material & warehouse",
    items: [
      { label: "Stock Monitoring", to: "/stock", icon: Boxes, caps: ["stock.monitor"] },
      {
        label: "Supplier Arrivals",
        to: "/stock/supplier-orders",
        icon: Truck,
        caps: ["supplier.order.write", "supplier.arrival.enter", "supplier.arrival.confirm"],
      },
      {
        label: "Stock Reception",
        to: "/stock/reception",
        icon: Warehouse,
        caps: ["stock.reception.write"],
      },
      {
        label: "CutMan Imports",
        to: "/stock/cutman",
        icon: Activity,
        caps: ["stock.cutman.import", "stock.wip.manual"],
      },
      {
        label: "Transit Stock",
        to: "/stock/transit",
        icon: Truck,
        caps: ["stock.transit.write"],
      },
      {
        label: "Stock History",
        to: "/stock/history",
        icon: ListChecks,
        caps: ["stock.history.view"],
      },
    ],
  },
  {
    label: "Delivery",
    items: [
      {
        label: "Warehouse Handover",
        to: "/handover",
        icon: PackageCheck,
        caps: ["handover.instruction.create", "handover.validate"],
      },
      {
        label: "Delivery Code Access",
        to: "/handover/access",
        icon: KeyRound,
        caps: ["handover.code.access"],
      },
      {
        label: "Customer Deliveries",
        to: "/customer-deliveries",
        icon: Truck,
        caps: ["customer.delivery.view"],
      },
    ],
  },
  {
    label: "Finance & records",
    items: [
      { label: "Finance", to: "/finance", icon: Receipt, caps: ["finance.view"] },
      { label: "Documents", to: "/documents", icon: FileStack, caps: ["documents.view"] },
      { label: "Audit Trail", to: "/audit", icon: ShieldCheck, caps: ["audit.view"] },
    ],
  },
  {
    label: "Administration",
    items: [
      { label: "Users & Access", to: "/admin/users", icon: UserCog, caps: ["admin.users"] },
      {
        label: "Reference Lists",
        to: "/admin/reference-lists",
        icon: Settings2,
        caps: ["admin.reference"],
      },
    ],
  },
  {
    label: "System",
    items: [{ label: "System Info", to: "/about", icon: Info, caps: ["system.info"] }],
  },
];

function useAlerts() {
  const { can, projectIds } = useSession();
  return useMemo(() => {
    const list: {
      id: string;
      tone: "danger" | "warn";
      title: string;
      detail: string;
      to: string;
    }[] = [];
    if (can("stock.monitor")) {
      materials.filter(isBelowThreshold).forEach((m) =>
        list.push({
          id: `mat-${m.id}`,
          tone: "danger",
          title: `${m.partNumber} at or below critical threshold`,
          detail: `Practical stock ${m.practicalStock} ${m.unit} · threshold ${m.criticalThreshold} ${m.unit}`,
          to: "/stock",
        }),
      );
    }
    if (can("handover.validate")) {
      deliveryInstructions
        .filter((d) => d.status === "Awaiting validation" && projectIds.includes(d.projectId))
        .forEach((d) =>
          list.push({
            id: `di-${d.id}`,
            tone: "warn",
            title: `${d.ref} awaiting signed-document validation`,
            detail: `Receiver ${d.receiverName ?? "—"} · uploaded by ${d.warehouseTeamLeader ?? "—"}`,
            to: "/handover",
          }),
        );
    }
    if (can("simulation.view")) {
      simulations
        .filter((s) => !s.approved && !s.meetingMinutesDocId && projectIds.includes(s.projectId))
        .forEach((s) =>
          list.push({
            id: `sim-${s.id}`,
            tone: "warn",
            title: `${s.ref} has no meeting minutes (PV)`,
            detail: "Launch cannot be finalised until the PV document is uploaded.",
            to: "/simulations",
          }),
        );
    }
    if (can("customer.delivery.view")) {
      customerDeliveries
        .filter((d) => d.status === "Pending confirmation" && projectIds.includes(d.projectId))
        .forEach((d) =>
          list.push({
            id: `cd-${d.id}`,
            tone: "warn",
            title: `${d.ref} awaiting delivery confirmation`,
            detail: `${d.fgpn} · ${d.quantity} pcs · ${d.deliveryMethod}`,
            to: "/customer-deliveries",
          }),
        );
    }
    return list;
  }, [can, projectIds]);
}

function ProjectSelector() {
  const { projectIds, activeProjectId, setActiveProjectId } = useSession();
  if (projectIds.length === 0) return null;
  const active = projects.find((p) => p.id === activeProjectId);
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="outline" size="sm" className="h-8 gap-2 text-xs">
          <Folders className="size-3.5" />
          {active ? `${active.code} · ${active.name}` : "All assigned projects"}
          <ChevronDown className="size-3.5 opacity-60" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" className="w-72">
        <DropdownMenuLabel className="text-xs">Project scope</DropdownMenuLabel>
        <DropdownMenuRadioGroup
          value={activeProjectId ?? "__all"}
          onValueChange={(v) => setActiveProjectId(v === "__all" ? null : v)}
        >
          <DropdownMenuRadioItem value="__all" className="text-xs">
            All projects visible to me
          </DropdownMenuRadioItem>
          {projects
            .filter((p) => projectIds.includes(p.id))
            .map((p) => (
              <DropdownMenuRadioItem key={p.id} value={p.id} className="text-xs">
                {p.code} · {p.name}
              </DropdownMenuRadioItem>
            ))}
        </DropdownMenuRadioGroup>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

function GlobalSearch() {
  const [open, setOpen] = useState(false);
  const navigate = useNavigate();
  const { projectIds, can } = useSession();

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "k" && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        setOpen((o) => !o);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const go = (to: string) => {
    setOpen(false);
    void navigate({ to });
  };

  return (
    <>
      <button
        onClick={() => setOpen(true)}
        className="flex h-8 w-56 items-center gap-2 rounded-md border border-border bg-background px-2.5 text-xs text-muted-foreground transition-colors hover:bg-muted lg:w-72"
      >
        <Search className="size-3.5" />
        Search materials, POs, projects…
        <kbd className="ml-auto rounded border border-border bg-muted px-1 text-[10px]">⌘K</kbd>
      </button>
      <CommandDialog open={open} onOpenChange={setOpen}>
        <CommandInput placeholder="Type at least 3 characters — part number, description, PO number…" />
        <CommandList>
          <CommandEmpty>No results found.</CommandEmpty>
          {can("stock.search") && (
            <CommandGroup heading="Materials">
              {materials.map((m) => (
                <CommandItem
                  key={m.id}
                  value={`${m.partNumber} ${m.description}`}
                  onSelect={() => go("/stock")}
                >
                  <Boxes className="size-3.5" />
                  <span className="num">{m.partNumber}</span>
                  <span className="truncate text-xs text-muted-foreground">{m.description}</span>
                </CommandItem>
              ))}
            </CommandGroup>
          )}
          {can("po.view") && (
            <CommandGroup heading="Purchase orders">
              {purchaseOrders
                .filter((p) => projectIds.includes(p.projectId))
                .map((p) => (
                  <CommandItem
                    key={p.id}
                    value={`${p.poNumber} ${p.jitCustomer}`}
                    onSelect={() => go(`/purchase-orders/${p.id}`)}
                  >
                    <ClipboardList className="size-3.5" />
                    <span className="num">{p.poNumber}</span>
                    <span className="truncate text-xs text-muted-foreground">
                      {p.jitCustomer} · {p.status}
                    </span>
                  </CommandItem>
                ))}
            </CommandGroup>
          )}
          {can("project.view") && (
            <CommandGroup heading="Projects">
              {projects
                .filter((p) => projectIds.includes(p.id))
                .map((p) => (
                  <CommandItem
                    key={p.id}
                    value={`${p.code} ${p.name}`}
                    onSelect={() => go(`/projects/${p.id}`)}
                  >
                    <Folders className="size-3.5" />
                    <span className="num">{p.code}</span>
                    <span className="truncate text-xs text-muted-foreground">{p.name}</span>
                  </CommandItem>
                ))}
            </CommandGroup>
          )}
        </CommandList>
      </CommandDialog>
    </>
  );
}

function NotificationBell() {
  const alerts = useAlerts();
  const navigate = useNavigate();
  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button variant="ghost" size="sm" className="relative h-8 px-2">
          <Bell className="size-4" />
          {alerts.length > 0 && (
            <span className="absolute right-0.5 top-0.5 flex size-4 items-center justify-center rounded-full bg-danger text-[10px] font-bold text-danger-foreground">
              {alerts.length}
            </span>
          )}
        </Button>
      </PopoverTrigger>
      <PopoverContent align="end" className="w-96 p-0">
        <div className="border-b border-border px-3 py-2">
          <p className="text-sm font-semibold">Action required</p>
          <p className="text-xs text-muted-foreground">
            Exceptions in your scope, newest operational impact first.
          </p>
        </div>
        <ScrollArea className="max-h-80">
          {alerts.length === 0 ? (
            <p className="px-3 py-6 text-center text-xs text-muted-foreground">
              Nothing requires your attention.
            </p>
          ) : (
            alerts.map((a) => (
              <button
                key={a.id}
                onClick={() => void navigate({ to: a.to })}
                className="flex w-full flex-col items-start gap-0.5 border-b border-border px-3 py-2 text-left last:border-0 hover:bg-muted"
              >
                <div className="flex items-center gap-2">
                  <StatusBadge tone={a.tone} dot>
                    {a.tone === "danger" ? "Critical" : "Pending"}
                  </StatusBadge>
                  <span className="text-xs font-medium text-foreground">{a.title}</span>
                </div>
                <span className="text-xs text-muted-foreground">{a.detail}</span>
              </button>
            ))
          )}
        </ScrollArea>
      </PopoverContent>
    </Popover>
  );
}

function UserMenu() {
  const { user, setUserId } = useSession();
  const roleName = roles.find((r) => r.id === user.role)?.name ?? user.role;
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="sm" className="h-8 gap-2 px-2">
          <span className="flex size-6 items-center justify-center rounded-sm bg-primary text-[10px] font-bold text-primary-foreground">
            {user.fullName
              .split(" ")
              .map((n) => n[0])
              .join("")}
          </span>
          <span className="hidden text-left leading-tight sm:block">
            <span className="block text-xs font-semibold">{user.fullName}</span>
            <span className="block text-[10px] text-muted-foreground">{roleName}</span>
          </span>
          <ChevronDown className="size-3.5 opacity-60" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-64">
        <DropdownMenuLabel className="text-xs">
          Signed in as {user.username}
          <span className="mt-0.5 block font-normal text-muted-foreground">{roleName}</span>
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuLabel className="text-[11px] font-normal text-muted-foreground">
          Prototype: switch session role to inspect permission boundaries
        </DropdownMenuLabel>
        <DropdownMenuLabel className="text-[11px] font-normal text-muted-foreground">
          {poweredByText}
        </DropdownMenuLabel>
        <DropdownMenuRadioGroup value={user.id} onValueChange={setUserId}>
          {users
            .filter((u) => u.active && !u.locked)
            .map((u) => (
              <DropdownMenuRadioItem key={u.id} value={u.id} className="text-xs">
                {u.fullName}
                <span className="ml-1 text-muted-foreground">
                  — {roles.find((r) => r.id === u.role)?.name}
                </span>
              </DropdownMenuRadioItem>
            ))}
        </DropdownMenuRadioGroup>
        <DropdownMenuSeparator />
        <DropdownMenuItem asChild className="text-xs">
          <Link to="/login">
            <LogOut className="size-3.5" /> Sign out
          </Link>
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  const { can, user } = useSession();
  const pathname = useRouterState({ select: (s) => s.location.pathname });
  const roleName = roles.find((r) => r.id === user.role)?.name ?? "";

  if (pathname === "/login") {
    return <main className="min-h-screen bg-background">{children}</main>;
  }

  const groups = NAV.map((g) => ({
    ...g,
    items: g.items.filter((i) => i.caps.some((c) => can(c))),
  })).filter((g) => g.items.length > 0);

  return (
    <div className="flex min-h-screen bg-background">
      <aside className="sticky top-0 hidden h-screen w-60 shrink-0 flex-col border-r border-sidebar-border bg-sidebar text-sidebar-foreground lg:flex">
        <div className="space-y-1 border-b border-sidebar-border px-4 py-3">
          <BrandLogo inverse className="h-[50px] w-[125px]" />
          <div className="leading-tight">
            <p className="text-sm font-semibold text-sidebar-accent-foreground">
              {appInfo.productName}
            </p>
            <p className="text-[10px] text-sidebar-foreground/70">{appInfo.productTagline}</p>
          </div>
        </div>
        <ScrollArea className="flex-1">
          <nav className="px-2 py-3">
            {groups.map((g) => (
              <div key={g.label} className="mb-4">
                <p className="px-2 pb-1 text-[10px] font-semibold uppercase tracking-wider text-sidebar-foreground/50">
                  {g.label}
                </p>
                {g.items.map((item) => {
                  const active = item.to === "/" ? pathname === "/" : pathname.startsWith(item.to);
                  const Icon = item.icon;
                  return (
                    <Link
                      key={item.to}
                      to={item.to}
                      className={cn(
                        "mb-0.5 flex items-center gap-2 rounded-sm px-2 py-1.5 text-[13px] transition-colors",
                        active
                          ? "bg-sidebar-accent font-semibold text-sidebar-accent-foreground"
                          : "text-sidebar-foreground/85 hover:bg-sidebar-accent/60 hover:text-sidebar-accent-foreground",
                      )}
                    >
                      <Icon className="size-4 shrink-0 opacity-80" />
                      <span className="truncate">{item.label}</span>
                    </Link>
                  );
                })}
              </div>
            ))}
          </nav>
        </ScrollArea>
        <div className="space-y-1 border-t border-sidebar-border px-3 py-2 text-[10px] text-sidebar-foreground/60">
          <p>Session role: {roleName}</p>
          <p>{footerSignature}</p>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-30 flex flex-wrap items-center gap-2 border-b border-border bg-card px-4 py-2">
          <span className="flex items-center gap-2 lg:hidden">
            <BrandLogo className="h-8 w-20" />
            <span className="text-sm font-semibold">{appInfo.productName}</span>
          </span>
          <ProjectSelector />
          <div className="ml-auto flex items-center gap-2">
            <GlobalSearch />
            <NotificationBell />
            <UserMenu />
          </div>
        </header>
        <main className="min-w-0 flex-1">{children}</main>
        <footer className="border-t border-border bg-card px-4 py-2 text-center text-[11px] text-muted-foreground">
          {footerSignature}
        </footer>
      </div>
    </div>
  );
}
