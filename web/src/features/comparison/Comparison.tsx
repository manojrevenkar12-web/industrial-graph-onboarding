import { SHORT, type DesignRow } from "../../shared/data/report";
import { num, pct } from "../../shared/format";
import styles from "./Comparison.module.css";

interface Metric {
  title: string;
  note: string;
  value: (d: DesignRow) => number;
  show: (d: DesignRow) => string;
  better: "high" | "low";
}

const METRICS: Metric[] = [
  {
    title: "Series on the right machine",
    note: "of every historian series, at the end of the window",
    value: (d) => d.link_recall,
    show: (d) => pct(d.link_recall),
    better: "high",
  },
  {
    title: "Wrong links",
    note: "alarms and history that land on the wrong machine",
    value: (d) => d.wrong_links,
    show: (d) => num(d.wrong_links),
    better: "low",
  },
  {
    title: "Engineer hours to go-live",
    note: "per plant, for review and fixes by hand",
    value: (d) => d.onboarding_hours,
    show: (d) => `${num(d.onboarding_hours, 1)} h`,
    better: "low",
  },
  {
    title: "Work orders on the right machine",
    note: "after duplicate merges and relinks",
    value: (d) => d.work_orders.right / d.work_orders.total,
    show: (d) => pct(d.work_orders.right / d.work_orders.total),
    better: "high",
  },
  {
    title: "Incidents caught within their SLA",
    note: "outages, flatlines, tags renamed after go-live",
    value: (d) => d.incidents_in_sla,
    show: (d) => pct(d.incidents_in_sla, 0),
    better: "high",
  },
  {
    title: "Agent answers outside the user's units",
    note: "answers a person was not allowed to see",
    value: (d) => d.agent.leaks,
    show: (d) => num(d.agent.leaks),
    better: "low",
  },
];

export function Comparison({ designs, order }: { designs: Record<string, DesignRow>; order: string[] }) {
  const rows = order.filter((n) => designs[n]);
  return (
    <div className={styles.grid}>
      {METRICS.map((m) => {
        const max = Math.max(...rows.map((n) => m.value(designs[n] as DesignRow)), 1e-9);
        return (
          <section key={m.title} className={styles.plate} aria-label={m.title}>
            <h3>{m.title}</h3>
            <p className={styles.note}>{m.note}</p>
            <dl className={styles.bars}>
              {rows.map((n) => {
                const d = designs[n] as DesignRow;
                const v = m.value(d);
                return (
                  <div key={n} className={`${styles.row} ${n === "platform" ? styles.mine : ""}`}>
                    <dt>{SHORT[n] ?? n}</dt>
                    <dd>
                      <span className={styles.track}>
                        <span className={styles.fill} style={{ width: `${(100 * v) / max}%` }} />
                      </span>
                      <span className="num">{m.show(d)}</span>
                    </dd>
                  </div>
                );
              })}
            </dl>
          </section>
        );
      })}
    </div>
  );
}
