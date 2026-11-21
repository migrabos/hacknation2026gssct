"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import BrandMark from "./BrandMark";
import ThemeToggle from "./ThemeToggle";

const NAV = [
  { href: "/analizuj", label: "Sprawdź działkę" },
  { href: "/#jak-to-dziala", label: "Jak to działa" },
  { href: "/#dane", label: "Skąd dane" },
];

export default function SiteHeader() {
  const pathname = usePathname();
  return (
    <header className="site-header">
      <div className="container">
        <Link href="/" className="brand" aria-label="Retencja — strona główna">
          <span className="brand-mark">
            <BrandMark />
          </span>
          <span>
            <span className="brand-name">Retencja</span>
            <span className="brand-sub">woda na Twoim polu</span>
          </span>
        </Link>
        <div className="site-header-actions">
          <nav className="site-nav" aria-label="Menu główne">
            {NAV.map((n) => (
              <Link key={n.href} href={n.href} aria-current={pathname === n.href ? "page" : undefined}>
                {n.label}
              </Link>
            ))}
          </nav>
          <ThemeToggle />
        </div>
      </div>
    </header>
  );
}
