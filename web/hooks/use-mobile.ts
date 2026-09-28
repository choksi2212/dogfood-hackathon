import * as React from "react"

const MOBILE_BREAKPOINT = 768

export function useIsMobile() {
  // Starting from `undefined` (not a `window`-derived lazy initializer)
  // means the first render is identical on the server and during client
  // hydration — `window` doesn't exist server-side, so a lazy
  // `useState(() => window.innerWidth < BREAKPOINT)` would evaluate
  // `false` on the server but the real viewport width during hydration,
  // mismatching for anyone on a narrow viewport and forcing React to
  // discard and regenerate the whole tree on every dashboard page load.
  // The real value is set after mount instead, in an effect.
  const [isMobile, setIsMobile] = React.useState<boolean | undefined>(undefined)

  React.useEffect(() => {
    const mql = window.matchMedia(`(max-width: ${MOBILE_BREAKPOINT - 1}px)`)
    const onChange = () => {
      setIsMobile(window.innerWidth < MOBILE_BREAKPOINT)
    }
    mql.addEventListener("change", onChange)
    onChange()
    return () => mql.removeEventListener("change", onChange)
  }, [])

  return !!isMobile
}
