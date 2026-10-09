"use client";

import React, { useEffect, useState, useCallback, useRef } from "react";
import { api } from "./lib/api";
import NetworkVisualization from "./components/NetworkVisualization";
import MetricsDashboard from "./components/MetricsDashboard";
import AssetList from "./components/AssetList";
import type { Metrics, VisualizationData } from "./types/api";

type HomeTab = "visualization" | "metrics" | "assets";

type HomeContentProps = Readonly<{
  activeTab: HomeTab;
  vizData: VisualizationData | null;
  metrics: Metrics | null;
  visualizationLoading: boolean;
  metricsLoading: boolean;
  visualizationError: string | null;
  metricsError: string | null;
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
 * Render the home page's tabbed content area with per-resource loading, data, and error states.
 *
 * Each resource (visualization, metrics) is rendered independently from its own lifecycle.
 * A global error is shown only when neither resource has usable data.
 *
 * @returns The JSX element for the content area, or `null` if no content is applicable.
 */
function HomeContent({
  activeTab,
  vizData,
  metrics,
  visualizationLoading,
  metricsLoading,
  visualizationError,
  metricsError,
  onRetry,
}: HomeContentProps) {
  if (activeTab === "visualization") {
    if (visualizationLoading && !vizData) {
      return (
        <div className="text-center py-12">
          <div className="inline-block animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600" />
          <p className="mt-4 text-gray-600">Loading data...</p>
        </div>
      );
    }

    if (visualizationError && !vizData) {
      return (
        <div className="bg-red-50 border border-red-200 rounded-lg p-6 text-center">
          <p className="text-red-800">{visualizationError}</p>
          <button
            type="button"
            onClick={onRetry}
            className="mt-4 px-4 py-2 bg-red-600 text-white rounded-md hover:bg-red-700 transition-colors"
          >
            Retry
          </button>
        </div>
      );
    }

    if (vizData) {
      return (
        <div className="bg-white rounded-lg shadow-lg p-6">
          {visualizationError && (
            <div className="mb-4 flex items-center justify-between gap-4 rounded-md border border-amber-200 bg-amber-50 p-4">
              <output className="block text-sm text-amber-700">
                The latest refresh failed — showing the last successfully loaded
                graph.
              </output>
              <button
                type="button"
                onClick={onRetry}
                className="px-3 py-1 text-xs font-medium bg-amber-600 text-white rounded hover:bg-amber-700 transition-colors"
              >
                Retry
              </button>
            </div>
          )}
          <NetworkVisualization data={vizData} />
        </div>
      );
    }
  }

  if (activeTab === "metrics") {
    if (metricsLoading && !metrics) {
      return (
        <div className="text-center py-12">
          <div className="inline-block animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600" />
          <p className="mt-4 text-gray-600">Loading data...</p>
        </div>
      );
    }

    if (metricsError && !metrics) {
      return (
        <div className="bg-red-50 border border-red-200 rounded-lg p-6 text-center">
          <p className="text-red-800">{metricsError}</p>
          <button
            type="button"
            onClick={onRetry}
            className="mt-4 px-4 py-2 bg-red-600 text-white rounded-md hover:bg-red-700 transition-colors"
          >
            Retry
          </button>
        </div>
      );
    }

    if (metrics) {
      return (
        <div>
          {metricsError && (
            <div className="mb-4 flex items-center justify-between gap-4 rounded-md border border-amber-200 bg-amber-50 p-4">
              <output className="block text-sm text-amber-700">
                The latest refresh failed — showing the last successfully loaded
                metrics.
              </output>
              <button
                type="button"
                onClick={onRetry}
                className="px-3 py-1 text-xs font-medium bg-amber-600 text-white rounded hover:bg-amber-700 transition-colors"
              >
                Retry
              </button>
            </div>
          )}
          <MetricsDashboard metrics={metrics} />
        </div>
      );
    }
  }

  if (activeTab === "assets") {
    return <AssetList />;
  }

  const showGenericError =
    !vizData &&
    !metrics &&
    !visualizationLoading &&
    !metricsLoading &&
    (visualizationError || metricsError);

  if (showGenericError) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-lg p-6 text-center">
        <p className="text-red-800">
          Failed to load data. Please ensure the API server is running.
        </p>
        <button
          type="button"
          onClick={onRetry}
          className="mt-4 px-4 py-2 bg-red-600 text-white rounded-md hover:bg-red-700 transition-colors"
        >
          Retry
        </button>
      </div>
    );
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
              type="button"
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
 * Manages dashboard data fetching with independent per-resource request tracking.
 * Each resource (metrics, visualization) has its own loading and error state,
 * allowing one to fail or remain pending without blocking the other.
 */
function useDashboardData() {
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [vizData, setVizData] = useState<VisualizationData | null>(null);
  const [metricsLoading, setMetricsLoading] = useState(true);
  const [visualizationLoading, setVisualizationLoading] = useState(true);
  const [metricsError, setMetricsError] = useState<string | null>(null);
  const [visualizationError, setVisualizationError] = useState<string | null>(
    null,
  );

  const metricsRequestIdRef = useRef(0);
  const visualizationRequestIdRef = useRef(0);
  const mountedRef = useRef(true);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  const fetchMetrics = useCallback(async () => {
    const requestId = ++metricsRequestIdRef.current;
    setMetricsLoading(true);
    setMetricsError(null);

    try {
      const result = await api.getMetrics();
      if (!mountedRef.current || requestId !== metricsRequestIdRef.current) {
        return;
      }
      setMetrics(result);
      setMetricsError(null);
    } catch (error) {
      if (!mountedRef.current || requestId !== metricsRequestIdRef.current) {
        return;
      }
      if (process.env.NODE_ENV === "production") {
        console.error("Error loading metrics");
      } else {
        console.error("Error loading metrics:", error);
      }
      setMetricsError("Failed to load metrics data.");
    } finally {
      if (mountedRef.current && requestId === metricsRequestIdRef.current) {
        setMetricsLoading(false);
      }
    }
  }, []);

  const fetchVisualization = useCallback(async () => {
    const requestId = ++visualizationRequestIdRef.current;
    setVisualizationLoading(true);
    setVisualizationError(null);

    try {
      const result = await api.getVisualizationData();
      if (!mountedRef.current || requestId !== visualizationRequestIdRef.current) {
        return;
      }
      setVizData(result);
      setVisualizationError(null);
    } catch (error) {
      if (!mountedRef.current || requestId !== visualizationRequestIdRef.current) {
        return;
      }
      if (process.env.NODE_ENV === "production") {
        console.error("Error loading visualization");
      } else {
        console.error("Error loading visualization:", error);
      }
      setVisualizationError(
        "Failed to load visualization data. Please ensure the API server is running.",
      );
    } finally {
      if (
        mountedRef.current &&
        requestId === visualizationRequestIdRef.current
      ) {
        setVisualizationLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    void fetchMetrics();
    void fetchVisualization();
  }, [fetchMetrics, fetchVisualization]);

  const handleRetry = useCallback(async () => {
    await Promise.all([fetchMetrics(), fetchVisualization()]);
  }, [fetchMetrics, fetchVisualization]);

  return {
    metrics,
    vizData,
    metricsLoading,
    visualizationLoading,
    metricsError,
    visualizationError,
    onRetry: handleRetry,
  };
}

/**
 * Render the dashboard home page with a tabbed interface for Visualization, Metrics, and Assets.
 *
 * Loads metrics and visualization data independently on mount, displays per-resource loading
 * and error states, and exposes a retry action.
 *
 * @returns The top-level JSX element for the home page
 */
export default function Home() {
  const [activeTab, setActiveTab] = useState<HomeTab>("visualization");
  const {
    metrics,
    vizData,
    metricsLoading,
    visualizationLoading,
    metricsError,
    visualizationError,
    onRetry,
  } = useDashboardData();

  const handleTabChange = useCallback((tab: HomeTab) => {
    setActiveTab(tab);
  }, []);

  return (
    <main className="min-h-screen bg-gradient-to-b from-gray-50 to-gray-100">
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

      <TabNavigation activeTab={activeTab} onTabChange={handleTabChange} />

      <div className="container mx-auto px-4 py-8">
        <HomeContent
          activeTab={activeTab}
          vizData={vizData}
          metrics={metrics}
          visualizationLoading={visualizationLoading}
          metricsLoading={metricsLoading}
          visualizationError={visualizationError}
          metricsError={metricsError}
          onRetry={onRetry}
        />
      </div>

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
