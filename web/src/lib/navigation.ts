export type NavItem = { href: string; label: string };

/** Primary destinations, in the order they appear in the header. */
export const primaryNav: readonly NavItem[] = [
  { href: "/projects", label: "Projects" },
  { href: "/methodology", label: "Methodology" },
];

/** The main call to action. Shown as a button on wide screens, as a link in the mobile menu. */
export const uploadNav: NavItem = { href: "/upload", label: "Upload lecture" };

export const footerNav: readonly NavItem[] = [
  { href: "/status", label: "System status" },
  { href: "/design", label: "Design system" },
];

/**
 * True when `pathname` is the item's page or one of its children.
 * "/projects/abc/results" activates "/projects"; "/projectsx" does not.
 */
export function isActivePath(pathname: string | null, href: string): boolean {
  if (!pathname) return false;
  if (href === "/") return pathname === "/";
  return pathname === href || pathname.startsWith(`${href}/`);
}
