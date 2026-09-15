import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";

import {
  ConsentBanner,
  ConsentReset,
  setConsent,
} from "@/app/_shell/ConsentBanner";
import { CONSENT_STORAGE_KEY, gtagScriptUrl } from "@/app/_shell/analytics";

const ID = "G-TESTTESTTE";

function gtagScripts(): HTMLScriptElement[] {
  return [
    ...document.querySelectorAll<HTMLScriptElement>("script[src]"),
  ].filter((element) => element.src === gtagScriptUrl(ID));
}

beforeEach(() => {
  window.localStorage.clear();
});

afterEach(() => {
  for (const script of gtagScripts()) script.remove();
  delete (window as { dataLayer?: unknown[] }).dataLayer;
});

describe("the question about measuring", () => {
  it("renders nothing at all in a build without a measurement ID", () => {
    const { container } = render(<ConsentBanner measurementId="" />);
    expect(container).toBeEmptyDOMElement();
    expect(gtagScripts()).toHaveLength(0);
  });

  it("asks a visitor who has not answered, and loads nothing while asking", () => {
    render(<ConsentBanner measurementId={ID} />);
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(gtagScripts()).toHaveLength(0);
  });

  it("offers two answers of equal weight, no first, and neither pre-selected", () => {
    render(<ConsentBanner measurementId={ID} />);
    const buttons = screen.getAllByRole("button");
    expect(buttons.map((button) => button.textContent)).toEqual([
      "Nee, liever niet",
      "Ja, dat mag",
    ]);
    // Same classes means same size, same border, same weight: a yes styled
    // as the primary action is a nudge, and the law asks for a choice.
    expect(buttons[0]?.className).toBe(buttons[1]?.className);
    // Nothing is a checkbox and nothing is checked.
    expect(screen.queryByRole("checkbox")).toBeNull();
  });

  it("loads gtag.js once after yes, configured without Google Signals", () => {
    render(<ConsentBanner measurementId={ID} />);
    fireEvent.click(screen.getByRole("button", { name: "Ja, dat mag" }));

    expect(window.localStorage.getItem(CONSENT_STORAGE_KEY)).toBe("ja");
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(gtagScripts()).toHaveLength(1);

    const layer = (window as { dataLayer?: IArguments[] }).dataLayer ?? [];
    const config = layer.find((entry) => entry[0] === "config");
    expect(config?.[1]).toBe(ID);
    expect(config?.[2]).toMatchObject({
      allow_google_signals: false,
      allow_ad_personalization_signals: false,
    });
  });

  it("does not load a second copy when it renders again", () => {
    const { rerender } = render(<ConsentBanner measurementId={ID} />);
    fireEvent.click(screen.getByRole("button", { name: "Ja, dat mag" }));
    rerender(<ConsentBanner measurementId={ID} />);
    rerender(<ConsentBanner measurementId={ID} />);
    expect(gtagScripts()).toHaveLength(1);
  });

  it("remembers no, loads nothing, and stops asking", () => {
    render(<ConsentBanner measurementId={ID} />);
    fireEvent.click(screen.getByRole("button", { name: "Nee, liever niet" }));

    expect(window.localStorage.getItem(CONSENT_STORAGE_KEY)).toBe("nee");
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(gtagScripts()).toHaveLength(0);
  });

  it("does not ask a visitor who already said no", () => {
    window.localStorage.setItem(CONSENT_STORAGE_KEY, "nee");
    render(<ConsentBanner measurementId={ID} />);
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(gtagScripts()).toHaveLength(0);
  });

  it("loads for a visitor who already said yes, without asking again", () => {
    window.localStorage.setItem(CONSENT_STORAGE_KEY, "ja");
    render(<ConsentBanner measurementId={ID} />);
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(gtagScripts()).toHaveLength(1);
  });

  it("a no after a yes raises the flag gtag.js honours", () => {
    render(<ConsentBanner measurementId={ID} />);
    fireEvent.click(screen.getByRole("button", { name: "Ja, dat mag" }));
    expect(
      (window as unknown as Record<string, unknown>)[`ga-disable-${ID}`],
    ).toBe(false);
    setConsent("denied", ID);
    expect(
      (window as unknown as Record<string, unknown>)[`ga-disable-${ID}`],
    ).toBe(true);
  });
});

describe("the way back, on the privacy page", () => {
  it("renders nothing without a measurement ID", () => {
    const { container } = render(<ConsentReset measurementId="" />);
    expect(container).toBeEmptyDOMElement();
  });

  it("says what was chosen and lets the visitor un-choose it", () => {
    window.localStorage.setItem(CONSENT_STORAGE_KEY, "ja");
    render(
      <>
        <ConsentReset measurementId={ID} />
        <ConsentBanner measurementId={ID} />
      </>,
    );
    expect(screen.getByText("U heeft ja gezegd.")).toBeInTheDocument();
    expect(screen.queryByRole("dialog")).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "Uw keuze wijzigen" }));

    expect(window.localStorage.getItem(CONSENT_STORAGE_KEY)).toBeNull();
    expect(screen.getByText("U heeft nog niets gekozen.")).toBeInTheDocument();
    // The question is back, on this same page.
    expect(screen.getByRole("dialog")).toBeInTheDocument();
  });

  it("offers no button to a visitor who has not chosen yet", () => {
    render(<ConsentReset measurementId={ID} />);
    expect(screen.getByText("U heeft nog niets gekozen.")).toBeInTheDocument();
    expect(screen.queryByRole("button")).toBeNull();
  });
});
