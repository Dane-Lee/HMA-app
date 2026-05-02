export function formatTimestamp(value: string) {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short"
  }).format(new Date(value));
}

export function bandTone(band: string) {
  if (band.startsWith("Low")) {
    return "bg-emerald-100 text-emerald-700";
  }
  if (band.startsWith("Moderate")) {
    return "bg-amber-100 text-amber-700";
  }
  return "bg-rose-100 text-rose-700";
}

export function prettyFault(fault: string) {
  return fault.replaceAll("_", " ");
}

