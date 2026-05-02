import "@testing-library/jest-dom";
import { vi } from "vitest";

if (!URL.createObjectURL) {
  URL.createObjectURL = vi.fn(() => "blob:mock-url");
}

if (!URL.revokeObjectURL) {
  URL.revokeObjectURL = vi.fn();
}
