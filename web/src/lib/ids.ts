const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

/** Project IDs are UUIDs. Anything else is rejected before any lookup. */
export function isUuid(value: string): boolean {
  return UUID_RE.test(value);
}

/** First 8 characters, for breadcrumbs and labels. */
export function shortId(id: string): string {
  return id.slice(0, 8);
}
