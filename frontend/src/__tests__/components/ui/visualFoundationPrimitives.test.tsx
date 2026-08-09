import React from "react"
import { render, screen } from "@testing-library/react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"

describe("Story101 visual foundation primitives", () => {
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
