import { describe, expect, it } from "vitest";

import {
  CONSENT_STORAGE_KEY,
  GTAG_HOST,
  disableAnalytics,
  gtagScriptUrl,
  loadAnalytics,
  readConsent,
  writeConsent,
} from "@/app/_shell/analytics";

function fakeStorage(initial: Record<string, string> = {}) {
  const store = new Map(Object.entries(initial));
  return {
    store,
    getItem: (key: string) => store.get(key) ?? null,
    setItem: (key: string, value: string) => {
      store.set(key, value);
    },
    removeItem: (key: string) => {
      store.delete(key);
    },
  };
}

describe("reading and writing the answer", () => {
  it("reads nothing as unknown, and only the two Dutch words as answers", () => {
    expect(readConsent(fakeStorage())).toBe("unknown");
    expect(readConsent(fakeStorage({ [CONSENT_STORAGE_KEY]: "ja" }))).toBe(
      "granted",
    );
    expect(readConsent(fakeStorage({ [CONSENT_STORAGE_KEY]: "nee" }))).toBe(
      "denied",
    );
    // A value nobody wrote is not a yes.
    expect(readConsent(fakeStorage({ [CONSENT_STORAGE_KEY]: "true" }))).toBe(
      "unknown",
    );
  });

  it("writes the two answers and removes the key for unknown", () => {
    const storage = fakeStorage();
    writeConsent(storage, "granted");
    expect(storage.store.get(CONSENT_STORAGE_KEY)).toBe("ja");
    writeConsent(storage, "denied");
    expect(storage.store.get(CONSENT_STORAGE_KEY)).toBe("nee");
    writeConsent(storage, "unknown");
    expect(storage.store.has(CONSENT_STORAGE_KEY)).toBe(false);
  });

  it("treats a browser that refuses storage as a visitor who has not answered", () => {
    const refusing = {
      getItem: () => {
        throw new Error("SecurityError");
      },
      setItem: () => {
        throw new Error("SecurityError");
      },
      removeItem: () => {
        throw new Error("SecurityError");
      },
    };
    expect(readConsent(refusing)).toBe("unknown");
    expect(() => writeConsent(refusing, "granted")).not.toThrow();
  });
});

describe("what a yes loads", () => {
  it("builds the script URL on the one host the policy admits for scripts", () => {
    expect(gtagScriptUrl("G-ABC123")).toBe(`${GTAG_HOST}/gtag/js?id=G-ABC123`);
    expect(gtagScriptUrl("G-A&B")).toBe(`${GTAG_HOST}/gtag/js?id=G-A%26B`);
  });

  it("loads nothing for an empty ID, whatever the document", () => {
    const doc = document.implementation.createHTMLDocument("");
    const win = {} as Window & { dataLayer?: unknown[] };
    loadAnalytics(doc, win, "");
    expect(doc.querySelectorAll("script")).toHaveLength(0);
    expect(win.dataLayer).toBeUndefined();
  });

  it("adds the script once, async, and the two commands gtag.js expects", () => {
    const doc = document.implementation.createHTMLDocument("");
    const win = {} as Window & { dataLayer?: IArguments[] };
    loadAnalytics(doc, win, "G-ABC123");
    loadAnalytics(doc, win, "G-ABC123");

    const scripts = doc.querySelectorAll("script");
    expect(scripts).toHaveLength(1);
    expect(scripts[0]?.async).toBe(true);
    expect(scripts[0]?.src).toBe(gtagScriptUrl("G-ABC123"));

    const layer = win.dataLayer ?? [];
    expect(layer.map((entry) => entry[0])).toEqual(["js", "config"]);
    // gtag.js reads the `arguments` object its snippet pushes and ignores a
    // plain array; this is the check that the shape survived a tidy-up.
    expect(Object.prototype.toString.call(layer[0])).toBe("[object Arguments]");
    expect(layer[1]?.[2]).toMatchObject({
      allow_google_signals: false,
      allow_ad_personalization_signals: false,
      cookie_flags: "SameSite=Strict;Secure",
    });
  });

  it("lowers the disable flag on load and raises it on a later no", () => {
    const doc = document.implementation.createHTMLDocument("");
    const win = {} as Window & Record<string, unknown>;
    loadAnalytics(doc, win, "G-ABC123");
    expect(win["ga-disable-G-ABC123"]).toBe(false);
    disableAnalytics(win, "G-ABC123");
    expect(win["ga-disable-G-ABC123"]).toBe(true);
    // And an empty ID touches nothing.
    disableAnalytics(win, "");
    expect(Object.keys(win)).toEqual(["ga-disable-G-ABC123", "dataLayer"]);
  });
});
