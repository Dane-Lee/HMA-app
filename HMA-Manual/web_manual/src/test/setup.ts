import "@testing-library/jest-dom";
import { vi } from "vitest";

if (!URL.createObjectURL) {
  URL.createObjectURL = vi.fn(() => "blob:mock-url");
}

if (!URL.revokeObjectURL) {
  URL.revokeObjectURL = vi.fn();
}

HTMLCanvasElement.prototype.getContext = vi.fn(() => ({
  arc: vi.fn(),
  beginPath: vi.fn(),
  clearRect: vi.fn(),
  fill: vi.fn(),
  fillRect: vi.fn(),
  lineTo: vi.fn(),
  moveTo: vi.fn(),
  stroke: vi.fn(),
})) as unknown as HTMLCanvasElement["getContext"];
