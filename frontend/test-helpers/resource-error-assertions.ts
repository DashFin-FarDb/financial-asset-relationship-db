import "@testing-library/jest-dom";
import { fireEvent, screen, waitFor } from "@testing-library/react";

export async function expectVisualizationFailureAndMetricsAvailable() {
  await waitFor(() => {
    expect(
      screen.getByText(
        "Failed to load visualization data. Please ensure the API server is running.",
      ),
    ).toBeInTheDocument();
  });

  fireEvent.click(screen.getByRole("button", { name: "Metrics & Analytics" }));
  expect(screen.getByTestId("metrics-dashboard")).toBeInTheDocument();
}
