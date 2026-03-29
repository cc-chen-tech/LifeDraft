"use client"

import * as React from "react"

import { cn } from "@/lib/utils"

interface SliderProps {
  value: number[]
  max?: number
  step?: number
  onValueChange?: (value: number[]) => void
  className?: string
}

export function Slider({
  value,
  max = 100,
  step = 1,
  onValueChange,
  className,
}: SliderProps) {
  const percentage = ((value[0] || 0) / max) * 100

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const newValue = parseFloat(e.target.value)
    onValueChange?.([newValue])
  }

  return (
    <div className={cn("relative flex w-full touch-none select-none items-center", className)}>
      <div className="relative h-1.5 w-full grow overflow-hidden rounded-full bg-primary/20">
        <div
          className="absolute h-full bg-primary"
          style={{ width: `${percentage}%` }}
        />
      </div>
      <input
        type="range"
        min={0}
        max={max}
        step={step}
        value={value[0] || 0}
        onChange={handleChange}
        className="absolute w-full h-1.5 opacity-0 cursor-pointer"
        style={{ top: "50%", transform: "translateY(-50%)" }}
      />
      <div
        className="absolute block h-4 w-4 rounded-full border-2 border-primary bg-background shadow transition-colors"
        style={{ left: `calc(${percentage}% - 8px)` }}
      />
    </div>
  )
}


