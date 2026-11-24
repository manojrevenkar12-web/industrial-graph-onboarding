import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import report from "../../public/data/report.json";
import { App } from "./App";

const ok = (body: unknown) => Promise.resolve(new Response(JSON.stringify(body), { status: 200 }));

afterEach(() => vi.restoreAllMocks());

describe("App", () => {
  it("shows loading, then the development results", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() => ok(report));
    render(<App />);
    expect(screen.getByRole("status")).toHaveTextContent("Loading the study results");
    expect(await screen.findByRole("heading", { level: 1 })).toBeInTheDocument();
    expect(screen.getByText(/Release gates: 9 of 9 pass/)).toBeInTheDocument();
  });

  it("explains a missing report and loads it again", async () => {
    const spy = vi
      .spyOn(globalThis, "fetch")
      .mockImplementationOnce(() => Promise.resolve(new Response("", { status: 404 })))
      .mockImplementation(() => ok(report));
    render(<App />);
    expect(await screen.findByRole("alert")).toHaveTextContent("HTTP 404");
    fireEvent.click(screen.getByRole("button", { name: "Load the report again" }));
    expect(await screen.findByRole("heading", { level: 1 })).toBeInTheDocument();
    expect(spy).toHaveBeenCalledTimes(2);
  });

  it("says when the held-out plants have not been run", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() => ok({ ...report, heldout: null, lock: null }));
    render(<App />);
    fireEvent.click(await screen.findByRole("radio", { name: /Held-out/ }));
    expect(screen.getByText("The held-out plants have not been run")).toBeInTheDocument();
  });

  it("shows the held-out run without a wiring sample", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() => ok(report));
    render(<App />);
    fireEvent.click(await screen.findByRole("radio", { name: /Held-out/ }));
    expect(screen.getByText("No wiring sample for these plants")).toBeInTheDocument();
    expect(screen.getByText(/Locked to config/)).toBeInTheDocument();
  });

  it("opens a review item to show its candidates", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() => ok(report));
    render(<App />);
    await screen.findByRole("heading", { level: 1 });
    const heads = screen.getAllByRole("button", { expanded: false });
    fireEvent.click(heads[0] as HTMLElement);
    await waitFor(() => expect(screen.getAllByText("Candidates as the engineer saw them").length).toBeGreaterThan(1));
  });

  it("switches the agent transcripts to the model acting alone", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() => ok(report));
    render(<App />);
    fireEvent.click(await screen.findByRole("tab", { name: "Model alone" }));
    expect(screen.getByRole("tab", { name: "Model alone" })).toHaveAttribute("aria-selected", "true");
  });
});
