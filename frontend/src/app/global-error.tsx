"use client"; // Error boundaries must be Client Components

import "./globals.css";
import { useEffect } from "react";
import Link from "next/link";
import { ArrowPathIcon, HomeIcon } from "@heroicons/react/24/outline";
import { Button, buttonVariants } from "@/components/ui/button";
import { ErrorScreen } from "@/components/errors/ErrorScreen";

/**
 * Last-resort boundary: replaces the root layout when it fails, so it renders its own <html>/<body>,
 * imports the global styles and cannot use the app providers (language, theme). The copy is bilingual
 * and the theme is read from the same localStorage key the app uses.
 */
export default function GlobalError({ error, retry }: { error: unknown; retry: () => void }) {
  useEffect(() => {
    console.error(error);
    try {
      const saved = localStorage.getItem("nasa_earth_theme");
      document.documentElement.classList.toggle("dark", saved !== "light");
    } catch {
      // storage blocked: keep the dark default
    }
  }, [error]);

  const digest = error instanceof Error && "digest" in error ? String((error as Error & { digest?: string }).digest ?? "") : "";

  return (
    <html lang="es" className="dark" suppressHydrationWarning>
      <body className="font-sans bg-background text-foreground antialiased">
        <title>Error · Moody Trends</title>
        <ErrorScreen
          left="5"
          right="0"
          eyebrow="Error 500"
          title="Algo falló en nuestra estación"
          description="No pudimos cargar la aplicación. Reintenta en unos segundos. · We couldn't load the app. Please retry in a few seconds."
          detail={digest ? `Ref: ${digest}` : undefined}
        >
          <Button size="lg" onClick={() => retry()}>
            <ArrowPathIcon className="size-5" />
            Reintentar · Retry
          </Button>
          <Link href="/" className={buttonVariants({ size: "lg", variant: "outline" })}>
            <HomeIcon className="size-5" />
            Inicio · Home
          </Link>
        </ErrorScreen>
      </body>
    </html>
  );
}
