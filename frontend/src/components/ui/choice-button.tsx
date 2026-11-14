import * as React from "react"
import { cn } from "cn"

import { Button } from "@/components/ui/button"

/**
 * A selectable option card built on the shadcn Button. Use for answers in a list
 * (topics, periods, regions, variables). `selected` draws the primary ring.
 */
function ChoiceButton({
  className,
  selected,
  ...props
}: React.ComponentProps<typeof Button> & { selected?: boolean }) {
  return (
    <Button
      type="button"
      variant="outline"
      data-selected={selected}
      className={cn(
        "h-auto w-full flex-row items-start justify-start gap-3 rounded-2xl px-4 py-3 text-left font-normal whitespace-normal hover:border-foreground/40 data-[selected=true]:border-brand-blue data-[selected=true]:bg-brand-blue/10 data-[selected=true]:ring-1 data-[selected=true]:ring-brand-blue",
        className
      )}
      {...props}
    />
  )
}

export { ChoiceButton }
