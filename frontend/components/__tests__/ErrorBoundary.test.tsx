import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import ErrorBoundary from "../ErrorBoundary";

function Bomb() {
  throw new Error("💥 crashed");
}

describe("ErrorBoundary", () => {
  beforeEach(() => {
    vi.spyOn(console, "error").mockImplementation(() => {});
  });

  it("renders children when no error", () => {
    render(
      <ErrorBoundary>
        <div>safe content</div>
      </ErrorBoundary>,
    );
    expect(screen.getByText("safe content")).toBeDefined();
  });

  function findByTextContent(text: string) {
    return screen.getByText((_: string, el: Element | null) => el?.textContent === text);
  }

  it("catches errors and shows fallback", () => {
    render(
      <ErrorBoundary name="TestComponent">
        <Bomb />
      </ErrorBoundary>,
    );
    expect(findByTextContent("TestComponent crashed")).toBeDefined();
    expect(screen.getByText("💥 crashed")).toBeDefined();
  });

  it("shows generic name when not provided", () => {
    render(
      <ErrorBoundary>
        <Bomb />
      </ErrorBoundary>,
    );
    expect(findByTextContent("Component crashed")).toBeDefined();
  });

  it("retry button resets error state", () => {
    let canRender = false;
    function ConditionalBomb() {
      if (!canRender) throw new Error("💥");
      return <div>recovered</div>;
    }

    const { rerender } = render(
      <ErrorBoundary name="Test">
        <ConditionalBomb />
      </ErrorBoundary>,
    );
    expect(findByTextContent("Test crashed")).toBeDefined();

    canRender = true;
    fireEvent.click(screen.getByText("Try again"));

    rerender(
      <ErrorBoundary name="Test">
        <ConditionalBomb />
      </ErrorBoundary>,
    );
    expect(screen.getByText("recovered")).toBeDefined();
  });
});
