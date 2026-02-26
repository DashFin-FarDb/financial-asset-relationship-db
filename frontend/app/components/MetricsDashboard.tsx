"use client";

import React from "react";
import type { Metrics } from "../types/api";

interface MetricsDashboardProps {
  metrics: Metrics;
}

/**
 * Renders a responsive dashboard of six metric panels based on the provided metrics.
 *
 * Displays Total Assets, Total Relationships, Network Density (as a percentage),
 * Average Degree, Max Degree, and a list of Asset Classes with counts in a 1–3 column grid.
 *
 * @param props.metrics - Object containing metric values:
 *   - `total_assets`: total number of assets
 *   - `total_relationships`: total number of relationships
 *   - `network_density`: density value in the range 0–1 (rendered as percentage)
 *   - `avg_degree`: average node degree
 *   - `max_degree`: maximum node degree
 *   - `asset_classes`: record mapping asset class names to counts
 * @returns The JSX element that renders the metrics dashboard UI
 */
export default function MetricsDashboard({ metrics }: MetricsDashboardProps) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
      <div className="bg-white rounded-lg shadow-md p-6">
        <h3 className="text-lg font-semibold text-gray-700 mb-2">
          Total Assets
        </h3>
        <p className="text-3xl font-bold text-blue-600">
          {metrics.total_assets}
        </p>
      </div>

      <div className="bg-white rounded-lg shadow-md p-6">
        <h3 className="text-lg font-semibold text-gray-700 mb-2">
          Total Relationships
        </h3>
        <p className="text-3xl font-bold text-green-600">
          {metrics.total_relationships}
        </p>
      </div>

      <div className="bg-white rounded-lg shadow-md p-6">
        <h3 className="text-lg font-semibold text-gray-700 mb-2">
          Network Density
        </h3>
        <p className="text-3xl font-bold text-purple-600">
          {(metrics.network_density * 100).toFixed(2)}%
        </p>
      </div>

      <div className="bg-white rounded-lg shadow-md p-6">
        <h3 className="text-lg font-semibold text-gray-700 mb-2">
          Average Degree
        </h3>
        <p className="text-3xl font-bold text-orange-600">
          {metrics.avg_degree.toFixed(2)}
        </p>
      </div>

      <div className="bg-white rounded-lg shadow-md p-6">
        <h3 className="text-lg font-semibold text-gray-700 mb-2">Max Degree</h3>
        <p className="text-3xl font-bold text-red-600">{metrics.max_degree}</p>
      </div>

      <div className="bg-white rounded-lg shadow-md p-6">
        <h3 className="text-lg font-semibold text-gray-700 mb-2">
          Asset Classes
        </h3>
        <div className="space-y-1">
          {Object.entries(metrics.asset_classes).map(([className, count]) => (
            <div key={className} className="flex justify-between text-sm">
              <span className="text-gray-600">{className}:</span>
              <span className="font-semibold text-gray-800">{count}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
