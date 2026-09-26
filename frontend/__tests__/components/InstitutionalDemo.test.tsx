import React from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import "@testing-library/jest-dom";
import InstitutionalDemo from "../../app/components/InstitutionalDemo";

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
