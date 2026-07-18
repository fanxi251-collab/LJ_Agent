export function resolveRouteSummary(source) {
  const metadata = source?.metadata || null;
  if (!metadata || metadata.source_type !== "amap_route") return null;
  return metadata.route_summary || (metadata.polyline || metadata.steps ? metadata : null);
}

export function findSuccessfulRouteSource(sources) {
  return (sources || []).find((source) => {
    const summary = resolveRouteSummary(source);
    return Boolean(summary && (summary.polyline?.length || summary.steps?.length));
  }) || null;
}
