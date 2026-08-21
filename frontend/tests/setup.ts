import "@testing-library/jest-dom/vitest";

import { installMatchMedia } from "./matchMedia";

// jsdom implements no matchMedia, so any component reading a media
// preference throws the moment it renders. Installed here with movement
// allowed, which is the browser default; a test that wants the reduced
// branch installs it again with true.
installMatchMedia(false);
