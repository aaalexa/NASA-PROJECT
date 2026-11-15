"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowLeftIcon, HomeIcon } from "@heroicons/react/24/outline";
import { Button, buttonVariants } from "@/components/ui/button";
import { ErrorScreen } from "@/components/errors/ErrorScreen";
import { useTranslation } from "@/context/LanguageContext";

/** 404: unmatched routes and `notFound()` calls. Renders inside the root layout, so theme and language apply. */
export default function NotFound() {
  const { t } = useTranslation();
  const router = useRouter();

  const goBack = () => {
    if (window.history.length > 1) router.back();
    else router.push("/");
  };

  return (
    <ErrorScreen
      left="4"
      right="4"
      eyebrow={t("errors.notFound.eyebrow")}
      title={t("errors.notFound.title")}
      description={t("errors.notFound.description")}
    >
      <Button size="lg" variant="outline" onClick={goBack}>
        <ArrowLeftIcon className="size-5" />
        {t("errors.notFound.back")}
      </Button>
      <Link href="/" className={buttonVariants({ size: "lg" })}>
        <HomeIcon className="size-5" />
        {t("errors.notFound.home")}
      </Link>
    </ErrorScreen>
  );
}
