"use client";

import { useCallback, useMemo, useState } from "react";
import dynamic from "next/dynamic";
import type {
  VisualizationData,
  VisualizationEdge,
  VisualizationNode,
} from "../types/api";
import RelationshipExplanationPanel from "./RelationshipExplanationPanel";

// Dynamically import Plotly to avoid SSR issues
const Plot = dynamic(() => import("react-plotly.js"), {
  ssr: false,
  loading: () => (
    <div className="text-center p-8">Loading visualization...</div>
  ),
});

type NetworkVisualizationProps = Readonly<{
  data: VisualizationData | null;
}>;

type EdgeTrace = {
  type: "scatter3d";
  mode: "lines";
  x: number[];
  y: number[];
  z: number[];
  line: {
    color: string;
    width: number;
  };
  hoverinfo: "none";
  showlegend: false;
  /** Stable edge selection key, repeated for each of the two line points. */
  customdata: [string, string];
};

type NodeTrace = {
  type: "scatter3d";
  mode: "markers" | "text" | "lines" | "markers+text";
  x: number[];
  y: number[];
  z: number[];
  text: string[];
  hovertext: string[];
  hoverinfo: "text";
  marker: {
    size: number[];
    color: string[];
    line: {
      color: string;
      width: number;
    };
  };
  textposition: "top center";
  textfont: {
    size: number;
  };
};

type VisualizationStatus = "loading" | "ready" | "empty" | "tooLarge";

type VisualizationPreparation = {
  status: VisualizationStatus;
  message: string;
  plotData: Array<EdgeTrace | NodeTrace>;
};

/**
 * One edge paired with its resolved endpoint nodes. Shared by the Plotly trace
 * builder and the keyboard-accessible relationship list so both views always
 * agree on which edges are renderable and how each is identified for selection.
 */
type PreparedEdge = {
  key: string;
  edge: VisualizationEdge;
  sourceNode: VisualizationNode;
  targetNode: VisualizationNode;
};

const MAX_NODES = Number(process.env.NEXT_PUBLIC_MAX_NODES) || 500;
const MAX_EDGES = Number(process.env.NEXT_PUBLIC_MAX_EDGES) || 2000;

/**
 * Derive a stable selection key for an edge. Governed edges are keyed by their
 * assertion ID (stable across data refreshes); legacy edges fall back to their
 * endpoint/type triple, which is stable as long as the relationship itself
 * does not change.
 */
function edgeKey(edge: VisualizationEdge): string {
  if (edge.assertion_id) return `assertion:${edge.assertion_id}`;
  return `edge:${edge.source}|${edge.target}|${edge.relationship_type}`;
}

/**
 * Resolve edges against their endpoint nodes, skipping any edge whose source
 * or target node is missing. This is the single source of truth for "valid"
 * edges consumed by both the Plotly traces and the keyboard-accessible list.
 */
function buildValidEdges(
  nodes: VisualizationData["nodes"],
  edges: VisualizationData["edges"],
): PreparedEdge[] {
  const nodeMap = new Map(nodes.map((node) => [node.id, node]));
  return edges.reduce<PreparedEdge[]>((acc, edge) => {
    const sourceNode = nodeMap.get(edge.source);
    const targetNode = nodeMap.get(edge.target);

    if (!sourceNode || !targetNode) {
      if (process.env.NODE_ENV === "development") {
        console.debug(
          `[Development Only] Skipping invalid edge: source ${edge.source} or target ${edge.target} not found.`,
        );
      }
      return acc;
    }

    acc.push({ key: edgeKey(edge), edge, sourceNode, targetNode });
    return acc;
  }, []);
}

/**
 * Build a Plotly 3D scatter trace that renders nodes as markers with inline labels.
 *
 * Produces a `scatter3d` trace with markers and text where each node's position, label,
 * marker size, and color are taken from the corresponding node object; hover text shows
 * the node's name, symbol, and asset class.
 *
 * @param nodes - Array of node objects. Each node should provide `x`, `y`, `z`, `symbol`, `name`, `asset_class`, `size`, and `color`.
 * @returns A NodeTrace configured as a 3D scatter with markers and text labels.
 */
function buildNodeTrace(nodes: VisualizationData["nodes"]): NodeTrace {
  return {
    type: "scatter3d",
    mode: "markers+text",
    x: nodes.map((n) => n.x),
    y: nodes.map((n) => n.y),
    z: nodes.map((n) => n.z),
    text: nodes.map((n) => n.symbol),
    hovertext: nodes.map(
      (n) => `${n.name} (${n.symbol})<br>Class: ${n.asset_class}`,
    ),
    hoverinfo: "text",
    marker: {
      size: nodes.map((n) => n.size),
      color: nodes.map((n) => n.color),
      line: {
        color: "white",
        width: 0.5,
      },
    },
    textposition: "top center",
    textfont: {
      size: 8,
    },
  };
}

/**
 * Build Plotly 3D line traces from already-validated edges.
 *
 * @param validEdges - Edges paired with their resolved endpoint nodes (see `buildValidEdges`).
 * @returns An array of `EdgeTrace` objects; each trace is a two-point 3D line connecting
 *   source and target, carrying the edge's stable selection key as `customdata`.
 */
function buildEdgeTraces(validEdges: readonly PreparedEdge[]): EdgeTrace[] {
  return validEdges.map(({ key, edge, sourceNode, targetNode }) => ({
    type: "scatter3d",
    mode: "lines",
    x: [sourceNode.x, targetNode.x],
    y: [sourceNode.y, targetNode.y],
    z: [sourceNode.z, targetNode.z],
    line: {
      color: `rgba(125, 125, 125, ${edge.strength})`,
      width: edge.strength * 3,
    },
    hoverinfo: "none",
    showlegend: false,
    customdata: [key, key],
  }));
}

/**
 * Prepare Plotly traces and a rendering status from the provided visualization data.
 *
 * @param data - The visualization input containing `nodes` and `edges` to convert into traces.
 * @param validEdges - Edges already resolved against their endpoint nodes (see `buildValidEdges`).
 * @returns A `VisualizationPreparation` describing the resulting `status`, a human-readable `message`, and `plotData`:
 * - `status` is `"empty"` when there are no nodes,
 * - `"tooLarge"` when node or edge counts exceed configured limits,
 * - `"ready"` when `plotData` contains the edge traces followed by the node trace.
 */
function prepareVisualizationData(
  data: VisualizationData,
  validEdges: readonly PreparedEdge[],
): VisualizationPreparation {
  const nodes = Array.isArray(data.nodes) ? data.nodes : [];
  const edges = Array.isArray(data.edges) ? data.edges : [];

  if (nodes.length === 0) {
    return {
      status: "empty",
      message: "Visualization data is missing nodes.",
      plotData: [],
    };
  }

  if (nodes.length > MAX_NODES || edges.length > MAX_EDGES) {
    return {
      status: "tooLarge",
      message:
        `Visualization is unavailable because the dataset is too large (` +
        `${nodes.length} nodes, ${edges.length} edges). Maximum: ` +
        `${MAX_NODES} nodes, ${MAX_EDGES} edges.`,
      plotData: [],
    };
  }

  const nodeTrace = buildNodeTrace(nodes);
  const edgeTraces = buildEdgeTraces(validEdges);

  return {
    status: "ready",
    message: "",
    plotData: [...edgeTraces, nodeTrace],
  };
}

type RelationshipListProps = Readonly<{
  validEdges: readonly PreparedEdge[];
  selectedKey: string | null;
  onSelect: (key: string) => void;
}>;

/**
 * Keyboard-accessible list of relationships, mirroring exactly the edges drawn
 * in the plot. Provides a first-class selection route independent of clicking
 * a line in the 3D plot.
 */
function RelationshipList({
  validEdges,
  selectedKey,
  onSelect,
}: RelationshipListProps) {
  return (
    <div
      role="group"
      aria-label="Relationships (keyboard-accessible list)"
      className="max-h-64 overflow-y-auto border border-gray-200 rounded-lg p-2"
    >
      <ul className="space-y-1">
        {validEdges.map(({ key, edge }) => (
          <RelationshipListItem
            key={key}
            edgeKey={key}
            edge={edge}
            isSelected={key === selectedKey}
            onSelect={onSelect}
          />
        ))}
      </ul>
    </div>
  );
}

type RelationshipListItemProps = Readonly<{
  edgeKey: string;
  edge: VisualizationEdge;
  isSelected: boolean;
  onSelect: (key: string) => void;
}>;

/** A single selectable relationship row within the keyboard-accessible list. */
function RelationshipListItem({
  edgeKey: key,
  edge,
  isSelected,
  onSelect,
}: RelationshipListItemProps) {
  const isGoverned = edge.governance_status === "governed";
  return (
    <li>
      <button
        type="button"
        aria-pressed={isSelected}
        onClick={() => onSelect(key)}
        className={`w-full text-left text-sm px-2 py-1 rounded ${
          isSelected
            ? "bg-blue-100 text-blue-900"
            : "hover:bg-gray-100 text-gray-700"
        }`}
      >
        {edge.source} {"\u2192"} {edge.target}{" "}
        <span className="text-xs text-gray-500">
          ({edge.relationship_type})
        </span>{" "}
        <span
          className={`text-xs px-1.5 py-0.5 rounded ${
            isGoverned
              ? "bg-blue-50 text-blue-700"
              : "bg-gray-100 text-gray-500"
          }`}
        >
          {isGoverned ? "Governed" : "Legacy"}
        </span>
      </button>
    </li>
  );
}

/**
 * Display an interactive 3D network of assets from the provided visualization payload.
 *
 * It validates incoming data against size limits and prepares Plotly traces for nodes and edges.
 *
 * @param data - Visualization payload containing `nodes` and `edges`.
 *   Nodes are objects with at least: `id`, `x`, `y`, `z`, `symbol`, `name`, `asset_class`, `size`, `color`.
 *   Edges are objects with at least: `source`, `target`, `relationship_type`, `strength`.
 * @returns A JSX element rendering the 3D network plot when data is valid, or a centred status message when data is missing, invalid or too large.
 */
export default function NetworkVisualization({
  data,
}: NetworkVisualizationProps) {
  const [selectedKey, setSelectedKey] = useState<string | null>(null);

  const validEdges = useMemo<PreparedEdge[]>(() => {
    if (!data || !Array.isArray(data.nodes) || !Array.isArray(data.edges))
      return [];
    return buildValidEdges(data.nodes, data.edges);
  }, [data]);

  const preparation = useMemo<VisualizationPreparation>(() => {
    if (!data) {
      return {
        status: "empty",
        message: "No visualization data available.",
        plotData: [],
      };
    }
    return prepareVisualizationData(data, validEdges);
  }, [data, validEdges]);

  const { plotData, status, message } = preparation;

  const handlePlotClick = useCallback(
    (event: { points?: ReadonlyArray<{ customdata?: unknown }> }) => {
      const point = event?.points?.[0];
      if (typeof point?.customdata === "string") {
        setSelectedKey(point.customdata);
      }
    },
    [],
  );

  // Always re-resolved from the current `validEdges`, so a stale key can never
  // point at a relationship other than the one the user selected: if the
  // dataset changes such that the key no longer exists, this naturally
  // becomes `null` instead of silently resolving to an unrelated edge.
  const selectedEdge = useMemo(
    () =>
      validEdges.find((prepared) => prepared.key === selectedKey)?.edge ?? null,
    [validEdges, selectedKey],
  );

  if (status !== "ready") {
    const isUrgent = status === "tooLarge";
    return (
      <div
        className="text-center p-8 text-gray-600"
        role={isUrgent ? "alert" : "status"}
        aria-live={isUrgent ? "assertive" : "polite"}
      >
        {message}
      </div>
    );
  }

  return (
    <div className="w-full space-y-4">
      <div className="w-full h-[800px]">
        <Plot
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          data={plotData as any}
          layout={{
            title: "3D Asset Relationship Network",
            showlegend: false,
            scene: {
              xaxis: {
                showgrid: false,
                zeroline: false,
                showticklabels: false,
              },
              yaxis: {
                showgrid: false,
                zeroline: false,
                showticklabels: false,
              },
              zaxis: {
                showgrid: false,
                zeroline: false,
                showticklabels: false,
              },
              camera: {
                eye: { x: 1.5, y: 1.5, z: 1.5 },
              },
            },
            hovermode: "closest",
            margin: { l: 0, r: 0, b: 0, t: 40 },
            paper_bgcolor: "rgba(0,0,0,0)",
            plot_bgcolor: "rgba(0,0,0,0)",
          }}
          config={{
            displayModeBar: true,
            displaylogo: false,
            responsive: true,
          }}
          style={{ width: "100%", height: "100%" }}
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          onClick={handlePlotClick as any}
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <RelationshipList
          validEdges={validEdges}
          selectedKey={selectedKey}
          onSelect={setSelectedKey}
        />
        <RelationshipExplanationPanel relationship={selectedEdge} />
      </div>
    </div>
  );
}
