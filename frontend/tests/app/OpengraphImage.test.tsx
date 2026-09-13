import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { alt, contentType, dynamic, size } from "@/app/opengraph-image";

const CONFIG = join(process.cwd(), "..", "infra", "nginx", "nginx.conf");

describe("the picture every share of this site shows", () => {
  it("is the size the platforms crop to, and says so", () => {
    expect(size).toEqual({ width: 1200, height: 630 });
    expect(contentType).toBe("image/png");
  });

  it("is static, because there is no Node process in production", () => {
    // next.config.ts sets output: "export", and an image route is a route:
    // without this the build fails outright rather than shipping something
    // broken. Asserted so that the reason survives the line.
    expect(dynamic).toBe("force-static");
  });

  it("describes the picture rather than selling the product", () => {
    // Read aloud in place of an image when somebody shares the link. A sales
    // line there is the kind of thing this site does not do.
    expect(alt.length).toBeGreaterThan(20);
    expect(alt).toMatch(/bandbreedte/);
    expect(alt).not.toMatch(/€|\d+\s*euro|gratis|nu /i);
  });

  it("is typed by nginx, which cannot guess from a name with no extension", () => {
    // THE FAILURE THIS CATCHES IS INVISIBLE IN A BUILD. Next names the file
    // after its route, so the export writes out/opengraph-image: a real PNG
    // whose name ends in nothing. nginx types a response from the extension
    // and falls back to `default_type application/octet-stream`, so every
    // crawler would receive a binary blob and render the blank card this
    // picture exists to prevent. Verified against the running stack on
    // 2026-09-13, which answered image/png only after the block below existed.
    const config = readFileSync(CONFIG, "utf-8");
    const block = config.split("location = /opengraph-image")[1];
    expect(block).toBeDefined();
    expect(block?.split("}")[0]).toMatch(/default_type\s+image\/png\s*;/);
  });
});
