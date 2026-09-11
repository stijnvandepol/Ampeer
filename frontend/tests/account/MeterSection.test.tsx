import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MeterSection } from "@/app/_account/MeterSection";
import type { MeterKey, MeterStatus } from "@/lib/accounts";

const API_BASE = "http://127.0.0.1:8000";

const NOT_ALLOWED: MeterStatus = {
  may_link: false,
  linked: false,
  created_at: null,
  last_seen_at: null,
  last_seen_label: null,
};

const MAY_LINK: MeterStatus = {
  may_link: true,
  linked: false,
  created_at: null,
  last_seen_at: null,
  last_seen_label: null,
};

const LINKED_NOTHING_YET: MeterStatus = {
  may_link: true,
  linked: true,
  created_at: "2026-09-09T09:00:00Z",
  last_seen_at: null,
  last_seen_label: null,
};

const LINKED_WITH_READING: MeterStatus = {
  may_link: true,
  linked: true,
  created_at: "2026-09-09T09:00:00Z",
  last_seen_at: "2026-09-09T10:15:00Z",
  last_seen_label: "9 september 2026 12:15",
};

const ISSUED_KEY: MeterKey = {
  token: "a".repeat(43),
  push_path: "/api/meter/readings/",
  created_at: "2026-09-09T09:00:00Z",
};

function noop(): void {}

describe("the meter section: not possible", () => {
  it("shows no button and the sentence about what is needed", () => {
    render(
      <MeterSection
        status={NOT_ALLOWED}
        issuedKey={null}
        apiBase={API_BASE}
        busy={false}
        onLink={noop}
        onUnlink={noop}
      />,
    );
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
    expect(
      screen.getByText(/bevestigd e-mailadres en toestemming/),
    ).toBeInTheDocument();
  });
});

describe("the meter section: possible and not linked", () => {
  it("offers the link button and calls onLink exactly once per click", async () => {
    const onLink = vi.fn();
    render(
      <MeterSection
        status={MAY_LINK}
        issuedKey={null}
        apiBase={API_BASE}
        busy={false}
        onLink={onLink}
        onUnlink={noop}
      />,
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Koppel uw meter" }),
    );
    expect(onLink).toHaveBeenCalledTimes(1);
  });

  it("disables the link button and shows a busy status while linking", () => {
    render(
      <MeterSection
        status={MAY_LINK}
        issuedKey={null}
        apiBase={API_BASE}
        busy={true}
        onLink={noop}
        onUnlink={noop}
      />,
    );
    expect(
      screen.getByRole("button", { name: "Koppel uw meter" }),
    ).toBeDisabled();
    expect(screen.getByRole("status")).toHaveTextContent("Bezig.");
  });
});

describe("the meter section: the issued key", () => {
  it("shows the key and the full push address", () => {
    render(
      <MeterSection
        status={MAY_LINK}
        issuedKey={ISSUED_KEY}
        apiBase={API_BASE}
        busy={false}
        onLink={noop}
        onUnlink={noop}
      />,
    );
    expect(screen.getByText(ISSUED_KEY.token)).toBeInTheDocument();
    expect(
      screen.getByText(API_BASE + ISSUED_KEY.push_path),
    ).toBeInTheDocument();
  });
});

describe("the meter section: linked", () => {
  it("says nothing has come in yet when last_seen_at is null", () => {
    render(
      <MeterSection
        status={LINKED_NOTHING_YET}
        issuedKey={null}
        apiBase={API_BASE}
        busy={false}
        onLink={noop}
        onUnlink={noop}
      />,
    );
    expect(
      screen.getByText("Er is nog niets binnengekomen."),
    ).toBeInTheDocument();
  });

  it("shows the last-seen moment in Europe/Amsterdam", () => {
    render(
      <MeterSection
        status={LINKED_WITH_READING}
        issuedKey={null}
        apiBase={API_BASE}
        busy={false}
        onLink={noop}
        onUnlink={noop}
      />,
    );
    // The sentence the API built, shown word for word. This used to compute
    // its own expectation with the same `new Date(...).toLocaleString(...)`
    // the component called, so the two agreed by construction and the
    // assertion could not tell a right conversion from a wrong one. The
    // conversion is now the API's, tested there against both sides of the
    // clock change, and what is left here is that the page shows what it
    // was handed.
    expect(
      screen.getByText(
        new RegExp(LINKED_WITH_READING.last_seen_label as string),
      ),
    ).toBeInTheDocument();
    // Not the raw UTC string: that is the wrong timezone shown to a household.
    expect(document.body.textContent).not.toContain(
      LINKED_WITH_READING.last_seen_at,
    );
  });

  it("calls onUnlink only after the confirmation, not on the first click", async () => {
    const onUnlink = vi.fn();
    render(
      <MeterSection
        status={LINKED_NOTHING_YET}
        issuedKey={null}
        apiBase={API_BASE}
        busy={false}
        onLink={noop}
        onUnlink={onUnlink}
      />,
    );
    await userEvent.click(screen.getByRole("button", { name: "Ontkoppel" }));
    expect(onUnlink).not.toHaveBeenCalled();
    await userEvent.click(
      screen.getByRole("button", { name: "Ontkoppelen bevestigen" }),
    );
    expect(onUnlink).toHaveBeenCalledTimes(1);
  });

  /**
   * `busy` is a prop, so this expands the confirmation first (which is local
   * state) and then re-renders the same instance with `busy` turned on,
   * rather than mounting fresh with `busy` already true, which would leave
   * the opener disabled before it could ever be clicked.
   *
   * Red-proof: drop `disabled={busy}` from the opener button and see this
   * test fail on the first assertion.
   */
  it("disables both the opener and the confirm button while busy", async () => {
    const { rerender } = render(
      <MeterSection
        status={LINKED_NOTHING_YET}
        issuedKey={null}
        apiBase={API_BASE}
        busy={false}
        onLink={noop}
        onUnlink={noop}
      />,
    );
    await userEvent.click(screen.getByRole("button", { name: "Ontkoppel" }));
    rerender(
      <MeterSection
        status={LINKED_NOTHING_YET}
        issuedKey={null}
        apiBase={API_BASE}
        busy={true}
        onLink={noop}
        onUnlink={noop}
      />,
    );
    expect(screen.getByRole("button", { name: "Ontkoppel" })).toBeDisabled();
    expect(
      screen.getByRole("button", { name: "Ontkoppelen bevestigen" }),
    ).toBeDisabled();
  });
});
