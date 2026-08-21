import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Nothing here renders per request. The browser calls the advice API
  // directly, for two reasons that both come from the API rather than from
  // taste: it throttles per IP, so a server-side fetch would put every visitor
  // into one bucket of twenty computations an hour, and the answers are
  // personal data that gain nothing from passing through one more process with
  // one more access log.
  //
  // So there is no Node process in production. Verified working on 16.3.1:
  // this produces out/ with static HTML per route.
  output: "export",
  // A trailing slash makes every route a directory with an index.html, which
  // is what lets a plain file server resolve /advies/<token> to one page.
  trailingSlash: true,
  reactStrictMode: true,
};

export default nextConfig;
