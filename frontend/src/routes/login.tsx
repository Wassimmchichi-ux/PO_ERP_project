import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useState } from "react";
import { LogIn, ShieldCheck } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { StatusBadge } from "@/components/erp/StatusBadge";
import { appInfo, footerSignature, pageTitle, poweredByText } from "@/lib/erp/appInfo";
import { roles, users } from "@/lib/erp/data";
import { useSession } from "@/lib/erp/session";
import { BrandLogo } from "@/components/erp/BrandLogo";

export const Route = createFileRoute("/login")({
  head: () => ({
    meta: [
      { title: pageTitle("Login") },
      {
        name: "description",
        content: `${appInfo.productName} prototype access.`,
      },
      { property: "og:title", content: pageTitle("Login") },
    ],
  }),
  component: LoginPage,
});

function LoginPage() {
  const navigate = useNavigate();
  const { user, setUserId } = useSession();
  const [selectedUserId, setSelectedUserId] = useState(user.id);
  const selectedUser = users.find((item) => item.id === selectedUserId) ?? user;
  const roleName = roles.find((role) => role.id === selectedUser.role)?.name ?? selectedUser.role;

  return (
    <div className="grid min-h-screen place-items-center px-4 py-10">
      <div className="w-full max-w-sm rounded-md border border-border bg-card shadow-sm">
        <div className="border-b border-border px-5 py-4">
          <div className="flex items-center gap-3">
            <BrandLogo />
            <div className="min-w-0">
              <h1 className="truncate text-base font-semibold text-foreground">
                {appInfo.productName}
              </h1>
              <p className="text-xs text-muted-foreground">{appInfo.clientName}</p>
            </div>
          </div>
        </div>

        <div className="grid gap-4 p-5">
          <div className="flex items-center justify-between gap-3">
            <div>
              <p className="text-sm font-semibold text-foreground">Prototype login</p>
              <p className="text-xs text-muted-foreground">{poweredByText}</p>
            </div>
            <StatusBadge tone="info">Academic</StatusBadge>
          </div>

          <div className="grid gap-1.5">
            <label className="label-caps" htmlFor="prototype-user">
              Session user
            </label>
            <Select value={selectedUserId} onValueChange={setSelectedUserId}>
              <SelectTrigger id="prototype-user" className="h-9 text-xs">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {users
                  .filter((item) => item.active && !item.locked)
                  .map((item) => (
                    <SelectItem key={item.id} value={item.id}>
                      {item.fullName} - {roles.find((role) => role.id === item.role)?.name}
                    </SelectItem>
                  ))}
              </SelectContent>
            </Select>
          </div>

          <div className="rounded-md border border-border bg-muted/30 p-3 text-xs">
            <div className="flex items-center gap-2">
              <ShieldCheck className="size-4 text-info" />
              <span className="font-medium text-foreground">{roleName}</span>
            </div>
            <p className="mt-1 text-muted-foreground">{selectedUser.username}</p>
          </div>

          <Button
            className="h-9 w-full"
            onClick={() => {
              setUserId(selectedUserId);
              void navigate({ to: "/" });
            }}
          >
            <LogIn className="size-4" /> Continue
          </Button>
        </div>

        <div className="border-t border-border px-5 py-3 text-center text-[11px] text-muted-foreground">
          {footerSignature}
        </div>
      </div>
    </div>
  );
}
