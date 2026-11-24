import { useState, type ReactNode } from "react";
import { Agent } from "../features/agent/Agent";
import { Comparison } from "../features/comparison/Comparison";
import { Gates } from "../features/gates/Gates";
import { Operations } from "../features/operations/Operations";
import { ReviewQueue } from "../features/review/ReviewQueue";
import { Wiring } from "../features/wiring/Wiring";
import { SHORT, useReport, type Report, type WorldReport } from "../shared/data/report";
import { hours, num, pct } from "../shared/format";
import { Empty, ErrorState, Loading } from "../shared/ui/states";
import styles from "./App.module.css";

type World = "dev" | "heldout";

export function App() {
  const { load, retry } = useReport();
  return (
    <div className={styles.page}>
      <header className={styles.top}>
        <p className={styles.product}>industrial-graph-onboarding</p>
        <a className={styles.repo} href="https://github.com/manojrevenkar12-web/industrial-graph-onboarding">
          Source on GitHub
        </a>
      </header>
      {load.state === "loading" && <Loading label="Loading the study results" />}
      {load.state === "error" && <ErrorState message={load.message} onRetry={retry} />}
      {load.state === "ready" && <Results report={load.report} />}
    </div>
  );
}

function Results({ report }: { report: Report }) {
  const [world, setWorld] = useState<World>("dev");
  const data = report[world];
  return (
    <main>
      <div className={styles.switch} role="radiogroup" aria-label="Which plants">
        <button type="button" role="radio" aria-checked={world === "dev"} onClick={() => setWorld("dev")}>
          Development plants
        </button>
        <button type="button" role="radio" aria-checked={world === "heldout"} onClick={() => setWorld("heldout")}>
          Held-out plants, run once
        </button>
      </div>
      {data ? (
        <World data={data} report={report} />
      ) : (
        <Empty title="The held-out plants have not been run">
          Run <code>igo run heldout</code> once the development gates pass. It writes a lock, and a second run is
          refused.
        </Empty>
      )}
    </main>
  );
}

function World({ data, report }: { data: WorldReport; report: Report }) {
  const p = data.designs.platform;
  const manual = data.designs.status_quo;
  const passed = data.gates.filter((g) => g.pass).length;
  return (
    <>
      <section className={styles.hero} aria-labelledby="hero-title">
        <div className={styles.lede}>
          <h1 id="hero-title">Every historian tag on the machine it measures, before go-live</h1>
          <p>
            A simulated plant exports its historian, SAP PM and P&amp;IDs with the mess real plants have: three naming
            styles, internal ids, duplicate equipment, misbooked work orders. Code links what the evidence settles,
            an engineer reviews the rest, and the platform keeps the graph right after go-live.
          </p>
          {p && manual && (
            <dl className={styles.readout}>
              <div>
                <dt>Wrong links</dt>
                <dd className="num">{num(p.wrong_links)}</dd>
                <dd className={styles.vs}>manual mapping: {num(manual.wrong_links)}</dd>
              </div>
              <div>
                <dt>Engineer hours to go-live</dt>
                <dd className="num">{num(p.onboarding_hours, 1)}</dd>
                <dd className={styles.vs}>manual mapping: {num(manual.onboarding_hours, 1)}</dd>
              </div>
              <div>
                <dt>Linked by code</dt>
                <dd className="num">{pct(p.auto_share, 0)}</dd>
                <dd className={styles.vs}>{num(p.review_items)} sent to review</dd>
              </div>
            </dl>
          )}
          <p className={styles.seeds}>
            Plants from seeds <span className="num">{data.seeds.join(", ")}</span>; every design sees the same
            plants.
          </p>
        </div>
        <div className={styles.wiring}>
          {data.samples.links && data.samples.links.length > 0 ? (
            <Wiring links={data.samples.links} />
          ) : (
            <Empty title="No wiring sample for these plants">
              The held-out run finished before the wiring sample was added, and it is not run twice.
            </Empty>
          )}
        </div>
      </section>

      <Section id="compare" title="Four ways to onboard the same plant">
        <p className={styles.note}>
          {report.order.main.map((n) => SHORT[n] ?? n).join(", ")}: the platform is the last bar in each panel.
        </p>
        <Comparison designs={data.designs} order={report.order.main} />
      </Section>

      <Section id="review" title="What the engineer reviewed">
        <p className={styles.note}>
          Series code would not link alone. The engineer sees the ranked candidates and the evidence behind each.
        </p>
        <ReviewQueue items={data.samples.review} />
      </Section>

      <Section id="operations" title="After go-live">
        <p className={styles.note}>
          Incidents planted in the weeks after go-live. Manual mapping has no monitoring, so it finds out when someone
          complains.
        </p>
        <Operations designs={data.designs} order={report.order.main} sla={report.sla_hours} />
      </Section>

      <Section id="agent" title="The agent on the graph">
        <p className={styles.note}>
          Plant staff ask in plain language. The agent answers only from the graph and only for the user's units.
        </p>
        <Agent transcripts={data.samples.transcripts} />
      </Section>

      <Section id="gates" title={`Release gates: ${passed} of ${data.gates.length} pass`}>
        <Gates gates={data.gates} />
        {data.world === "heldout" && report.lock && (
          <p className={styles.note}>
            Locked to config <span className="num">{report.lock.config_hash}</span>. Median alert time for an outage:{" "}
            {hours(p?.incidents.extractor_outage?.median_hours ?? null)}.
          </p>
        )}
      </Section>
    </>
  );
}

function Section({ id, title, children }: { id: string; title: string; children: ReactNode }) {
  return (
    <section className={styles.section} aria-labelledby={`${id}-title`}>
      <h2 id={`${id}-title`}>{title}</h2>
      {children}
    </section>
  );
}
