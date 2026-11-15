"use client"; // Error boundaries must be Client Components

import { useEffect } from "react";
import Link from "next/link";
import { ArrowPathIcon, HomeIcon } from "@heroicons/react/24/outline";
import { Button, buttonVariants } from "@/components/ui/button";
import { ErrorScreen } from "@/components/errors/ErrorScreen";
import { useTranslation } from "@/context/LanguageContext";

/**
 * 500-style screen for runtime errors inside the app (below the root layout). `retry` re-fetches
 * and re-renders the segment. In production, server errors only expose `digest`, which we show as a
 * reference to match the server logs.
 */
export default function Error({ error, retry }: { error: unknown; retry: () => void }) {
  const { t } = useTranslation();

  useEffect(() => {
    console.error(error);
  }, [error]);

  const digest = error instanceof Error && "digest" in error ? String((error as Error & { digest?: string }).digest ?? "") : "";

  return (
    <ErrorScreen
      left="5"
      right="0"
      eyebrow={t("errors.server.eyebrow")}
      title={t("errors.server.title")}
      description={t("errors.server.description")}
      detail={digest ? `${t("errors.server.reference")}: ${digest}` : undefined}
    >
      <Button size="lg" onClick={() => retry()}>
        <ArrowPathIcon className="size-5" />
        {t("errors.server.retry")}
      </Button>
      <Link href="/" className={buttonVariants({ size: "lg", variant: "outline" })}>
        <HomeIcon className="size-5" />
        {t("errors.server.home")}
      </Link>
    </ErrorScreen>
  );
}
