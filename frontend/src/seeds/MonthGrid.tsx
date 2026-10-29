import { ACTIVITIES, MONTH_NAMES, currentMonth, type Calendar } from "./calendar";

type Props = {
  calendar: Calendar;
  /** Given, the cells are buttons that flip a month; otherwise the grid is just a picture. */
  onToggle?: (activity: (typeof ACTIVITIES)[number]["key"], month: number) => void;
  /** Hide rows with nothing in them (for the compact view on the library list). */
  hideEmpty?: boolean;
};

/** Four rows (sow indoors, sow outdoors, plant out, harvest) by twelve months. */
export default function MonthGrid({ calendar, onToggle, hideEmpty }: Props) {
  const now = currentMonth();
  const rows = ACTIVITIES.filter((a) => !hideEmpty || (calendar[a.key]?.length ?? 0) > 0);
  if (rows.length === 0) return <p className="muted">No dates set.</p>;
  return (
    <table className="month-grid">
      <thead>
        <tr>
          <th scope="col"><span className="sr-only">Activity</span></th>
          {MONTH_NAMES.map((m, i) => (
            <th key={m} scope="col" className={i + 1 === now ? "now" : undefined} title={m}>{m[0]}</th>
          ))}
        </tr>
      </thead>
      <tbody>
        {rows.map((a) => (
          <tr key={a.key} className={`act-${a.key}`}>
            <th scope="row">{a.label}</th>
            {MONTH_NAMES.map((m, i) => {
              const on = calendar[a.key]?.includes(i + 1) ?? false;
              return (
                <td key={m} className={`${on ? "on" : ""}${i + 1 === now ? " now" : ""}`}>
                  {onToggle ? (
                    <button type="button" aria-pressed={on} aria-label={`${a.label} in ${m}`} onClick={() => onToggle(a.key, i + 1)} />
                  ) : (
                    <span role="img" aria-label={`${a.label} in ${m}: ${on ? "yes" : "no"}`} />
                  )}
                </td>
              );
            })}
          </tr>
        ))}
      </tbody>
    </table>
  );
}
