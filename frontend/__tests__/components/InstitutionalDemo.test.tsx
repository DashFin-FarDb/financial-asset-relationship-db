import React from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import "@testing-library/jest-dom";
import InstitutionalDemo from "../../app/components/InstitutionalDemo";
import { mockVisualizationData } from "../test-utils";

jest.mock("../../app/components/NetworkVisualization", () => ({
  __esModule: true,
  default: () => <div data-testid="network-visualization" />,
}));

describe("InstitutionalDemo", () => {
  it("presents the synthetic governance walkthrough and live graph separately", () => {
    render(<InstitutionalDemo data={null} />);

    expect(
      screen.getByText("FarDb Institutional Demonstrator"),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Synthetic governance walkthrough"),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        /synthetic and are not presented as live FarDb customer data/,
      ),
    ).toBeInTheDocument();
    expect(screen.getByTestId("network-visualization")).toBeInTheDocument();
  });

  it("shows a loading state instead of an empty graph while data is pending", () => {
    render(<InstitutionalDemo data={null} isGraphLoading={true} />);

    expect(
      screen.getByText("Loading relationship graph..."),
    ).toBeInTheDocument();
    expect(
      screen.queryByTestId("network-visualization"),
    ).not.toBeInTheDocument();
    expect(
      screen.getByText("Loading the latest FarDb relationship graph..."),
    ).toBeInTheDocument();
  });

  it("shows a stale graph notice when the latest refresh fails", () => {
    render(
      <InstitutionalDemo
        data={mockVisualizationData}
        isGraphStale={true}
      />,
    );

    expect(
      screen.getByText(
        "The latest refresh failed — showing the last successfully loaded graph.",
      ),
    ).toBeInTheDocument();
    expect(screen.getByTestId("network-visualization")).toBeInTheDocument();
  });

  it("moves through the synthetic lifecycle without changing the data contract", () => {
    render(<InstitutionalDemo data={null} />);

    expect(
      screen.getByRole("button", {
        name: "Show Governance determination (12 May 2026)",
      }),
    ).toBeInTheDocument();
    expect(screen.getByText("Accepted")).toBeInTheDocument();

    fireEvent.click(
      screen.getByRole("button", { name: "Show Supersession (26 Aug 2026)" }),
    );

    expect(
      screen.getByRole("button", { name: "Show Supersession (26 Aug 2026)" }),
    ).toHaveAttribute("aria-current", "step");
    expect(screen.getByText("Superseded")).toBeInTheDocument();
    expect(screen.getAllByText("26 Aug 2026")).toHaveLength(2);
  });
});
