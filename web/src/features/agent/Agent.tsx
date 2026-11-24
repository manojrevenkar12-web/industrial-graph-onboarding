import { useState } from "react";
import { SHORT, type Transcript } from "../../shared/data/report";
import { Empty } from "../../shared/ui/states";
import styles from "./Agent.module.css";

const VERDICT: Record<string, string> = {
  right: "right",
  wrong: "wrong",
  declined: "asked to name the machine",
  leaks: "answered outside the user's units",
  refused_wrongly: "refused wrongly",
};

export function Agent({ transcripts }: { transcripts: Record<string, Transcript[]> }) {
  const tabs = ["platform", "model_alone", "status_quo"].filter((t) => transcripts[t]);
  const [tab, setTab] = useState(tabs[0] ?? "platform");
  const list = transcripts[tab] ?? [];
  return (
    <div className={styles.wrap}>
      <div role="tablist" aria-label="Who answered" className={styles.tabs}>
        {tabs.map((t) => (
          <button
            key={t}
            role="tab"
            type="button"
            aria-selected={t === tab}
            className={t === tab ? styles.on : undefined}
            onClick={() => setTab(t)}
          >
            {SHORT[t] ?? t}
          </button>
        ))}
      </div>
      {list.length === 0 ? (
        <Empty title="No transcripts">This design answered no questions in the sample.</Empty>
      ) : (
        <ul className={styles.list} role="tabpanel">
          {list.map((x) => (
            <li key={x.q} className={styles[x.verdict] ?? undefined}>
              <p className={styles.q}>
                <span className={styles.user}>{x.user}</span> {x.text}
              </p>
              <p className={styles.a}>{x.answer}</p>
              <p className={styles.verdict}>{VERDICT[x.verdict] ?? x.verdict}</p>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
