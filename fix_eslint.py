import re

with open('frontend/app/components/NetworkVisualization.tsx', 'r') as f:
    content = f.read()

# Replace useEffect with useMemo
content = content.replace(
"""  const [plotData, setPlotData] = useState<Array<EdgeTrace | NodeTrace>>([]);
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
  }, [data]);""",
"""  const { plotData, status, message } = useMemo(() => {
    if (!data) {
      return {
        plotData: [],
        status: "empty" as VisualizationStatus,
        message: "No visualization data available.",
      };
    }
    return prepareVisualizationData(data);
  }, [data]);"""
)

# Add useMemo to imports if missing
if 'useMemo' not in content:
    content = content.replace('useState', 'useState, useMemo')

with open('frontend/app/components/NetworkVisualization.tsx', 'w') as f:
    f.write(content)

with open('frontend/app/page.tsx', 'r') as f:
    content = f.read()

content = content.replace(
"""  useEffect(() => {
    loadData();
  }, [loadData]);""",
"""  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    loadData();
  }, [loadData]);"""
)

with open('frontend/app/page.tsx', 'w') as f:
    f.write(content)
