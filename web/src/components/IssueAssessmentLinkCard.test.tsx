import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { IssueAssessmentLinkCard } from "./IssueAssessmentLinkCard";

const apiMocks = vi.hoisted(() => ({
  createEmployee: vi.fn(),
  issueMagicLink: vi.fn()
}));

vi.mock("../lib/api", () => ({
  createEmployee: apiMocks.createEmployee,
  issueMagicLink: apiMocks.issueMagicLink
}));

describe("IssueAssessmentLinkCard", () => {
  beforeEach(() => {
    apiMocks.createEmployee.mockReset();
    apiMocks.issueMagicLink.mockReset();
  });

  it("issues a link and shows the URL with a copy button", async () => {
    apiMocks.createEmployee.mockResolvedValue({
      id: "e1",
      name: "Jamie",
      email: null,
      employer: "Hendrickson",
      created_at: "2026-04-30T00:00:00+00:00",
      notes: null
    });
    apiMocks.issueMagicLink.mockResolvedValue({
      url: "http://localhost:5181/self/start/abc123",
      expires_at: "2026-05-07T00:00:00+00:00"
    });

    render(<IssueAssessmentLinkCard />);

    fireEvent.change(screen.getByLabelText(/^name$/i), { target: { value: "Jamie" } });
    fireEvent.change(screen.getByLabelText(/^employer$/i), {
      target: { value: "Hendrickson" }
    });
    fireEvent.click(screen.getByRole("button", { name: /issue link/i }));

    expect(await screen.findByText(/Link for Jamie/)).toBeInTheDocument();
    expect(screen.getByText("http://localhost:5181/self/start/abc123")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /copy link/i })).toBeInTheDocument();
    expect(apiMocks.createEmployee).toHaveBeenCalledWith({
      name: "Jamie",
      employer: "Hendrickson",
      email: undefined
    });
    expect(apiMocks.issueMagicLink).toHaveBeenCalledWith("e1");
  });

  it("surfaces a server error without showing a link", async () => {
    apiMocks.createEmployee.mockRejectedValue(new Error("Server boom"));

    render(<IssueAssessmentLinkCard />);

    fireEvent.change(screen.getByLabelText(/^name$/i), { target: { value: "Jamie" } });
    fireEvent.change(screen.getByLabelText(/^employer$/i), {
      target: { value: "Hendrickson" }
    });
    fireEvent.click(screen.getByRole("button", { name: /issue link/i }));

    expect(await screen.findByText(/Server boom/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /copy link/i })).not.toBeInTheDocument();
  });
});
