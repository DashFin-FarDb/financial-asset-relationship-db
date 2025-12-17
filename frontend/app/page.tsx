'use client';

import React, { useEffect, useState } from 'react';
import { api } from './lib/api';
import NetworkVisualization from './components/NetworkVisualization';
import MetricsDashboard from './components/MetricsDashboard';
import AssetList from './components/AssetList';
import type { Metrics, VisualizationData } from './types/api';

/**
 * Renders the dashboard home page with a tabbed UI that loads metrics and visualization data,
 * shows loading and error states, and conditionally displays the 3D visualization, metrics dashboard, or asset explorer.
 *
 * The component fetches metrics and visualization data on mount, provides a retry action on failure,
 * and manages which tab is active.
 *
 * @returns The top-level JSX element for the home page.
 */
export default function Home() {
  const [activeTab, setActiveTab] = useState<'visualization' | 'metrics' | 'assets'>('visualization');
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [vizData, setVizData] = useState<VisualizationData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [metricsData, visualizationData] = await Promise.all([
        api.getMetrics(),
        api.getVisualizationData()
      ]);
      setMetrics(metricsData);
      setVizData(visualizationData);
    } catch (err) {
      console.error('Error loading data:', err);
      setError('Failed to load data. Please ensure the API server is running.');
    } finally {
      setLoading(false);
    }
  };

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
      <nav className="bg-white border-b border-gray-200">
        <div className="container mx-auto px-4">
          <div className="flex space-x-8">
            <button
              onClick={() => setActiveTab('visualization')}
              className={`py-4 px-2 border-b-2 font-medium text-sm transition-colors ${
                activeTab === 'visualization'
                  ? 'border-blue-500 text-blue-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              }`}
            >
              3D Visualization
            </button>
            <button
              onClick={() => setActiveTab('metrics')}
              className={`py-4 px-2 border-b-2 font-medium text-sm transition-colors ${
                activeTab === 'metrics'
                  ? 'border-blue-500 text-blue-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              }`}
            >
              Metrics & Analytics
            </button>
            <button
              onClick={() => setActiveTab('assets')}
              className={`py-4 px-2 border-b-2 font-medium text-sm transition-colors ${
                activeTab === 'assets'
                  ? 'border-blue-500 text-blue-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              }`}
            >
              Asset Explorer
            </button>
          </div>
        </div>
      </nav>

      {/* Content */}
      <div className="container mx-auto px-4 py-8">
        {loading && (
          <div className="text-center py-12">
            <div className="inline-block animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
            <p className="mt-4 text-gray-600">Loading data...</p>
          </div>
        )}

        {error && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-6 text-center">
            <p className="text-red-800">{error}</p>
            <button
              onClick={loadData}
              className="mt-4 px-4 py-2 bg-red-600 text-white rounded-md hover:bg-red-700 transition-colors"
            >
              Retry
            </button>
          </div>
        )}

        {!loading && !error && (
          <>
            {activeTab === 'visualization' && vizData && (
              <div className="bg-white rounded-lg shadow-lg p-6">
                <NetworkVisualization data={vizData} />
              </div>
            )}

            {activeTab === 'metrics' && metrics && (
              <MetricsDashboard metrics={metrics} />
            )}

            {activeTab === 'assets' && (
              <AssetList />
            )}
          </>
        )}
      </div>

      {/* Footer */}
      <footer className="bg-white border-t border-gray-200 mt-12">
        <div className="container mx-auto px-4 py-6 text-center text-gray-600 text-sm">
          <p>Financial Asset Relationship Database - Powered by Next.js & FastAPI</p>
        </div>
      </footer>
    </main>
  );
}
