import { afterEach, describe, expect, it, vi } from "vitest";
import { readRecoveryFragment } from "@/app/_account/fragment";

const TOKEN = "A".repeat(43);

afterEach(() => {
  window.history.replaceState(null, "", "/account/");
});

describe("the token in the fragment", () => {
  it("reads a reset link and clears the fragment from the address bar", () => {
    window.history.replaceState(null, "", `/account/#herstel=${TOKEN}`);
    expect(readRecoveryFragment()).toEqual({ kind: "reset", token: TOKEN });
    expect(window.location.hash).toBe("");
    expect(window.location.pathname).toBe("/account/");
  });

  it("reads a verification link", () => {
    window.history.replaceState(null, "", `/account/#verificatie=${TOKEN}`);
    expect(readRecoveryFragment()).toEqual({ kind: "verify", token: TOKEN });
    expect(window.location.hash).toBe("");
  });

  it("reads nothing on a second call, because the first one cleared it", () => {
    window.history.replaceState(null, "", `/account/#herstel=${TOKEN}`);
    readRecoveryFragment();
    expect(readRecoveryFragment()).toBeNull();
  });

  it.each([
    "",
    "#",
    "#herstel=",
    `#herstel=${"A".repeat(42)}`,
    `#herstel=${"A".repeat(44)}`,
    `#herstel=${"A".repeat(42)}!`,
    `#reset=${TOKEN}`,
    `#herstel=${TOKEN}&x=1`,
    "#organisatie",
  ])("reads nothing from %j and leaves it alone", (hash) => {
    window.history.replaceState(null, "", `/account/${hash}`);
    expect(readRecoveryFragment()).toBeNull();
    expect(window.location.hash).toBe(hash === "#" ? "" : hash);
  });

  it("keeps the query string when it clears the fragment", () => {
    window.history.replaceState(null, "", `/account/?ronde=2#herstel=${TOKEN}`);
    readRecoveryFragment();
    expect(window.location.search).toBe("?ronde=2");
    expect(window.location.hash).toBe("");
  });

  it("clears the fragment with replaceState, not a navigation, and never leaves a hash on the URL it writes", () => {
    window.history.replaceState(null, "", `/account/#herstel=${TOKEN}`);
    const replaceSpy = vi.spyOn(window.history, "replaceState");
    const pushSpy = vi.spyOn(window.history, "pushState");
    readRecoveryFragment();
    expect(pushSpy).not.toHaveBeenCalled();
    expect(replaceSpy).toHaveBeenCalledTimes(1);
    const url = String(replaceSpy.mock.calls[0]?.[2]);
    expect(url).not.toContain("#");
    replaceSpy.mockRestore();
    pushSpy.mockRestore();
  });
});
