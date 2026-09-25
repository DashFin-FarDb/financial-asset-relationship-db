"use client";

import NetworkVisualization from "./NetworkVisualization";
import type { VisualizationData } from "../types/api";

type InstitutionalDemoProps = Readonly<{
  data: VisualizationData | null;
}>;

/**
 * Institutional presentation surface for the existing FarDb/GRAC graph.
 *
 * This component deliberately contains presentation and narrative only.
 * GRAC semantics, persistence, and publication logic remain in the existing
 * graph and governed-edge APIs.
 */
export default function InstitutionalDemo({
  data,
}: InstitutionalDemoProps) {
  return (
    <div className="space-y-8">
      <section className="rounded-2xl bg-slate-900 px-6 py-8 text-white shadow-lg">
        <div className="max-w-4xl">
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-300">
            FarDb Institutional Demonstrator
          </p>
          <h2 className="mt-3 text-3xl font-semibold tracking-tight sm:text-4xl">
            Governed relationships for consequential decisions
          </h2>
          <p className="mt-4 max-w-3xl text-base leading-7 text-slate-300">
            A relationship is more than a line in a graph. FarDb can connect the
            published relationship to the assertion, evidence, temporal context,
            lifecycle history, and publication provenance behind it.
          </p>
        </div>
      </section>

      <section className="grid grid-cols-1 gap-4 md:grid-cols-4">
        {[
          {
            number: "01",
            title: "Relationship",
            body: "Start with the relationship that a decision-maker needs to understand.",
          },
          {
            number: "02",
            title: "Evidence",
            body: "Inspect the supporting, opposing, and contextual evidence attached to the assertion.",
          },
          {
            number: "03",
            title: "Time & authority",
            body: "See effective time, known time, proposer, determining authority, and lifecycle state.",
          },
          {
            number: "04",
            title: "Provenance",
            body: "Trace the published edge back to its assertion, revision, execution, and hashes.",
          },
        ].map((item) => (
          <article
            key={item.number}
            className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm"
          >
            <p className="text-xs font-semibold tracking-[0.16em] text-slate-400">
              {item.number}
            </p>
            <h3 className="mt-2 text-lg font-semibold text-slate-900">
              {item.title}
            </h3>
            <p className="mt-2 text-sm leading-6 text-slate-600">{item.body}</p>
          </article>
        ))}
      </section>

      <section className="rounded-xl border border-amber-200 bg-amber-50 px-5 py-4">
        <p className="text-sm font-medium text-amber-900">
          Governance boundary
        </p>
        <p className="mt-1 text-sm leading-6 text-amber-800">
          The demonstrator presents relationship evidence and governance state.
          It does not grant an AI system authority to determine or publish a
          relationship.
        </p>
      </section>

      <section>
        <div className="mb-4">
          <h3 className="text-2xl font-semibold text-slate-900">
            Explore the relationship graph
          </h3>
          <p className="mt-1 text-sm leading-6 text-slate-600">
            Select a relationship to inspect the governed assertion behind the
            published graph edge.
          </p>
        </div>
        <NetworkVisualization data={data} />
      </section>
    </div>
  );
}
