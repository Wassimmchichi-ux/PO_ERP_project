import { appInfo } from "@/lib/erp/appInfo";
import { cn } from "@/lib/utils";

export function BrandLogo({
  inverse = false,
  className,
}: {
  inverse?: boolean;
  className?: string;
}) {
  return (
    <img
      src={inverse ? appInfo.logoInverseSrc : appInfo.logoSrc}
      alt="Adient"
      width={125}
      height={50}
      className={cn("h-10 w-[100px] shrink-0 object-contain", className)}
    />
  );
}
