import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MeterSection } from "@/app/_account/MeterSection";
import type {
  ConsumptionCheckAnswer,
  MeterKey,
  MeterStatus,
} from "@/lib/accounts";

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
        check={null}
        onAccept={noop}
        onClaim={noop}
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
        check={null}
        onAccept={noop}
        onClaim={noop}
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
        check={null}
        onAccept={noop}
        onClaim={noop}
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
        check={null}
        onAccept={noop}
        onClaim={noop}
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
        check={null}
        onAccept={noop}
        onClaim={noop}
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
        check={null}
        onAccept={noop}
        onClaim={noop}
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
        check={null}
        onAccept={noop}
        onClaim={noop}
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
        check={null}
        onAccept={noop}
        onClaim={noop}
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
        check={null}
        onAccept={noop}
        onClaim={noop}
      />,
    );
    expect(screen.getByRole("button", { name: "Ontkoppel" })).toBeDisabled();
    expect(
      screen.getByRole("button", { name: "Ontkoppelen bevestigen" }),
    ).toBeDisabled();
  });
});

const CONTRADICTED: ConsumptionCheckAnswer = {
  advice_token: "b".repeat(22),
  check: {
    typed_kwh: 2800,
    p10_kwh: 3600,
    p50_kwh: 4000,
    p90_kwh: 4400,
    runs: 8,
    quarters_used: 5376,
    message:
      "U gaf 2800 kWh per jaar op. Over de periode die uw meter heeft doorgegeven komen wij uit op 3600 tot 4400 kWh per jaar.",
    measured_over:
      "Gemeten over 5376 kwartieren van uw eigen meter, in 8 herberekeningen met telkens een week weggelaten.",
    accept_label: "Reken met 4000 kWh",
    keep_own: "Doet u niets, dan blijft uw advies op uw eigen getal rekenen.",
    installation_note: null,
  },
};

describe("the meter section: what the meter says about the typed figure", () => {
  it("shows the API's sentence, what the band rests on, and the button", async () => {
    const onAccept = vi.fn();
    render(
      <MeterSection
        status={LINKED_WITH_READING}
        issuedKey={null}
        apiBase={API_BASE}
        busy={false}
        onLink={noop}
        onUnlink={noop}
        check={CONTRADICTED}
        onAccept={onAccept}
        onClaim={noop}
      />,
    );

    expect(screen.getByText(CONTRADICTED.check!.message)).toBeInTheDocument();
    // The band is what makes this a finding rather than a corrected number,
    // so what it was measured over is on the screen beside it.
    expect(screen.getByText(/5376 kwartieren/)).toBeInTheDocument();
    expect(screen.getByText(/8 herberekeningen/)).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /4000 kWh/ }));

    expect(onAccept).toHaveBeenCalledOnce();
  });

  it("says nothing at all when the meter does not contradict", () => {
    render(
      <MeterSection
        status={LINKED_WITH_READING}
        issuedKey={null}
        apiBase={API_BASE}
        busy={false}
        onLink={noop}
        onUnlink={noop}
        check={{ advice_token: null, check: null }}
        onAccept={noop}
        onClaim={noop}
      />,
    );

    expect(
      screen.queryByRole("button", { name: /kWh/ }),
    ).not.toBeInTheDocument();
  });

  it("passes on the note about the installation when there is one", () => {
    const note =
      "Wat u teruglevert komt niet goed overeen met onze berekening.";
    render(
      <MeterSection
        status={LINKED_WITH_READING}
        issuedKey={null}
        apiBase={API_BASE}
        busy={false}
        onLink={noop}
        onUnlink={noop}
        check={{
          ...CONTRADICTED,
          check: { ...CONTRADICTED.check!, installation_note: note },
        }}
        onAccept={noop}
        onClaim={noop}
      />,
    );

    expect(screen.getByText(note)).toBeInTheDocument();
  });

  it("disables the button while something else is in flight", () => {
    render(
      <MeterSection
        status={LINKED_WITH_READING}
        issuedKey={null}
        apiBase={API_BASE}
        busy={true}
        onLink={noop}
        onUnlink={noop}
        check={CONTRADICTED}
        onAccept={noop}
        onClaim={noop}
      />,
    );

    expect(screen.getByRole("button", { name: /4000 kWh/ })).toBeDisabled();
  });
});

describe("the meter section: an account with no advice of its own", () => {
  const NO_ADVICE = { advice_token: null, check: null } as const;

  it("offers to turn a link into one, and passes on what was typed", async () => {
    const onClaim = vi.fn();
    render(
      <MeterSection
        status={LINKED_WITH_READING}
        issuedKey={null}
        apiBase={API_BASE}
        busy={false}
        onLink={noop}
        onUnlink={noop}
        check={NO_ADVICE}
        onAccept={noop}
        onClaim={onClaim}
      />,
    );

    await userEvent.type(
      screen.getByLabelText("Link van uw advies"),
      "https://ampeer.nl/advies/bbbbbbbbbbbbbbbbbbbbbb/",
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Koppel aan mijn account" }),
    );

    expect(onClaim).toHaveBeenCalledWith(
      "https://ampeer.nl/advies/bbbbbbbbbbbbbbbbbbbbbb/",
    );
  });

  it("keeps the button out of reach until something is typed", () => {
    render(
      <MeterSection
        status={LINKED_WITH_READING}
        issuedKey={null}
        apiBase={API_BASE}
        busy={false}
        onLink={noop}
        onUnlink={noop}
        check={NO_ADVICE}
        onAccept={noop}
        onClaim={noop}
      />,
    );

    expect(
      screen.getByRole("button", { name: "Koppel aan mijn account" }),
    ).toBeDisabled();
  });

  it("does not offer it once the account has an advice", () => {
    render(
      <MeterSection
        status={LINKED_WITH_READING}
        issuedKey={null}
        apiBase={API_BASE}
        busy={false}
        onLink={noop}
        onUnlink={noop}
        check={CONTRADICTED}
        onAccept={noop}
        onClaim={noop}
      />,
    );

    expect(
      screen.queryByLabelText("Link van uw advies"),
    ).not.toBeInTheDocument();
  });
});
