import type { Gate } from "../../shared/data/report";
import styles from "./Gates.module.css";

const fmt = (v: number) => (Math.abs(v) >= 10 || Number.isInteger(v) ? v.toFixed(0) : v.toFixed(3));

export function Gates({ gates }: { gates: Gate[] }) {
  return (
    <ul className={styles.list}>
      {gates.map((g) => (
        <li key={g.gate} className={g.pass ? styles.pass : styles.fail}>
          <span className={styles.mark}>{g.pass ? "Pass" : "Fail"}</span>
          <span>{g.gate}</span>
          <span className="num">
            {fmt(g.value)} {g.op} {fmt(g.limit)}
          </span>
        </li>
      ))}
    </ul>
  );
}
