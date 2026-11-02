"use client";
import { useSyncExternalStore } from "react";

const Q = "(prefers-reduced-motion: reduce)";
function subscribe(cb: () => void) {
  const m = window.matchMedia(Q);
  m.addEventListener("change", cb);
  return () => m.removeEventListener("change", cb);
}
/** True when the user prefers reduced motion (false on the server). */
export function useReducedMotion(): boolean {
  return useSyncExternalStore(subscribe, () => window.matchMedia(Q).matches, () => false);
}

const noop = () => () => {};
/** False during server render and hydration, true afterwards. It flips in the same re-render as useReducedMotion's
 *  client value, so gating WebGL on `hydrated && !reduce` never mounts it, even briefly, when motion is reduced. */
export function useHydrated(): boolean {
  return useSyncExternalStore(noop, () => true, () => false);
}
