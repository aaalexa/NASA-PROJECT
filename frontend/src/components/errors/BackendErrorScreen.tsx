"use client";

import { useEffect } from "react";
import { ArrowPathIcon, ServerStackIcon } from "@heroicons/react/24/outline";
import { Button } from "@/components/ui/button";
import { ErrorScreen } from "@/components/errors/ErrorScreen";
import { useBackend } from "@/context/BackendContext";
import { useTranslation } from "@/context/LanguageContext";

const AUTO_RETRY_MS = 15000;

/**
 * Full-screen state when the data backend cannot be used at start-up: the whole app depends on it
 * (catalog, regions, periods, analyses), so we stop here with a diagnosis instead of a broken UI.
 * The message stays generic on purpose (no URL or technical detail). Retries on demand and every
 * 15 s, and closes itself as soon as the backend answers correctly.
 */
export function BackendErrorScreen() {
  const { t } = useTranslation();
  const { failure, state, recheck } = useBackend();
  const visible = failure !== null && state !== "online";
  const retrying = state === "checking";

  useEffect(() => {
    if (!visible) return;
    const id = window.setInterval(recheck, AUTO_RETRY_MS);
    return () => window.clearInterval(id);
  }, [visible, recheck]);

  if (!visible) return null;

  return (
    <div role="alertdialog" aria-modal="true" aria-live="assertive" className="fixed inset-0 z-[90]">
      <ErrorScreen
        left="5"
        right="3"
        badge={<ServerStackIcon className="size-7 md:size-8" />}
        eyebrow={t("errors.backend.eyebrow")}
        title={t("errors.backend.title")}
        description={t("errors.backend.description")}
      >
        <Button size="lg" onClick={recheck} disabled={retrying}>
          <ArrowPathIcon className={`size-5 ${retrying ? "animate-spin" : ""}`} />
          {retrying ? t("errors.backend.checking") : t("errors.backend.retry")}
        </Button>
      </ErrorScreen>
    </div>
  );
}
