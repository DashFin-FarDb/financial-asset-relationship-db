"use client";

import { useState } from "react";
import NetworkVisualization from "./NetworkVisualization";
import type { VisualizationData } from "../types/api";

type InstitutionalDemoProps = Readonly<{
  data: VisualizationData | null;
}>;

type ScenarioStep = Readonly<{
  label: string;
  date: string;
  effectiveAt: string;
  knownAt: string;
  state: "Proposed" | "Accepted" | "Challenged" | "Superseded";
  description: string;
  decision: string;
}>;

const SCENARIO_STEPS: readonly ScenarioStep[] = [
  {
    label: "Relationship arises",
    date: "01 May 2026",
    effectiveAt: "01 May 2026",
    knownAt: "—",
    state: "Proposed",
    description:
      "Meridian Group acquires a controlling interest in Northstar Holdings.",
    decision: "No organisational determination yet.",
  },
  {
    label: "Evidence received",
    date: "10 May 2026",
    effectiveAt: "01 May 2026",
    knownAt: "10 May 2026",
    state: "Proposed",
    description:
      "A registry extract and shareholder filing provide the initial evidence package.",
    decision: "Analyst proposes an assertion for review.",
  },
  {
    label: "Governance determination",
    date: "12 May 2026",
    effectiveAt: "01 May 2026",
    knownAt: "12 May 2026",
    state: "Accepted",
    description:
      "The authorised reviewer accepts the assertion under the applicable mandate.",
    decision:
      "Human authority determines; the graph may now project the relationship.",
  },
  {
    label: "Challenge",
    date: "22 Aug 2026",
    effectiveAt: "01 May 2026",
    knownAt: "22 Aug 2026",
    state: "Challenged",
    description:
      "A later source indicates that the original control interpretation may be incomplete.",
    decision:
      "The existing assertion remains historical evidence; it is not silently overwritten.",
  },
  {
    label: "Supersession",
    date: "26 Aug 2026",
    effectiveAt: "01 May 2026",
    knownAt: "26 Aug 2026",
    state: "Superseded",
    description:
      "A successor assertion incorporates the newer evidence and supersedes the prior determination.",
    decision:
      "The successor becomes the current governed proposition while the predecessor remains auditable.",
  },
];

function ScenarioTimeline() {
  const [stepIndex, setStepIndex] = useState(2);
  const step = SCENARIO_STEPS[stepIndex];

  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">
            Synthetic governance walkthrough
          </p>
          <h3 className="mt-2 text-2xl font-semibold text-slate-900">
            One relationship, two clocks, one accountable determination
          </h3>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">
            Demonstration-only scenario. The records below are synthetic and are
            not presented as live FarDb customer data.
          </p>
        </div>
        <div className="rounded-lg bg-slate-900 px-4 py-3 text-right text-white">
          <p className="text-xs uppercase tracking-[0.16em] text-slate-400">
            Step {stepIndex + 1} of {SCENARIO_STEPS.length}
          </p>
          <p className="mt-1 font-semibold">{step.label}</p>
        </div>
      </div>

      <div className="mt-6">
        <label
          htmlFor="scenario-step"
          className="text-sm font-medium text-slate-700"
        >
          Move through the governance timeline
        </label>
        <input
          id="scenario-step"
          type="range"
          min={0}
          max={SCENARIO_STEPS.length - 1}
          step={1}
          value={stepIndex}
          onChange={(event) => setStepIndex(Number(event.target.value))}
          className="mt-3 w-full"
        />
        <div className="mt-2 grid grid-cols-5 gap-2 text-[11px] text-slate-500">
          {SCENARIO_STEPS.map((item, index) => (
            <button
              key={item.date + item.label}
              type="button"
              onClick={() => setStepIndex(index)}
              className="text-left hover:text-slate-900"
              aria-label={"Show " + item.label}
            >
              <span className="block font-medium">{item.date}</span>
              <span>{item.label}</span>
            </button>
          ))}
        </div>
      </div>

      <div className="mt-6 grid grid-cols-1 gap-4 lg:grid-cols-3">
        <article className="rounded-xl bg-slate-50 p-4">
          <p className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-400">
            Effective time
          </p>
          <p className="mt-2 text-lg font-semibold text-slate-900">
            {step.effectiveAt}
          </p>
          <p className="mt-1 text-sm text-slate-600">
            When the relationship is represented as taking effect.
          </p>
        </article>
        <article className="rounded-xl bg-slate-50 p-4">
          <p className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-400">
            Known time
          </p>
          <p className="mt-2 text-lg font-semibold text-slate-900">
            {step.knownAt}
          </p>
          <p className="mt-1 text-sm text-slate-600">
            When the organisation has evidence sufficient to know about it.
          </p>
        </article>
        <article className="rounded-xl bg-slate-50 p-4">
          <p className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-400">
            Governance state
          </p>
          <p className="mt-2 text-lg font-semibold text-slate-900">
            {step.state}
          </p>
          <p className="mt-1 text-sm text-slate-600">{step.decision}</p>
        </article>
      </div>

      <div className="mt-4 rounded-xl border border-slate-200 p-4">
        <p className="text-sm font-medium text-slate-900">{step.description}</p>
        <div className="mt-4 grid grid-cols-1 gap-3 md:grid-cols-4">
          {[
            ["Assertion", "Control relationship proposed"],
            ["Evidence", "Supporting and potentially conflicting sources"],
            ["Authority", "Proposer → authorised determination"],
            ["Lifecycle", "Accepted → challenged → successor assertion"],
          ].map(([title, value]) => (
            <div key={title} className="rounded-lg bg-slate-50 p-3">
              <p className="text-xs font-semibold text-slate-500">{title}</p>
              <p className="mt-1 text-sm text-slate-700">{value}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

/**
 * Institutional presentation surface for the existing FarDb/GRAC graph.
 *
 * The synthetic scenario is deliberately presentation-only. GRAC semantics,
 * persistence, publication and governed-edge evidence remain in the existing
 * FarDb APIs.
 */
export default function InstitutionalDemo({ data }: InstitutionalDemoProps) {
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
          AI systems may propose, retrieve, explain, or challenge. Authority to
          determine and publish a consequential relationship remains with the
          governed decision process.
        </p>
      </section>

      <ScenarioTimeline />

      <section>
        <div className="mb-4">
          <h3 className="text-2xl font-semibold text-slate-900">
            Explore the live FarDb relationship graph
          </h3>
          <p className="mt-1 text-sm leading-6 text-slate-600">
            This section uses the existing FarDb graph and governed-edge
            explanation path. Select a relationship to inspect the assertion
            behind the published edge.
          </p>
        </div>
        <NetworkVisualization data={data} />
      </section>
    </div>
  );
}
