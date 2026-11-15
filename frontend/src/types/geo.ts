export type WorkflowStep = "region" | "period" | "variables" | "results";

/** A variable id from the backend catalog (e.g. "lluvia_gpcp", "temp_aire", "cdd_imerg"). */
export type VariableId = string;

export type Experience = "novice" | "expert";
export type AppPhase = "onboarding" | "guided" | "expert";
export type TopicId = "rain" | "heat" | "soil" | "extremes";

export interface DateRange {
  start: string;
  end: string;
  preset?: string;
}

export interface GeoPoint {
  lat: number;
  lng: number;
}

export interface RegionAnalysisPayload {
  regionName: string;
  description: string;
  /** Triangle kept for backwards compatibility with the GeoJSON the voice route returns. */
  triangleVertices: [GeoPoint, GeoPoint, GeoPoint];
  /** What is drawn on the globe and analysed: the bounding-box corners (or the triangle). */
  outline?: GeoPoint[];
  geoJsonPolygon: {
    type: "Polygon";
    coordinates: number[][][];
  };
  /** Official backend region id (e.g. "amazonia"); when set the API reuses its warm RAM cache. */
  backendId?: string;
}
