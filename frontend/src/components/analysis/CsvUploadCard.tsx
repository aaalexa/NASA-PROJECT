"use client";

import { useRef, useState } from "react";
import { ArrowUpTrayIcon } from "@heroicons/react/24/outline";
import { useTranslation } from "@/context/LanguageContext";
import { DteResult, analyzeCsv, classifyError, failureDetail } from "@/lib/api";
import { failureMessage } from "@/lib/analysisText";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";

type Units = "finales" | "originales";

/**
 * "Analyse your own CSV": uploads a monthly regional series (fecha, P, T, SM, ET or the NASA field names) to
 * `POST /api/v1/down-to-earth/calcular/csv` and hands the result to the results view. Same cleaning and method as
 * the region analysis; the backend reports every cleaning action and never fills missing months.
 */
export function CsvUploadCard({ onResult }: { onResult: (result: DteResult, fileName: string) => void }) {
  const { t } = useTranslation();
  const inputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [units, setUnits] = useState<Units>("finales");
  const [simulated, setSimulated] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async () => {
    if (!file) return;
    setBusy(true);
    setError(null);
    try {
      const result = await analyzeCsv(file, { unidades: units, simulado: simulated });
      onResult(result, file.name);
    } catch (e) {
      const detail = failureDetail(e);
      setError(`${failureMessage(classifyError(e), t)}${detail ? ` ${detail}` : ""}`);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card size="sm" className="gap-3 px-4">
      <div>
        <p className="text-sm font-bold">{t("resultsStep.uploadTitle")}</p>
        <p className="mt-0.5 text-xs text-muted-foreground">{t("resultsStep.uploadDesc")}</p>
      </div>

      <input
        ref={inputRef}
        type="file"
        accept=".csv,text/csv"
        className="sr-only"
        aria-label={t("resultsStep.uploadPick")}
        onChange={(e) => {
          setFile(e.target.files?.[0] ?? null);
          setError(null);
        }}
      />
      <Button variant="outline" size="sm" className="w-full justify-start gap-2" onClick={() => inputRef.current?.click()}>
        <ArrowUpTrayIcon className="size-4" />
        <span className="truncate">{file ? file.name : t("resultsStep.uploadPick")}</span>
      </Button>

      <div className="space-y-1.5">
        <p className="text-xs text-muted-foreground">{t("resultsStep.uploadUnits")}</p>
        <ToggleGroup
          value={[units]}
          onValueChange={(v) => v[0] && setUnits(v[0] as Units)}
          variant="outline"
          spacing={0}
          className="w-full rounded-full bg-card"
          aria-label={t("resultsStep.uploadUnits")}
        >
          <ToggleGroupItem value="finales" className="flex-1 rounded-full px-3 text-xs font-medium">
            {t("resultsStep.unitsFinal")}
          </ToggleGroupItem>
          <ToggleGroupItem value="originales" className="flex-1 rounded-full px-3 text-xs font-medium">
            {t("resultsStep.unitsOriginal")}
          </ToggleGroupItem>
        </ToggleGroup>
      </div>

      <Label className="flex items-center gap-2 text-xs font-normal">
        <Checkbox checked={simulated} onCheckedChange={(v) => setSimulated(v === true)} />
        {t("resultsStep.uploadSimulated")}
      </Label>

      {error && (
        <p className="text-xs text-brand-red" role="alert">
          {error}
        </p>
      )}

      <Button size="sm" disabled={!file || busy} onClick={submit}>
        {busy ? t("resultsStep.uploading") : t("resultsStep.uploadButton")}
      </Button>
    </Card>
  );
}
