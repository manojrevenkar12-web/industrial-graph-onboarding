import type { LinkSample } from "../../shared/data/report";
import styles from "./Wiring.module.css";

const ROW = 26;
const WIDTH = 640;
const LEFT = 170;
const RIGHT = WIDTH - 110;

/** Tags on the left wired to the machines they measure: the moment onboarding is about. Lines draw once, on load. */
export function Wiring({ links }: { links: LinkSample[] }) {
  const machines = [...new Set(links.map((l) => l.tag))];
  const height = Math.max(links.length, machines.length) * ROW + ROW;
  const mY = (tag: string) => {
    const gap = (links.length * ROW) / Math.max(machines.length, 1);
    return ROW / 2 + gap * machines.indexOf(tag) + gap / 2;
  };
  return (
    <figure className={styles.figure}>
      <svg viewBox={`0 0 ${WIDTH} ${height}`} role="img" aria-labelledby="wiring-title">
        <title id="wiring-title">
          {links.length} historian series of one unit, each wired to the machine onboarding linked it to
        </title>
        {links.map((l, i) => {
          const y1 = ROW / 2 + i * ROW + ROW / 2;
          const y2 = mY(l.tag);
          const mid = (LEFT + RIGHT) / 2;
          return (
            <g key={l.name}>
              <text x={LEFT - 10} y={y1} className={styles.tag} textAnchor="end" dominantBaseline="middle">
                {l.name}
              </text>
              <path
                d={`M ${LEFT} ${y1} C ${mid} ${y1}, ${mid} ${y2}, ${RIGHT} ${y2}`}
                pathLength={1}
                className={`${styles.wire} ${styles[l.how] ?? ""} ${l.right ? "" : styles.wrong}`}
                style={{ animationDelay: `${i * 70}ms` }}
              />
            </g>
          );
        })}
        {machines.map((m) => (
          <g key={m}>
            <rect x={RIGHT} y={mY(m) - 11} width={92} height={22} className={styles.machine} />
            <text x={RIGHT + 46} y={mY(m)} className={styles.machineText} textAnchor="middle" dominantBaseline="middle">
              {m}
            </text>
          </g>
        ))}
      </svg>
      <figcaption className={styles.legend}>
        <span className={styles.key}>
          <i className={`${styles.swatch} ${styles.auto}`} /> linked by code
        </span>
        <span className={styles.key}>
          <i className={`${styles.swatch} ${styles.review}`} /> chosen by the engineer
        </span>
        <span className={styles.key}>
          <i className={`${styles.swatch} ${styles.inherited}`} /> renamed tag, joined to its old name
        </span>
      </figcaption>
    </figure>
  );
}
