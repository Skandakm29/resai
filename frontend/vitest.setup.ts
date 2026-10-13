import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

const isBrowser = typeof window !== "undefined";

afterEach(() => {
  if (!isBrowser) return; // node-environment tests (server-side code)
  cleanup();
  window.localStorage.clear();
  window.sessionStorage.clear();
});

// jsdom does not implement these browser APIs.
if (isBrowser) Element.prototype.scrollIntoView = function scrollIntoView() {};
if (isBrowser && !window.matchMedia) {
  window.matchMedia = (query: string) =>
    ({
      matches: false,
      media: query,
      onchange: null,
      addListener() {},
      removeListener() {},
      addEventListener() {},
      removeEventListener() {},
      dispatchEvent: () => false,
    }) as MediaQueryList;
}
