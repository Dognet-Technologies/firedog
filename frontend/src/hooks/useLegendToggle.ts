import { useCallback, useState } from 'react';

/**
 * Click-to-toggle visibility for Recharts series via their Legend entry.
 * Default: every key visible. Clicking a legend entry hides that series;
 * clicking it again shows it back. Unrelated legend entries (dataKey not
 * in `keys`) are ignored.
 */
export function useLegendToggle(keys: string[]) {
  const [hidden, setHidden] = useState<Record<string, boolean>>({});

  // `any`: Recharts' Legend onClick payload type (dataKey can be a string,
  // number, or accessor function) doesn't structurally match a plain
  // object type, and this hook has no reason to depend on recharts' types.
  const onLegendClick = useCallback(
    (entry: any) => {
      const key = String(entry?.dataKey ?? '');
      if (!keys.includes(key)) return;
      setHidden((prev) => ({ ...prev, [key]: !prev[key] }));
    },
    [keys]
  );

  return { hidden, onLegendClick };
}

export default useLegendToggle;
