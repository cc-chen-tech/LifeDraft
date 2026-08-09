import React from "react"
import { render, screen } from "@testing-library/react"
import { readFileSync } from "node:fs"
import { resolve } from "node:path"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { NarrativeLoadingState } from "@/components/narrative-loading/NarrativeLoadingState"

describe("Story101 visual foundation primitives", () => {
  it("gives every control the explicit 6px radius token and interactive idle boundary", () => {
    render(
      <>
        <Button variant="chrome">Chrome</Button>
        <Button variant="floating">Floating</Button>
        <Button variant="outline">Outline</Button>
        <Button variant="narrative">Narrative</Button>
        <Input aria-label="Default input" />
        <Input aria-label="Underline input" surface="underline" />
        <Textarea aria-label="Default textarea" />
        <Textarea aria-label="Underline textarea" surface="underline" />
      </>
    )

    for (const control of screen.getAllByRole("button")) {
      expect(control).toHaveClass("rounded-[var(--radius-control)]")
    }
    for (const control of screen.getAllByRole("textbox")) {
      expect(control).toHaveClass("rounded-[var(--radius-control)]")
    }

    for (const name of ["Chrome", "Floating", "Outline", "Narrative"]) {
      expect(screen.getByRole("button", { name })).toHaveClass(
        "border-[var(--border-interactive)]"
      )
    }
    expect(screen.getByRole("textbox", { name: "Default input" })).toHaveClass(
      "border-input"
    )
    expect(screen.getByRole("textbox", { name: "Underline input" })).toHaveClass(
      "border-b-[var(--border-interactive)]"
    )
    expect(screen.getByRole("textbox", { name: "Default textarea" })).toHaveClass(
      "border-input"
    )
    expect(screen.getByRole("textbox", { name: "Underline textarea" })).toHaveClass(
      "border-b-[var(--border-interactive)]"
    )

    const stylesheet = readFileSync(resolve(process.cwd(), "src/app/globals.css"), "utf8")
    expect(stylesheet).toMatch(/--input:\s*var\(--border-interactive\)/)
  })

  it("self-hosts only the basic Latin Spline Sans variable face", () => {
    const stylesheet = readFileSync(resolve(process.cwd(), "src/app/globals.css"), "utf8")

    expect(stylesheet).not.toContain('@import "@fontsource-variable/spline-sans/wght.css"')
    expect(stylesheet).toContain("@font-face")
    expect(stylesheet).toContain("spline-sans-latin-wght-normal.woff2")
    expect(stylesheet).toContain("U+0000-00FF")
    expect(stylesheet).not.toContain("latin-ext")
  })

  it("ships the exact Spline Sans OFL alongside the public frontend", () => {
    const publicLicense = readFileSync(
      resolve(process.cwd(), "public/licenses/SplineSans-OFL.txt"),
      "utf8"
    )
    const packageLicense = readFileSync(
      resolve(process.cwd(), "node_modules/@fontsource-variable/spline-sans/LICENSE"),
      "utf8"
    )

    expect(publicLicense).toBe(packageLicense)
    expect(publicLicense).toContain("Copyright 2021 The Spline Sans Project Authors")
    expect(publicLicense).toContain("SIL OPEN FONT LICENSE Version 1.1")
  })

  it("routes touch button sizes to the native button", () => {
    render(
      <>
        <Button size="touch">Continue</Button>
        <Button size="icon-touch" aria-label="Open menu">Menu</Button>
      </>
    )

    expect(screen.getByRole("button", { name: "Continue" })).toHaveAttribute(
      "data-size",
      "touch"
    )
    expect(screen.getByRole("button", { name: "Open menu" })).toHaveAttribute(
      "data-size",
      "icon-touch"
    )
  })

  it.each(["chrome", "quiet", "narrative", "floating"] as const)(
    "routes the %s button variant",
    (variant) => {
      render(<Button variant={variant}>Continue</Button>)

      expect(screen.getByRole("button", { name: "Continue" })).toHaveAttribute(
        "data-variant",
        variant
      )
    }
  )

  it("keeps input semantics while routing its visual controls", () => {
    render(
      <label>
        Character name
        <Input
          type="text"
          defaultValue="Li Bai"
          surface="filled"
          controlSize="touch"
        />
      </label>
    )

    const input = screen.getByRole("textbox", { name: "Character name" })
    expect(input).toHaveValue("Li Bai")
    expect(input).toHaveAttribute("data-surface", "filled")
    expect(input).toHaveAttribute("data-control-size", "touch")
  })

  it("keeps textarea semantics while routing its visual controls", () => {
    render(
      <label>
        Story notes
        <Textarea
          defaultValue="A letter waits by the door."
          surface="underline"
          controlSize="touch"
        />
      </label>
    )

    const textarea = screen.getByRole("textbox", { name: "Story notes" })
    expect(textarea).toHaveValue("A letter waits by the door.")
    expect(textarea).toHaveAttribute("data-surface", "underline")
    expect(textarea).toHaveAttribute("data-control-size", "touch")
  })

  it("lets selected input surfaces own the background in the always-dark root", () => {
    render(
      <>
        <Input aria-label="Filled input" surface="filled" />
        <Input aria-label="Underline input" surface="underline" />
        <Textarea aria-label="Filled textarea" surface="filled" />
        <Textarea aria-label="Underline textarea" surface="underline" />
      </>
    )

    const filledControls = [
      screen.getByRole("textbox", { name: "Filled input" }),
      screen.getByRole("textbox", { name: "Filled textarea" }),
    ]
    const underlineControls = [
      screen.getByRole("textbox", { name: "Underline input" }),
      screen.getByRole("textbox", { name: "Underline textarea" }),
    ]

    for (const control of filledControls) {
      expect(control).toHaveClass("bg-[var(--surface-raised)]")
      expect(control).not.toHaveClass("dark:bg-input/30")
    }
    for (const control of underlineControls) {
      expect(control).toHaveClass("bg-transparent")
      expect(control).not.toHaveClass("dark:bg-input/30")
    }
  })

  it("renders delayed narrative copy with the warning foreground token", () => {
    const style = document.createElement("style")
    style.textContent = readFileSync(resolve(process.cwd(), "src/app/globals.css"), "utf8")
    document.head.appendChild(style)

    try {
      render(<NarrativeLoadingState context="gameplay" layout="section" delayed />)

      const delayedCopy = screen.getByText("这一页仍在继续写作")
      expect(getComputedStyle(delayedCopy).color).toBe("var(--warning-foreground)")
      expect(
        getComputedStyle(document.documentElement)
          .getPropertyValue("--warning-foreground")
          .trim()
      ).toBe("#C2A26E")
    } finally {
      style.remove()
    }
  })

  it.each(["success", "warning", "danger", "info"] as const)(
    "renders readable badge text for the %s semantic state",
    (variant) => {
      render(<Badge variant={variant}>Story saved</Badge>)

      const badge = screen.getByText("Story saved")
      expect(badge).toHaveAttribute("data-variant", variant)
      expect(badge).toHaveTextContent("Story saved")
    }
  )
})
