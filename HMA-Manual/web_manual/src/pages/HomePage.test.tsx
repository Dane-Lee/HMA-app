import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { HomePage } from "./HomePage";

const apiMocks = vi.hoisted(() => ({
  listAssessments: vi.fn(async () => [])
}));

vi.mock("../lib/api", () => ({
  listAssessments: apiMocks.listAssessments
}));

describe("HomePage", () => {
  it("presents the manual workflow without automatic scoring surfaces", async () => {
    render(
      <MemoryRouter>
        <HomePage />
      </MemoryRouter>
    );

    expect(await screen.findByRole("heading", { name: /begin hma-manual/i })).toBeInTheDocument();
    expect(screen.queryByText(/AI assisted/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Analyze capture/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/pose overlay/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/calibration/i)).not.toBeInTheDocument();
  });
});
