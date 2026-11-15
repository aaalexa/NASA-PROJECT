"use client";

import Image from "next/image";
import Link from "next/link";
import { ErrorGlobe } from "@/components/errors/ErrorGlobe";

interface ErrorScreenProps {
  /** Digit shown left of the globe ("4" for 404, "5" for 500). Omit both digits for a globe-only screen. */
  left?: string;
  /** Digit shown right of the globe. */
  right?: string;
  /** Small text above the title (e.g. "Error 404"). */
  eyebrow?: string;
  title: string;
  description: string;
  /** Extra line under the description, e.g. an error reference. */
  detail?: string;
  /** Dimmed globe without markers. */
  muted?: boolean;
  /** Icon or badge drawn over the globe. */
  badge?: React.ReactNode;
  /** Buttons. */
  children?: React.ReactNode;
}

/**
 * Shared layout for every error state: floating Cobe globe between two digits (or alone),
 * title, description and actions, with a staggered fade-up entrance. Context-free, so it also
 * renders inside global-error, where the app providers are not mounted.
 */
export function ErrorScreen({ left, right, eyebrow, title, description, detail, muted, badge, children }: ErrorScreenProps) {
  const hasDigits = Boolean(left || right);

  return (
    <main className="relative flex min-h-dvh w-full flex-col items-center justify-center overflow-hidden bg-background px-4 py-16 text-foreground">
      {/* Soft palette halos */}
      <div aria-hidden className="pointer-events-none absolute -top-40 -left-40 size-[28rem] rounded-full bg-brand-blue/15 blur-3xl" />
      <div aria-hidden className="pointer-events-none absolute -right-40 -bottom-40 size-[28rem] rounded-full bg-brand-red/10 blur-3xl" />

      <Link href="/" className="absolute top-5 left-5 flex items-center gap-2.5 rounded-full pr-3 text-sm font-bold tracking-tight">
        <Image src="/logo-light.png" alt="" width={28} height={28} className="size-7 dark:hidden" aria-hidden />
        <Image src="/logo-dark.png" alt="" width={28} height={28} className="hidden size-7 dark:block" aria-hidden />
        Moody Trends
      </Link>

      <div className="relative z-10 flex max-w-xl flex-col items-center text-center">
        <div className="mt-fade-up mb-10 flex items-center justify-center gap-4 md:gap-6" style={{ animationDelay: "0ms" }}>
          {hasDigits && (
            <span className="select-none text-8xl font-bold tracking-tight text-foreground/85 md:text-9xl" aria-hidden>
              {left}
            </span>
          )}
          <div className={`mt-float relative ${hasDigits ? "size-24 md:size-36" : "size-40 md:size-52"}`}>
            <ErrorGlobe muted={muted} />
            {badge && (
              <div className="absolute inset-0 flex items-center justify-center">
                <span className="flex size-14 items-center justify-center rounded-full bg-brand-red text-white shadow-lg md:size-16">
                  {badge}
                </span>
              </div>
            )}
          </div>
          {hasDigits && (
            <span className="select-none text-8xl font-bold tracking-tight text-foreground/85 md:text-9xl" aria-hidden>
              {right}
            </span>
          )}
        </div>

        {eyebrow && (
          <p className="mt-fade-up mb-3 rounded-full bg-brand-olive px-3 py-1 text-xs font-bold text-white" style={{ animationDelay: "80ms" }}>
            {eyebrow}
          </p>
        )}
        <h1 className="mt-fade-up mb-4 text-3xl font-semibold tracking-tight md:text-5xl" style={{ animationDelay: "120ms" }}>
          {title}
        </h1>
        <p className="mt-fade-up mx-auto mb-3 max-w-md text-base text-muted-foreground md:text-lg" style={{ animationDelay: "200ms" }}>
          {description}
        </p>
        {detail && (
          <p className="mt-fade-up mb-3 rounded-full bg-muted px-3 py-1 font-mono text-xs text-muted-foreground" style={{ animationDelay: "240ms" }}>
            {detail}
          </p>
        )}
        {children && (
          <div className="mt-fade-up mt-7 flex flex-wrap items-center justify-center gap-3" style={{ animationDelay: "280ms" }}>
            {children}
          </div>
        )}
      </div>
    </main>
  );
}
