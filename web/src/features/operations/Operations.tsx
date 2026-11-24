import { SHORT, type DesignRow } from "../../shared/data/report";
import { hours } from "../../shared/format";
import styles from "./Operations.module.css";

const KINDS: Record<string, string> = {
  extractor_outage: "Historian extractor stops for a unit",
  flatline: "A sensor flatlines",
  rename_after_golive: "A tag is renamed after go-live",
};

interface Props {
  designs: Record<string, DesignRow>;
  order: string[];
  sla: Record<string, number>;
}

export function Operations({ designs, order, sla }: Props) {
  const rows = order.filter((n) => designs[n]);
  return (
    <div className={styles.wrap}>
      <table className={styles.table}>
        <caption>Time from the incident to the first alert, median; caught within the SLA, of all</caption>
        <thead>
          <tr>
            <th scope="col">Incident</th>
            <th scope="col">SLA</th>
            {rows.map((n) => (
              <th key={n} scope="col" className={n === "platform" ? styles.mine : undefined}>
                {SHORT[n] ?? n}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {Object.entries(KINDS).map(([k, label]) => (
            <tr key={k}>
              <th scope="row">{label}</th>
              <td className="num">{sla[k] === undefined ? "n/a" : `${sla[k]} h`}</td>
              {rows.map((n) => {
                const inc = (designs[n] as DesignRow).incidents[k];
                if (!inc) return <td key={n}>n/a</td>;
                const missed = inc.in_sla < inc.n;
                return (
                  <td key={n} className={`num ${missed ? styles.missed : ""} ${n === "platform" ? styles.mine : ""}`}>
                    {hours(inc.median_hours)}
                    <span className={styles.sub}>
                      {inc.in_sla} of {inc.n} in SLA
                    </span>
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
