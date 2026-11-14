export type WorkflowStep = "region" | "period" | "variables" | "results";

export type VariableId =
  | "precipitation"
  | "temperature"
  | "moisture"
  | "evapotranspiration"
  | "vegetation";

export type Experience = "novice" | "expert";
export type AppPhase = "onboarding" | "guided" | "expert";
export type TopicId = "rain" | "heat" | "vegetation" | "soil";

export interface DateRange {
  start: string;
  end: string;
  preset?: string;
}

export interface GeoPoint {
  lat: number;
  lng: number;
}

export interface NasaVariableSuggestion {
  id: string;
  name: string;
  simpleExplanation: string;
}

export interface RegionAnalysisPayload {
  regionName: string;
  description: string;
  triangleVertices: [GeoPoint, GeoPoint, GeoPoint];
  geoJsonPolygon: {
    type: "Polygon";
    coordinates: [[[number, number], [number, number], [number, number], [number, number]]];
  };
  suggestedVariables: NasaVariableSuggestion[];
}

export interface PredefinedRegion {
  id: string;
  name: { es: string; en: string };
  area: { es: string; en: string };
  center: GeoPoint;
  triangle: [GeoPoint, GeoPoint, GeoPoint];
  aliases: string[];
}
