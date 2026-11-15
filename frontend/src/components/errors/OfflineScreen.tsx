"use client";

import { useSyncExternalStore } from "react";
import { ArrowPathIcon, SignalSlashIcon } from "@heroicons/react/24/outline";
import { Button } from "@/components/ui/button";
import { ErrorScreen } from "@/components/errors/ErrorScreen";
import { useTranslation } from "@/context/LanguageContext";

function subscribe(onChange: () => void) {
  window.addEventListener("online", onChange);
  window.addEventListener("offline", onChange);
  return () => {
    window.removeEventListener("online", onChange);
    window.removeEventListener("offline", onChange);
  };
}

/**
 * Full-screen overlay while the browser reports no connection. It disappears on its own when the
 * `online` event fires; the app state underneath is kept, nothing is reloaded unless the user asks.
 */
export function OfflineScreen() {
  const { t } = useTranslation();
  const online = useSyncExternalStore(subscribe, () => navigator.onLine, () => true);

  if (online) return null;

  return (
    <div role="alertdialog" aria-modal="true" aria-live="assertive" className="fixed inset-0 z-[100]">
      <ErrorScreen
        muted
        badge={<SignalSlashIcon className="size-7 md:size-8" />}
        eyebrow={t("errors.offline.eyebrow")}
        title={t("errors.offline.title")}
        description={t("errors.offline.description")}
        detail={t("errors.offline.waiting")}
      >
        <Button size="lg" onClick={() => window.location.reload()}>
          <ArrowPathIcon className="size-5" />
          {t("errors.offline.retry")}
        </Button>
      </ErrorScreen>
    </div>
  );
}
