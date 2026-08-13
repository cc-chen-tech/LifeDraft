"use client";

import { Loader2, X } from "lucide-react";

import { FormField } from "@/components/story101";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { LengthIndicator } from "@/components/ui/length-indicator";
import {
  Sheet,
  SheetClose,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import type { PresetSaveStatus } from "@/hooks/useCharacterCreation";
import { isWithinInputLimit } from "@/lib/inputLimits";
import { INPUT_LIMITS } from "@/types/input-limits.generated";

import { PresetSaveInlineStatus } from "./PresetSaveInlineStatus";

interface PresetSaveSheetProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  presetName: string;
  onPresetNameChange: (name: string) => void;
  isSaving: boolean;
  status: PresetSaveStatus;
  message: string;
  onSave: () => Promise<void>;
}

export function PresetSaveSheet({
  open,
  onOpenChange,
  presetName,
  onPresetNameChange,
  isSaving,
  status,
  message,
  onSave,
}: PresetSaveSheetProps) {
  const isOverLimit = !isWithinInputLimit(presetName, INPUT_LIMITS.name);
  const isDisabled = !presetName.trim() || isSaving || isOverLimit;

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent
        side="bottom"
        showCloseButton={false}
        className="border-[var(--border-default)] bg-[var(--surface-overlay)] px-4 pb-[max(1.5rem,env(safe-area-inset-bottom))] pt-2 sm:px-6"
      >
        <div
          data-slot="preset-save-sheet"
          className="mx-auto w-full max-w-xl"
        >
          <SheetClose asChild>
            <Button
              type="button"
              variant="quiet"
              size="icon-touch"
              className="absolute right-2 top-2 sm:right-4 sm:top-4"
              aria-label="关闭保存预设"
            >
              <X />
            </Button>
          </SheetClose>
          <SheetHeader className="px-0 pb-5 pt-3 text-left">
            <SheetTitle className="text-lg text-[var(--text-primary)]">
              保存角色预设
            </SheetTitle>
            <SheetDescription className="text-[var(--text-secondary)]">
              为这份角色设定命名，之后可以直接再次使用。
            </SheetDescription>
          </SheetHeader>

          <div className="grid gap-5">
            <FormField
              id="preset-name"
              label="预设名称"
              description="最多 50 字。"
              error={isOverLimit ? `预设名称不能超过 ${INPUT_LIMITS.name} 字` : undefined}
              required
            >
              {({ describedBy, invalid, required }) => (
                <>
                  <Input
                    id="preset-name"
                    value={presetName}
                    onChange={(event) => onPresetNameChange(event.target.value)}
                    placeholder="例如：林见微的城市人生"
                    surface="underline"
                    controlSize="touch"
                    aria-describedby={[describedBy, "preset-name-count"].filter(Boolean).join(" ")}
                    aria-invalid={invalid}
                    required={required}
                    autoFocus
                  />
                  <LengthIndicator
                    id="preset-name-count"
                    value={presetName}
                    limit={INPUT_LIMITS.name}
                    announce={false}
                  />
                </>
              )}
            </FormField>

            <PresetSaveInlineStatus status={status} message={message} />

            <Button
              type="button"
              size="touch"
              className="w-full"
              disabled={isDisabled}
              aria-busy={isSaving}
              onClick={onSave}
            >
              {isSaving && <Loader2 className="animate-spin" />}
              确认保存
            </Button>
          </div>
        </div>
      </SheetContent>
    </Sheet>
  );
}
