import { describe, expect, it } from "vitest";
import { ApiError } from "@/lib/api";
import { describeApiError, fieldMessages } from "@/app/_flow/messages";

describe("what the page says when the API said no", () => {
  it("repeats the field messages DRF sent, because they name the field", () => {
    const error = new ApiError(400, {
      postcode4: ["geen Nederlandse postcode"],
    });
    expect(fieldMessages(error)).toEqual(["geen Nederlandse postcode"]);
    expect(describeApiError(error)).toContain("geen Nederlandse postcode");
  });

  it("still says something useful for a 400 with no field messages", () => {
    expect(describeApiError(new ApiError(400))).toContain(
      "Controleer uw invoer",
    );
  });

  it("reads a 400 differently depending on what was being asked for", () => {
    // Computing sends a body, so a 400 is about a value somebody typed.
    // Reading an advice back sends no body at all, so a 400 there can only be
    // the token, and telling that visitor to check their input would send them
    // looking in the wrong place.
    expect(describeApiError(new ApiError(400), "compute")).toContain(
      "Controleer uw invoer",
    );
    expect(describeApiError(new ApiError(400), "link")).toContain("Deze link");
    expect(describeApiError(new ApiError(400), "link")).toBe(
      describeApiError(new ApiError(404), "link"),
    );
  });

  it("says that waiting is the answer to a 429, and that it is not for a 404", () => {
    // The two failures a visitor can do something about, and they are opposite
    // things. A single "er ging iets mis" would tell them neither.
    expect(
      describeApiError(new ApiError(429, {}, "Request was throttled.")),
    ).toContain("uur");
    expect(describeApiError(new ApiError(404))).toContain("link");
  });

  it("distinguishes a server fault from a request fault", () => {
    expect(describeApiError(new ApiError(500))).toContain("storing");
    expect(describeApiError(new ApiError(503))).toContain("storing");
    expect(describeApiError(new ApiError(418))).toContain("niet konden lezen");
  });

  it("treats a rejected fetch as unreachable rather than as a status", () => {
    // fetch rejects for a dead network, an unreachable origin and a refused
    // CORS response alike, and deliberately does not say which.
    expect(describeApiError(new TypeError("Failed to fetch"))).toContain(
      "niet bereiken",
    );
    expect(fieldMessages(new TypeError("Failed to fetch"))).toEqual([]);
  });
});
