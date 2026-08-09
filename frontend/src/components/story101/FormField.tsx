import * as React from "react";

import { cn } from "@/lib/utils";

export interface FormFieldRenderProps {
  describedBy: string | undefined;
  invalid: boolean;
  required: boolean;
}

export interface FormFieldProps {
  id: string;
  label: React.ReactNode;
  description?: React.ReactNode;
  error?: React.ReactNode;
  required?: boolean;
  children: (props: FormFieldRenderProps) => React.ReactNode;
  className?: string;
}

export function FormField({
  id,
  label,
  description,
  error,
  required = false,
  children,
  className,
}: FormFieldProps) {
  const descriptionId = description ? `${id}-description` : undefined;
  const errorId = error ? `${id}-error` : undefined;
  const describedBy = [descriptionId, errorId].filter(Boolean).join(" ") || undefined;
  const invalid = Boolean(error);

  return (
    <div className={cn("grid gap-2", className)} data-slot="form-field">
      <label className="text-sm font-medium text-[var(--text-primary)]" htmlFor={id}>
        {label}
        {required && <span aria-hidden="true"> *</span>}
      </label>
      {children({ describedBy, invalid, required })}
      {description && (
        <p className="text-xs text-[var(--text-secondary)]" id={descriptionId}>
          {description}
        </p>
      )}
      {error && (
        <p className="text-xs text-[var(--danger-foreground)]" id={errorId}>
          {error}
        </p>
      )}
    </div>
  );
}
