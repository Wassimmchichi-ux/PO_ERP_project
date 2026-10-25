import { createFileRoute } from "@tanstack/react-router";
import { Info, ShieldCheck } from "lucide-react";
import { PageHeader, Section, KeyValue } from "@/components/erp/PageHeader";
import { StatusBadge } from "@/components/erp/StatusBadge";
import { appInfo, pageTitle } from "@/lib/erp/appInfo";

export const Route = createFileRoute("/about")({
  head: () => ({
    meta: [
      { title: pageTitle("System Information") },
      {
        name: "description",
        content: "System information for the configurable ERP prototype.",
      },
      { property: "og:title", content: pageTitle("System Information") },
    ],
  }),
  component: AboutPage,
});

function AboutPage() {
  return (
    <>
      <PageHeader
        title="System information"
        subtitle={`${appInfo.productName} deployment profile`}
        crumbs={[{ label: "System" }, { label: "System information" }]}
        meta={<StatusBadge tone="info">Prototype</StatusBadge>}
      />

      <div className="grid gap-4 p-4 lg:grid-cols-2">
        <Section
          title="Application"
          description="Central product and client identity for this ERP installation."
        >
          <KeyValue
            columns={2}
            items={[
              { label: "Product name", value: appInfo.productName },
              { label: "Version", value: appInfo.version },
              { label: "Developed by", value: appInfo.companyName },
              { label: "Client/company", value: appInfo.clientName },
            ]}
          />
        </Section>

        <Section title="Governance" description="Authorization and business-rule baseline.">
          <div className="grid gap-3 p-4">
            <div className="flex items-center gap-3 rounded-md border border-border bg-muted/20 p-3">
              <div className="grid size-8 place-items-center rounded-sm bg-info-soft text-info">
                <ShieldCheck className="size-4" />
              </div>
              <div className="min-w-0">
                <p className="text-sm font-semibold text-foreground">RBAC + policy rules</p>
                <p className="text-xs text-muted-foreground">
                  Core authorization is centralized for reuse across ERP clients.
                </p>
              </div>
            </div>
            <div className="flex items-center gap-3 rounded-md border border-border bg-muted/20 p-3">
              <div className="grid size-8 place-items-center rounded-sm bg-muted text-muted-foreground">
                <Info className="size-4" />
              </div>
              <div className="min-w-0">
                <p className="text-sm font-semibold text-foreground">{appInfo.productTagline}</p>
                <p className="text-xs text-muted-foreground">
                  Client-specific behavior should live in configuration or policy modules.
                </p>
              </div>
            </div>
          </div>
        </Section>
      </div>
    </>
  );
}
