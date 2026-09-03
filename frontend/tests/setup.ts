import "@testing-library/jest-dom/vitest";

import { installMatchMedia } from "./matchMedia";

// jsdom implements no matchMedia, so any component reading a media
// preference throws the moment it renders. Installed here with movement
// allowed, which is the browser default; a test that wants the reduced
// branch installs it again with true.
installMatchMedia(false);

// jsdom implements no scrollIntoView either: `Element.prototype.scrollIntoView`
// is `undefined`, not a no-op, so any component that calls it throws the
// moment it renders in a component test rather than merely failing to scroll.
//
// A plain function and not a `vi.fn()`: installed once here, it would
// otherwise be one mock shared by the entire run with no test isolation
// between files, since nothing in this repository configures vitest to clear
// mocks between tests. A test that needs to see how it was called installs
// its own `vi.spyOn(Element.prototype, "scrollIntoView")` and restores it in
// its own `afterEach`, which spies on this stub without disturbing it for
// every other test that merely needs it to exist and do nothing.
Element.prototype.scrollIntoView ??= function scrollIntoViewStub() {};
