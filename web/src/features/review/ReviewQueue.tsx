import { AnimatePresence, motion } from "framer-motion";
import { useState } from "react";
import type { ReviewItem } from "../../shared/data/report";
import { evidenceLabel, pct } from "../../shared/format";
import { settle } from "../../shared/theme/motion";
import { Empty } from "../../shared/ui/states";
import styles from "./ReviewQueue.module.css";

/** What the engineer saw for each link code would not make alone: the candidates, ranked, with their evidence. */
export function ReviewQueue({ items }: { items: ReviewItem[] }) {
  const [open, setOpen] = useState<string | null>(items[0]?.ts ?? null);
  if (items.length === 0) {
    return <Empty title="Nothing to review">Every series on this plant was linked by code.</Empty>;
  }
  return (
    <ol className={styles.list}>
      {items.map((it) => {
        const isOpen = open === it.ts;
        return (
          <li key={it.ts} className={styles.item}>
            <button
              type="button"
              className={styles.head}
              aria-expanded={isOpen}
              onClick={() => setOpen(isOpen ? null : it.ts)}
            >
              <span className={`num ${styles.name}`}>{it.name}</span>
              <span className={styles.desc}>{it.description}</span>
              <span className={styles.chosen}>
                {it.chosen ?? "no machine"}
                {!it.right && <em className={styles.slip}> engineer slip</em>}
              </span>
            </button>
            <AnimatePresence initial={false}>
              {isOpen && (
                <motion.div
                  initial={{ height: 0, opacity: 0 }}
                  animate={{ height: "auto", opacity: 1 }}
                  exit={{ height: 0, opacity: 0 }}
                  transition={settle}
                  className={styles.body}
                >
                  <table className={styles.table}>
                    <caption>Candidates as the engineer saw them</caption>
                    <thead>
                      <tr>
                        <th scope="col">Machine</th>
                        <th scope="col">Confidence</th>
                        <th scope="col">Evidence</th>
                      </tr>
                    </thead>
                    <tbody>
                      {it.candidates.map((c) => (
                        <tr key={c.tag} className={c.tag === it.chosen ? styles.picked : undefined}>
                          <td className="num">{c.tag}</td>
                          <td className="num">{pct(c.p)}</td>
                          <td>
                            {Object.entries(c.evidence).length === 0
                              ? "none"
                              : Object.entries(c.evidence).map(([k, v]) => (
                                  <span key={k} className={styles.chip}>
                                    {evidenceLabel(k)}
                                    {k === "signal" ? ` +${v.toFixed(2)}` : ""}
                                  </span>
                                ))}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </motion.div>
              )}
            </AnimatePresence>
          </li>
        );
      })}
    </ol>
  );
}
