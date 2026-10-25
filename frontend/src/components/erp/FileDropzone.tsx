import { useRef, useState } from "react";
import { UploadCloud, FileCheck2 } from "lucide-react";
import { toast } from "sonner";
import { cn } from "@/lib/utils";

/**
 * Upload zone with client-side format enforcement.
 * SRS: PO intake accepts PDF only (M02-FR-01), BOM .xlsx (M06-FR-01),
 * CutMan .xlsx or .sql (M07-FR-13), signed documents PDF (M08-FR-13).
 */
export function FileDropzone({
  accept,
  label,
  hint,
  rejectMessage,
  onAccepted,
  onFileAccepted,
  disabled,
}: {
  accept: string[];
  label: string;
  hint?: string;
  rejectMessage?: string;
  onAccepted?: (fileName: string) => void;
  onFileAccepted?: (file: File) => void;
  disabled?: boolean;
}) {
  const [over, setOver] = useState(false);
  const [accepted, setAccepted] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  function handle(file: File) {
    const ok = accept.some((ext) => file.name.toLowerCase().endsWith(ext));
    if (!ok) {
      toast.error(rejectMessage ?? `Only ${accept.join(", ")} files are accepted.`);
      return;
    }
    setAccepted(file.name);
    onAccepted?.(file.name);
    onFileAccepted?.(file);
    toast.success(`${file.name} accepted for processing.`);
  }

  return (
    <div
      onDragOver={(e) => {
        e.preventDefault();
        if (!disabled) setOver(true);
      }}
      onDragLeave={() => setOver(false)}
      onDrop={(e) => {
        e.preventDefault();
        setOver(false);
        if (disabled) return;
        const f = e.dataTransfer.files?.[0];
        if (f) handle(f);
      }}
      onClick={() => !disabled && inputRef.current?.click()}
      className={cn(
        "flex cursor-pointer flex-col items-center justify-center rounded-md border border-dashed px-4 py-7 text-center transition-colors",
        over ? "border-accent bg-accent/10" : "border-border bg-muted/40 hover:bg-muted",
        disabled && "pointer-events-none opacity-50",
      )}
    >
      <input
        ref={inputRef}
        type="file"
        className="hidden"
        accept={accept.join(",")}
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f) handle(f);
        }}
      />
      {accepted ? (
        <FileCheck2 className="mb-2 size-5 text-ok" />
      ) : (
        <UploadCloud className="mb-2 size-5 text-muted-foreground" />
      )}
      <p className="text-sm font-medium text-foreground">{accepted ?? label}</p>
      <p className="mt-1 text-xs text-muted-foreground">
        {hint ?? `Accepted formats: ${accept.join(", ")}`}
      </p>
    </div>
  );
}
