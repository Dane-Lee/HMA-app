import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { SelfStartPage } from "./SelfStartPage";

const apiMocks = vi.hoisted(() => ({
  consumeMagicLink: vi.fn()
}));

vi.mock("../lib/api", () => ({
  consumeMagicLink: apiMocks.consumeMagicLink
}));

describe("SelfStartPage", () => {
  beforeEach(() => {
    apiMocks.consumeMagicLink.mockReset();
  });

  it("redirects to /self/home after successful link exchange", async () => {
    apiMocks.consumeMagicLink.mockResolvedValue({
      ok: true,
      employee: {
        id: "e1",
        name: "Jamie",
        email: null,
        employer: "Hendrickson",
        created_at: "2026-04-30T00:00:00+00:00",
        notes: null
      }
    });

    render(
      <MemoryRouter initialEntries={["/self/start/abc123"]}>
        <Routes>
          <Route path="/self/start/:token" element={<SelfStartPage />} />
          <Route path="/self/home" element={<p>Home placeholder</p>} />
        </Routes>
      </MemoryRouter>
    );

    expect(await screen.findByText(/home placeholder/i)).toBeInTheDocument();
    expect(apiMocks.consumeMagicLink).toHaveBeenCalledWith("abc123");
  });

  it("shows an error state when the link is invalid", async () => {
    apiMocks.consumeMagicLink.mockRejectedValue(new Error("Link is invalid or expired."));

    render(
      <MemoryRouter initialEntries={["/self/start/badtoken"]}>
        <Routes>
          <Route path="/self/start/:token" element={<SelfStartPage />} />
        </Routes>
      </MemoryRouter>
    );

    expect(await screen.findByRole("heading", { name: /can't open this link/i })).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByText(/Link is invalid or expired\./)).toBeInTheDocument();
    });
  });
});
