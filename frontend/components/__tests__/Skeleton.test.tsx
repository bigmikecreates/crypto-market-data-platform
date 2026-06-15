import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";
import { SkeletonBox, SkeletonText, SkeletonChart, SkeletonTable } from "../Skeleton";

describe("SkeletonBox", () => {
  it("renders with custom className", () => {
    const { container } = render(<SkeletonBox className="h-10 w-20" />);
    const el = container.firstChild as HTMLElement;
    expect(el.className).toContain("h-10");
    expect(el.className).toContain("w-20");
    expect(el.className).toContain("animate-pulse");
  });
});

describe("SkeletonText", () => {
  it("renders the specified number of lines", () => {
    const { container } = render(<SkeletonText lines={3} />);
    const lines = container.querySelectorAll(".animate-pulse");
    expect(lines.length).toBe(3);
  });
});

describe("SkeletonChart", () => {
  it("renders without crashing", () => {
    const { container } = render(<SkeletonChart />);
    expect(container.firstChild).toBeDefined();
  });
});

describe("SkeletonTable", () => {
  it("renders the specified number of rows", () => {
    const { container } = render(<SkeletonTable rows={4} cols={5} />);
    const rows = container.querySelectorAll(".flex.gap-3");
    expect(rows.length).toBe(5);
  });
});
