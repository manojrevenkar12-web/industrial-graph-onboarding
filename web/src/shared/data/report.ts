import { useCallback, useEffect, useState } from "react";

export interface Incident {
  n: number;
  in_sla: number;
  never: number;
  median_hours: number | null;
}

export interface DesignRow {
  label: string;
  series: number;
  machines: number;
  link_precision: number;
  link_recall: number;
  wrong_links: number;
  auto_share: number;
  review_items: number;
  questions_by_hand: number;
  onboarding_hours: number;
  golive_days: number;
  question_hours: number;
  duplicates: { planted: number; merged_right: number; merged_wrong: number };
  renames: { planted: number; merged_right: number; merged_wrong: number };
  units: { planted: number; caught: number; false: number };
  work_orders: {
    total: number;
    misbooked: number;
    right: number;
    relinked: number;
    relink_wrong: number;
    misbooked_fixed: number;
  };
  incidents_in_sla: number;
  incidents: Record<string, Incident>;
  failures: number;
  warned: number;
  false_warnings: number;
  agent: { right: number; wrong: number; declined: number; leaks: number; refused_wrongly: number };
  agent_right: number;
  questions: number;
}

export interface Candidate {
  tag: string;
  p: number;
  evidence: Record<string, number>;
}

export interface ReviewItem {
  ts: string;
  name: string;
  description: string;
  candidates: Candidate[];
  chosen: string | null;
  right: boolean;
}

export interface LinkSample {
  name: string;
  tag: string;
  how: string;
  right: boolean;
}

export interface Transcript {
  q: string;
  user: string;
  text: string;
  kind: string;
  answer: string;
  verdict: string;
  cited: string[];
}

export interface Gate {
  gate: string;
  value: number;
  op: "<=" | ">=";
  limit: number;
  pass: boolean;
}

export interface WorldReport {
  world: "dev" | "heldout";
  seeds: number[];
  designs: Record<string, DesignRow>;
  gates: Gate[];
  samples: {
    review: ReviewItem[];
    links?: LinkSample[];
    transcripts: Record<string, Transcript[]>;
  };
}

export interface Report {
  dev: WorldReport | null;
  heldout: WorldReport | null;
  lock: { seeds: number[]; config_hash: string } | null;
  order: { main: string[]; ablations: string[] };
  sla_hours: Record<string, number>;
}

export type Load = { state: "loading" } | { state: "error"; message: string } | { state: "ready"; report: Report };

export function useReport(url = "./data/report.json"): { load: Load; retry: () => void } {
  const [load, setLoad] = useState<Load>({ state: "loading" });
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    let alive = true;
    setLoad({ state: "loading" });
    fetch(url)
      .then((r) => {
        if (!r.ok) throw new Error(`The report did not load (HTTP ${r.status}).`);
        return r.json() as Promise<Report>;
      })
      .then((report) => alive && setLoad({ state: "ready", report }))
      .catch((e: unknown) => alive && setLoad({ state: "error", message: e instanceof Error ? e.message : String(e) }));
    return () => {
      alive = false;
    };
  }, [url, attempt]);
  const retry = useCallback(() => setAttempt((a) => a + 1), []);
  return { load, retry };
}

/** Short names for the designs, used where the full label does not fit. */
export const SHORT: Record<string, string> = {
  status_quo: "Manual",
  fuzzy_match: "Fuzzy match",
  model_alone: "Model alone",
  platform: "This platform",
  no_signal: "No signal",
  no_pid: "No P&ID",
  no_review: "No review",
  no_quality: "No quality checks",
  agent_unchecked: "Agent unchecked",
};
