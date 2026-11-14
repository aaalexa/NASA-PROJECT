"use client"

import * as React from "react"
import { es, enUS } from "react-day-picker/locale"
import { CalendarDaysIcon } from "@heroicons/react/24/outline"

import { Button } from "@/components/ui/button"
import { Calendar } from "@/components/ui/calendar"
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover"

function toDate(iso: string): Date | undefined {
  const [y, m, d] = iso.split("-").map(Number)
  return y ? new Date(y, (m ?? 1) - 1, d ?? 1) : undefined
}

function toIso(date: Date): string {
  const m = String(date.getMonth() + 1).padStart(2, "0")
  const d = String(date.getDate()).padStart(2, "0")
  return `${date.getFullYear()}-${m}-${d}`
}

/** shadcn date picker: Button trigger + Popover + Calendar. Value is an ISO yyyy-mm-dd string. */
function DatePicker({
  value,
  onChange,
  language,
  label,
  min,
  max,
}: {
  value: string
  onChange: (iso: string) => void
  language: "es" | "en"
  label: string
  min?: string
  max?: string
}) {
  const [open, setOpen] = React.useState(false)
  const selected = toDate(value)
  const text = selected
    ? selected.toLocaleDateString(language === "es" ? "es-ES" : "en-US", { day: "numeric", month: "short", year: "numeric" })
    : label

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger
        render={
          <Button variant="outline" aria-label={label} className="h-10 w-full justify-start gap-2 px-4 font-normal" />
        }
      >
        <CalendarDaysIcon className="size-4 text-muted-foreground" />
        {text}
      </PopoverTrigger>
      <PopoverContent className="w-auto p-2" align="start">
        <Calendar
          mode="single"
          locale={language === "es" ? es : enUS}
          selected={selected}
          defaultMonth={selected}
          captionLayout="dropdown"
          startMonth={new Date(1990, 0)}
          endMonth={new Date(2026, 11)}
          disabled={[
            ...(min ? [{ before: toDate(min)! }] : []),
            ...(max ? [{ after: toDate(max)! }] : []),
          ]}
          onSelect={(d) => {
            if (d) {
              onChange(toIso(d))
              setOpen(false)
            }
          }}
        />
      </PopoverContent>
    </Popover>
  )
}

export { DatePicker }
