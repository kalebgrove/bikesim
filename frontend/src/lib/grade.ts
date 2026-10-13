// Grade bands (percent) shared by the route map legend and the grade distribution.
export const GRADE_BANDS = [
  { label: "> 10%", min: 10, color: "#f87171" },
  { label: "6 – 10%", min: 6, color: "#f59e0b" },
  { label: "2 – 6%", min: 2, color: "#86efac" },
  { label: "± 2%", min: -2, color: "#64748b" },
  { label: "Descent", min: -Infinity, color: "#a78bfa" },
];

export function gradeBand(grade: number) {
  return GRADE_BANDS.find((b) => grade >= b.min) ?? GRADE_BANDS[GRADE_BANDS.length - 1];
}
