"use client";

import React, { useEffect, useState, useCallback, useRef } from "react";
import { api } from "./lib/api";
import NetworkVisualization from "./components/NetworkVisualization";
import InstitutionalDemo from "./components/InstitutionalDemo";
import MetricsDashboard from "./components/MetricsDashboard";
import AssetList from "./components/AssetList";
import type { Metrics, VisualizationData } from "./types/api";

type HomeTab = "demonstrator" | "visualization" | "metrics" | "assets";

type HomeContentProps = Readonly<{
  loading: boolean;
  error: string | null;
  activeTab: HomeTab;
  vizData: VisualizationData | null;
  metrics: Metrics | null;
  metricsError: string | null;
  visualizationError: string | null;
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
  { key: "demonstrator", label: "GRAC Demonstrator" },
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
 * The demonstrator renders immediately; data-dependent tabs show loading and error states as needed.
 * When `error` is set and no data is retained, shows an error panel with a retry action; otherwise renders the active tab
 * ("demonstrator", "visualization", "metrics", or "assets") preserving retained data on refresh failures.
 *
 * @returns The JSX element for the content area, or `null` if no content is applicable.
 */
function HomeContent({
  loading,
  error,
  activeTab,
  vizData,
  metrics,
  metricsError,
  visualizationError,
  onRetry,
}: HomeContentProps) {
  const tabPanelProps = {
    role: "tabpanel" as const,
    id: `tabpanel-${activeTab}`,
    "aria-labelledby": `tab-${activeTab}`,
    tabIndex: 0,
  };

  if (activeTab === "demonstrator") {
    return (
      <div {...tabPanelProps}>
        <InstitutionalDemo
          data={vizData}
          isGraphLoading={loading && vizData === null}
          isGraphStale={Boolean(visualizationError) && vizData !== null}
          graphError={error ?? visualizationError}
          onRetry={onRetry}
        />
      </div>
    );
  }

  if (activeTab === "assets") {
    return (
      <div {...tabPanelProps}>
        <AssetList />
      </div>
    );
  }

  if (activeTab === "visualization" && loading && !vizData) {
    return (
      <div {...tabPanelProps} className="text-center py-12">
        <div className="inline-block animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600" />
        <p className="mt-4 text-gray-600">Loading data...</p>
      </div>
    );
  }

  if (activeTab === "metrics" && loading && !metrics) {
    return (
      <div {...tabPanelProps} className="text-center py-12">
        <div className="inline-block animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600" />
        <p className="mt-4 text-gray-600">Loading data...</p>
      </div>
    );
  }

  if (error && !vizData && !metrics) {
    return (
      <div
        {...tabPanelProps}
        className="bg-red-50 border border-red-200 rounded-lg p-6 text-center"
      >
        <p className="text-red-800">{error}</p>
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

  if (activeTab === "visualization") {
    return (
      <div {...tabPanelProps} className="bg-white rounded-lg shadow-lg p-6">
        {vizData ? (
          <>
            {visualizationError && (
              <div className="mb-4 flex items-center justify-between gap-4 rounded-md border border-amber-200 bg-amber-50 p-4">
                <p className="text-sm text-amber-700" role="status">
                  The latest refresh failed — showing the last successfully
                  loaded graph.
                </p>
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
          </>
        ) : (
          <div className="text-center py-12 text-gray-600" role="alert">
            <p>
              {error ??
                visualizationError ??
                "Visualization data is unavailable."}
            </p>
            <div>
              <button
                type="button"
                onClick={onRetry}
                className="mt-4 px-4 py-2 bg-gray-800 text-white rounded-md hover:bg-gray-900 transition-colors"
              >
                Retry
              </button>
            </div>
          </div>
        )}
      </div>
    );
  }

  if (activeTab === "metrics") {
    return (
      <div {...tabPanelProps} className="bg-white rounded-lg shadow-lg p-6">
        {metrics ? (
          <>
            {metricsError && (
              <div className="mb-4 flex items-center justify-between gap-4 rounded-md border border-amber-200 bg-amber-50 p-4">
                <p className="text-sm text-amber-700" role="status">
                  The latest refresh failed — showing the last successfully
                  loaded metrics.
                </p>
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
          </>
        ) : (
          <div className="text-center py-12 text-gray-600" role="alert">
            <p>{error ?? metricsError ?? "Metrics data is unavailable."}</p>
            <div>
              <button
                type="button"
                onClick={onRetry}
                className="mt-4 px-4 py-2 bg-gray-800 text-white rounded-md hover:bg-gray-900 transition-colors"
              >
                Retry
              </button>
            </div>
          </div>
        )}
      </div>
    );
  }

  return <div {...tabPanelProps} />;
}

/**
 * Renders the top tab navigation bar for switching between home tabs.
 *
 * @param activeTab - The currently active tab key.
 * @param onTabChange - Callback invoked with the selected tab key when a tab is clicked.
 * @returns A JSX element containing the tab buttons with appropriate active/inactive styling.
 */
function TabNavigation({ activeTab, onTabChange }: TabNavigationProps) {
  const tabRefs = useRef<Partial<Record<HomeTab, HTMLButtonElement>>>({});

  const handleTabKeyDown = (event: React.KeyboardEvent<HTMLButtonElement>) => {
    const currentIndex = TAB_DEFINITIONS.findIndex(
      (tab) => tab.key === activeTab,
    );
    if (currentIndex < 0) return;

    let nextIndex: number | null = null;
    if (event.key === "ArrowRight") {
      nextIndex = (currentIndex + 1) % TAB_DEFINITIONS.length;
    } else if (event.key === "ArrowLeft") {
      nextIndex =
        (currentIndex - 1 + TAB_DEFINITIONS.length) % TAB_DEFINITIONS.length;
    } else if (event.key === "Home") {
      nextIndex = 0;
    } else if (event.key === "End") {
      nextIndex = TAB_DEFINITIONS.length - 1;
    }

    if (nextIndex === null) return;

    event.preventDefault();
    const nextTab = TAB_DEFINITIONS[nextIndex].key;
    onTabChange(nextTab);
    tabRefs.current[nextTab]?.focus();
  };

  return (
    <nav
      className="bg-white border-b border-gray-200"
      role="tablist"
      aria-label="Dashboard sections"
    >
      <div className="container mx-auto px-4">
        <div className="overflow-x-auto">
          <div className="flex min-w-max gap-x-8">
            {TAB_DEFINITIONS.map((tab) => (
              <button
                key={tab.key}
                onClick={() => onTabChange(tab.key)}
                className={getTabClassName(activeTab === tab.key)}
                onKeyDown={handleTabKeyDown}
                role="tab"
                id={`tab-${tab.key}`}
                aria-controls={
                  activeTab === tab.key ? `tabpanel-${tab.key}` : undefined
                }
                aria-selected={activeTab === tab.key}
                tabIndex={activeTab === tab.key ? 0 : -1}
                ref={(node) => {
                  tabRefs.current[tab.key] = node ?? undefined;
                }}
                type="button"
              >
                {tab.label}
              </button>
            ))}
          </div>
        </div>
      </div>
    </nav>
  );
}

type DashboardDataResult = Readonly<{
  metricsData: Metrics | null;
  visualizationData: VisualizationData | null;
  error: string | null;
  metricsError: string | null;
  visualizationError: string | null;
  requestId: number;
}>;

/**
 * Owns dashboard data fetching, partial-failure handling, retry state, and
 * request ordering so the page component remains focused on presentation.
 */
function useDashboardData() {
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [vizData, setVizData] = useState<VisualizationData | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [metricsError, setMetricsError] = useState<string | null>(null);
  const [visualizationError, setVisualizationError] = useState<string | null>(
    null,
  );

  const requestIdRef = useRef(0);
  const mountedRef = useRef(true);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  const fetchDashboardData =
    useCallback(async (): Promise<DashboardDataResult> => {
      const requestId = ++requestIdRef.current;

      const metricsPromise = api
        .getMetrics()
        .then((value) => {
          if (
            requestId === requestIdRef.current &&
            mountedRef.current
          ) {
            setMetrics(value);
          }
          return { status: "fulfilled" as const, value };
        })
        .catch((reason) => ({ status: "rejected" as const, reason }));

      const visualizationPromise = api
        .getVisualizationData()
        .then((value) => {
          if (
            requestId === requestIdRef.current &&
            mountedRef.current
          ) {
            setVizData(value);
          }
          return { status: "fulfilled" as const, value };
        })
        .catch((reason) => ({ status: "rejected" as const, reason }));

      const [metricsResult, visualizationResult] = await Promise.all([
        metricsPromise,
        visualizationPromise,
      ]);

      const metricsData =
        metricsResult.status === "fulfilled" ? metricsResult.value : null;
      const visualizationData =
        visualizationResult.status === "fulfilled"
          ? visualizationResult.value
          : null;
      const metricsError =
        metricsResult.status === "rejected"
          ? "Failed to load metrics data."
          : null;
      const visualizationError =
        visualizationResult.status === "rejected"
          ? "Failed to load visualization data. Please ensure the API server is running."
          : null;

      if (
        metricsResult.status === "rejected" ||
        visualizationResult.status === "rejected"
      ) {
        if (process.env.NODE_ENV === "production") {
          console.error("Error loading dashboard data");
        } else {
          console.error("Error loading dashboard data:", {
            metrics:
              metricsResult.status === "rejected" ? metricsResult.reason : null,
            visualization:
              visualizationResult.status === "rejected"
                ? visualizationResult.reason
                : null,
          });
        }
      }

      return {
        metricsData,
        visualizationData,
        error:
          !metricsData && !visualizationData
            ? "Failed to load data. Please ensure the API server is running."
            : null,
        metricsError,
        visualizationError,
        requestId,
      };
    }, []);

  const applyResult = useCallback((result: DashboardDataResult) => {
    if (result.requestId !== requestIdRef.current || !mountedRef.current) {
      return;
    }

    if (result.error) {
      setError(result.error);
      setMetricsError(result.metricsError);
      setVisualizationError(result.visualizationError);
    } else {
      if (result.metricsData) {
        setMetrics(result.metricsData);
      }
      if (result.visualizationData) {
        setVizData(result.visualizationData);
      }
      setMetricsError(result.metricsError);
      setVisualizationError(result.visualizationError);
      setError(null);
    }

    setLoading(false);
  }, []);

  useEffect(() => {
    const load = async () => {
      const result = await fetchDashboardData();
      applyResult(result);
    };
    load();
  }, [fetchDashboardData, applyResult]);

  const handleRetry = useCallback(async () => {
    setLoading(true);
    setError(null);
    setMetricsError(null);
    setVisualizationError(null);
    const result = await fetchDashboardData();
    applyResult(result);
  }, [fetchDashboardData, applyResult]);

  return {
    metrics,
    vizData,
    loading,
    error,
    metricsError,
    visualizationError,
    onRetry: handleRetry,
  };
}

/**
 * Render the dashboard home page with a tabbed interface for the GRAC demonstrator, Visualization, Metrics, and Assets.
 *
 * Loads metrics and visualization data independently on mount, displays loading and bounded per-tab error states, and exposes a retry action.
 *
 * @returns The top-level JSX element for the home page
 */
export default function Home() {
  const [activeTab, setActiveTab] = useState<HomeTab>("demonstrator");
  const {
    metrics,
    vizData,
    loading,
    error,
    metricsError,
    visualizationError,
    onRetry,
  } = useDashboardData();
  const handleTabChange = useCallback((tab: HomeTab) => {
    setActiveTab(tab);
  }, []);

  return (
    <main className="min-h-screen bg-gradient-to-b from-gray-50 to-gray-100">
      {/* Header */}
      <header className="bg-white shadow-md">
        <div className="container mx-auto px-4 py-6">
          <h1 className="text-3xl font-bold text-gray-800">
            FarDb — Financial Asset Relationship Database
          </h1>
          <p className="text-gray-600 mt-2">
            Governed relationship infrastructure with an institutional
            demonstration surface
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
          metricsError={metricsError}
          visualizationError={visualizationError}
          onRetry={onRetry}
        />
      </div>

      {/* Footer */}
      <footer className="bg-white border-t border-gray-200 mt-12">
        <div className="container mx-auto px-4 py-6 text-center text-gray-600 text-sm">
          <p>FarDb — Governed Relationship Assertion Contract demonstrator</p>
        </div>
      </footer>
    </main>
  );
}
