"use client";

import React, { useEffect, useState } from "react";
import dynamic from "next/dynamic";
import type { VisualizationData } from "../types/api";

// Dynamically import Plotly to avoid SSR issues
const Plot = dynamic(() => import("react-plotly.js"), {
  ssr: false,
  loading: () => (
    <div className="text-center p-8">Loading visualization...</div>
  ),
});

type NetworkVisualizationProps = Readonly<{
  data: VisualizationData;
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

const MAX_NODES = Number(process.env.NEXT_PUBLIC_MAX_NODES) || 500;
const MAX_EDGES = Number(process.env.NEXT_PUBLIC_MAX_EDGES) || 2000;

/**
 * Constructs a Plotly 3D node trace from the provided node definitions.
 *
 * @param nodes - Array of node objects supplying the 3D coordinates, display label, hover metadata, size, and color. Each node is expected to include `x`, `y`, `z`, `symbol`, `name`, `asset_class`, `size`, and `color`.
 * @returns A NodeTrace configured as a 3D scatter of markers and text. Marker sizes and colors are taken from each node; hover text includes the node name, symbol, and asset class.
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
 * Converts node and edge lists into Plotly 3D line traces representing network edges.
 *
 * Skips any edge whose source or target node is not found (a warning is logged in that case).
 *
 * @param nodes - Array of node objects with `id`, `x`, `y`, and `z` coordinates.
 * @param edges - Array of edge objects with `source`, `target`, and `strength` properties.
 * @returns An array of `EdgeTrace` objects where each trace is a two-point 3D line from source to target; line color and width are derived from the edge's `strength`.
 */
function buildEdgeTraces(
  nodes: VisualizationData["nodes"],
  edges: VisualizationData["edges"],
): EdgeTrace[] {
  const nodeMap = new Map(nodes.map((node) => [node.id, node]));
  return edges.reduce<EdgeTrace[]>((acc, edge) => {
    const sourceNode = nodeMap.get(edge.source);
    const targetNode = nodeMap.get(edge.target);

    if (!sourceNode || !targetNode) {
      console.warn(
        `Missing node for edge: source=${edge.source}, target=${edge.target}`,
      );
      return acc;
    }

    acc.push({
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
    });

    return acc;
  }, []);
}

/**
 * Prepare Plotly traces and a rendering status from the provided visualization data.
 *
 * @param data - The visualization input containing `nodes` and `edges` to convert into traces.
 * @returns A `VisualizationPreparation` describing the resulting `status`, a human-readable `message`, and `plotData`:
 * - `status` is `"empty"` when there are no nodes,
 * - `"tooLarge"` when node or edge counts exceed configured limits,
 * - `"ready"` when `plotData` contains the edge traces followed by the node trace.
 */
function prepareVisualizationData(
  data: VisualizationData,
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
  const edgeTraces = buildEdgeTraces(nodes, edges);
  return {
    status: "ready",
    message: "",
    plotData: [...edgeTraces, nodeTrace],
  };
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
  const [plotData, setPlotData] = useState<Array<EdgeTrace | NodeTrace>>([]);
  const [status, setStatus] = useState<VisualizationStatus>("loading");
  const [message, setMessage] = useState("Loading visualization...");

  useEffect(() => {
    if (!data) {
      setPlotData([]);
      setStatus("empty");
      setMessage("No visualization data available.");
      return;
    }
    const preparation = prepareVisualizationData(data);
    setPlotData(preparation.plotData);
    setStatus(preparation.status);
    setMessage(preparation.message);
  }, [data]);

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
    <div className="w-full h-[800px]">
      <Plot
        data={plotData as any}
        layout={{
          title: "3D Asset Relationship Network",
          showlegend: false,
          scene: {
            xaxis: { showgrid: false, zeroline: false, showticklabels: false },
            yaxis: { showgrid: false, zeroline: false, showticklabels: false },
            zaxis: { showgrid: false, zeroline: false, showticklabels: false },
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
      />
    </div>
  );
}
