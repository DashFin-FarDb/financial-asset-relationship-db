"use client";

import React, { useEffect, useState, useCallback } from "react";
import { api } from "./lib/api";
import NetworkVisualization from "./components/NetworkVisualization";
import MetricsDashboard from "./components/MetricsDashboard";
import AssetList from "./components/AssetList";
import type { Metrics, VisualizationData } from "./types/api";

type HomeTab = "visualization" | "metrics" | "assets";

type HomeContentProps = Readonly<{
  loading: boolean;
  error: string | null;
  activeTab: HomeTab;
  vizData: VisualizationData | null;
  metrics: Metrics | null;
  onRetry: () => void;
}>;

type TabNavigationProps = Readonly<{
  activeTab: HomeTab;
  onTabChange: (tab: HomeTab) => void;
}>;

type TabDefinition = Readonly<{
  key: HomeTab;
  label: string;
}>;

const TAB_DEFINITIONS: readonly TabDefinition[] = [
  { key: "visualization", label: "3D Visualization" },
  { key: "metrics", label: "Metrics & Analytics" },
  { key: "assets", label: "Asset Explorer" },
];

const ACTIVE_TAB_CLASS = "border-blue-500 text-blue-600";
const INACTIVE_TAB_CLASS =
  "border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300";

/**
 * Builds the CSS class string for a tab according to its active state.
 *
 * @param isActive - If `true`, include the active tab class fragment; otherwise include the inactive fragment.
 * @returns The combined CSS class string to apply to a tab element.
 */
function getTabClassName(isActive: boolean): string {
  return `py-4 px-2 border-b-2 font-medium text-sm transition-colors ${
    isActive ? ACTIVE_TAB_CLASS : INACTIVE_TAB_CLASS
  }`;
}

/**
 * Render the home page's tabbed content area based on loading, error, and the active tab.
 *
 * When `loading` is true, shows a loading indicator; when `error` is set, shows an error panel with a retry action;
 * otherwise renders the content for the active tab ("visualization", "metrics", or "assets").
 *
 * @returns The JSX element for the content area, or `null` if no content is applicable.
 */
function HomeContent({
  loading,
  error,
  activeTab,
  vizData,
  metrics,
  onRetry,
}: HomeContentProps) {
  if (loading) {
    return (
      <div className="text-center py-12">
        <div className="inline-block animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600" />
        <p className="mt-4 text-gray-600">Loading data...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-lg p-6 text-center">
        <p className="text-red-800">{error}</p>
        <button
          onClick={onRetry}
          className="mt-4 px-4 py-2 bg-red-600 text-white rounded-md hover:bg-red-700 transition-colors"
        >
          Retry
        </button>
      </div>
    );
  }

  if (activeTab === "visualization" && vizData) {
    return (
      <div className="bg-white rounded-lg shadow-lg p-6">
        <NetworkVisualization data={vizData} />
      </div>
    );
  }

  if (activeTab === "metrics" && metrics) {
    return <MetricsDashboard metrics={metrics} />;
  }

  if (activeTab === "assets") {
    return <AssetList />;
  }

  return null;
}

/**
 * Renders the top tab navigation bar for switching between home tabs.
 *
 * @param activeTab - The currently active tab key.
 * @param onTabChange - Callback invoked with the selected tab key when a tab is clicked.
 * @returns A JSX element containing the tab buttons with appropriate active/inactive styling.
 */
function TabNavigation({ activeTab, onTabChange }: TabNavigationProps) {
  return (
    <nav className="bg-white border-b border-gray-200">
      <div className="container mx-auto px-4">
        <div className="flex space-x-8">
          {TAB_DEFINITIONS.map((tab) => (
            <button
              key={tab.key}
              onClick={() => onTabChange(tab.key)}
              className={getTabClassName(activeTab === tab.key)}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>
    </nav>
  );
}

/**
 * Render the dashboard home page with a tabbed interface for Visualization, Metrics, and Assets.
 *
 * Loads metrics and visualization data on mount, displays loading and error states, and exposes a retry action.
 *
 * @returns The top-level JSX element for the home page
 */
export default function Home() {
  const [activeTab, setActiveTab] = useState<HomeTab>("visualization");
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [vizData, setVizData] = useState<VisualizationData | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  /**
   * Loads metrics and visualization data from the API.
   * Sets loading states during fetch and handles errors by logging and setting error message.
   */
  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const [metricsData, visualizationData] = await Promise.all([
        api.getMetrics(),
        api.getVisualizationData(),
      ]);

      setMetrics(metricsData);
      setVizData(visualizationData);
    } catch (err) {
      if (process.env.NODE_ENV === "production") {
        console.error("Error loading data");
      } else {
        console.error("Error loading data:", err);
      }
      setError("Failed to load data. Please ensure the API server is running.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleTabChange = useCallback((tab: HomeTab) => {
    setActiveTab(tab);
  }, []);

  return (
    <main className="min-h-screen bg-gradient-to-b from-gray-50 to-gray-100">
      {/* Header */}
      <header className="bg-white shadow-md">
        <div className="container mx-auto px-4 py-6">
          <h1 className="text-3xl font-bold text-gray-800">
            🏦 Financial Asset Relationship Network
          </h1>
          <p className="text-gray-600 mt-2">
            Interactive 3D visualization of interconnected financial assets
          </p>
        </div>
      </header>

      {/* Navigation */}
      <TabNavigation activeTab={activeTab} onTabChange={handleTabChange} />

      {/* Content */}
      <div className="container mx-auto px-4 py-8">
        <HomeContent
          loading={loading}
          error={error}
          activeTab={activeTab}
          vizData={vizData}
          metrics={metrics}
          onRetry={loadData}
        />
      </div>

      {/* Footer */}
      <footer className="bg-white border-t border-gray-200 mt-12">
        <div className="container mx-auto px-4 py-6 text-center text-gray-600 text-sm">
          <p>
            Financial Asset Relationship Database - Powered by Next.js & FastAPI
          </p>
        </div>
      </footer>
    </main>
  );
}
