'use client';

import React, { useEffect, useState } from 'react';
import dynamic from 'next/dynamic';
import type { VisualizationData } from '../types/api';

// Dynamically import Plotly to avoid SSR issues
const Plot = dynamic(() => import('react-plotly.js'), {
  ssr: false,
  loading: () => <div className="text-center p-8">Loading visualization...</div>
});

interface NetworkVisualizationProps {
  data: VisualizationData;
}

type EdgeTrace = {
  type: 'scatter3d';
  mode: 'lines';
  x: number[];
  y: number[];
  z: number[];
  line: {
    color: string;
    width: number;
  };
  hoverinfo: 'none';
  showlegend: false;
};

const MAX_NODES = Number(process.env.NEXT_PUBLIC_MAX_NODES) || 500;
const MAX_EDGES = Number(process.env.NEXT_PUBLIC_MAX_EDGES) || 2000;

/**
 * Display an interactive 3D network of assets from the provided visualization payload.
 *
 * @param data - Visualization payload containing `nodes` and `edges`.
 *   Nodes are objects with at least: `id`, `x`, `y`, `z`, `symbol`, `name`, `asset_class`, `size`, `color`.
 *   Edges are objects with at least: `source`, `target`, `relationship_type`, `strength`.
 * @returns A JSX element rendering the 3D network plot when data is valid, or a centred status message when data is missing, invalid or too large.
 */
export default function NetworkVisualization({ data }: NetworkVisualizationProps) {
const [plotData, setPlotData] = useState<(EdgeTrace | NodeTrace)[]>([]);
  const [status, setStatus] = useState<'loading' | 'ready' | 'empty' | 'tooLarge'>('loading');
  const [message, setMessage] = useState('Loading visualization...');

  useEffect(() => {
    if (!data) {
      setPlotData([]);
      setStatus('empty');
      setMessage('No visualization data available.');
      return;
    }

    const nodes = Array.isArray(data.nodes) ? data.nodes : [];
    const edges = Array.isArray(data.edges) ? data.edges : [];

    if (nodes.length === 0) {
      setPlotData([]);
      setStatus('empty');
      setMessage('Visualization data is missing nodes.');
      return;
    }

    if (nodes.length > MAX_NODES || edges.length > MAX_EDGES) {
      setPlotData([]);
      setStatus('tooLarge');
      setMessage(
        `Visualization is unavailable because the dataset is too large (${nodes.length} nodes, ${edges.length} edges). Maximum: ${MAX_NODES} nodes, ${MAX_EDGES} edges.`
      );
      return;
    }

    // Create node trace
    const nodeTrace = {
      type: 'scatter3d',
      mode: 'markers+text',
      x: nodes.map(n => n.x),
      y: nodes.map(n => n.y),
      z: nodes.map(n => n.z),
      text: nodes.map(n => n.symbol),
      hovertext: nodes.map(n => `${n.name} (${n.symbol})<br>Class: ${n.asset_class}`),
      hoverinfo: 'text',
      marker: {
        size: nodes.map(n => n.size),
        color: nodes.map(n => n.color),
        line: {
          color: 'white',
          width: 0.5
        }
      },
      textposition: 'top center',
      textfont: {
        size: 8,
      }
    };

    // Create node lookup map for O(1) access
    const nodeMap = new Map(nodes.map(node => [node.id, node]));

    // Create edge traces with type predicate to filter nulls
    const edgeTraces = edges.reduce<EdgeTrace[]>((acc, edge) => {
      const sourceNode = nodeMap.get(edge.source);
      const targetNode = nodeMap.get(edge.target);

      if (!sourceNode || !targetNode) {
        return acc;
      }

      acc.push({
        type: 'scatter3d',
        mode: 'lines',
        x: [sourceNode.x, targetNode.x],
        y: [sourceNode.y, targetNode.y],
        z: [sourceNode.z, targetNode.z],
        line: {
          color: `rgba(125, 125, 125, ${edge.strength})`,
          width: edge.strength * 3
        },
        hoverinfo: 'none',
        showlegend: false
      });

      return acc;
    }, []);

    setPlotData([...edgeTraces, nodeTrace]);
    setStatus('ready');
    setMessage('');
  }, [data]);

  if (status !== 'ready') {
    return (
      <div className="text-center p-8 text-gray-600" role={status === 'tooLarge' ? 'alert' : 'status'}>
        {message}
      </div>
    );
  }

  return (
    <div className="w-full h-[800px]">
      <Plot
        data={plotData}
        layout={{
          title: '3D Asset Relationship Network',
          showlegend: false,
          scene: {
            xaxis: { showgrid: false, zeroline: false, showticklabels: false },
            yaxis: { showgrid: false, zeroline: false, showticklabels: false },
            zaxis: { showgrid: false, zeroline: false, showticklabels: false },
            camera: {
              eye: { x: 1.5, y: 1.5, z: 1.5 }
            }
          },
          hovermode: 'closest',
          margin: { l: 0, r: 0, b: 0, t: 40 },
          paper_bgcolor: 'rgba(0,0,0,0)',
          plot_bgcolor: 'rgba(0,0,0,0)'
        }}
        config={{
          displayModeBar: true,
          displaylogo: false,
          responsive: true
        }}
        style={{ width: '100%', height: '100%' }}
      />
    </div>
  );
}
