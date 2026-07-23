"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

const navigation = [
  { href: "/platform", label: "Platform" },
  { href: "/workflow", label: "Workflow" },
  { href: "/about", label: "About" },
];

export function LogoMark() {
  return (
    <svg viewBox="0 0 32 32" aria-hidden="true">
      <path d="M3 9h10v4H7v6h6v4H3V9Zm16 0h10v4h-6v6h6v4H19V9Z" fill="currentColor" />
    </svg>
  );
}

export function Arrow() {
  return (
    <svg viewBox="0 0 16 16" aria-hidden="true">
      <path d="M3 8h9M9 4l4 4-4 4" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function MarketingNav() {
  const pathname = usePathname();
  return (
    <nav className="landing-nav" aria-label="Hauptnavigation">
      <Link className="landing-logo" href="/" aria-label="Communication Simulator Startseite">
        <LogoMark />
        <span>communication<br />simulator</span>
      </Link>
      <div className="nav-links">
        {navigation.map((item) => (
          <Link aria-current={pathname === item.href ? "page" : undefined} className={pathname === item.href ? "active" : ""} href={item.href} key={item.href}>
            {item.label}
          </Link>
        ))}
      </div>
      <Link className="nav-cta" href="/studio">Open studio <Arrow /></Link>
    </nav>
  );
}

export function MarketingFooter() {
  return (
    <footer className="landing-footer">
      <Link className="landing-logo footer-logo" href="/"><LogoMark /><span>communication<br />simulator</span></Link>
      <p>Simulation infrastructure for connected systems.</p>
      <div>{navigation.map((item) => <Link href={item.href} key={item.href}>{item.label}</Link>)}<Link href="/studio">Studio</Link></div>
      <span>© 2026 CS LAB</span>
    </footer>
  );
}

export function MarketingShell({ children }: { children: ReactNode }) {
  return <main className="landing"><MarketingNav />{children}<MarketingFooter /></main>;
}

export function PageHero({ eyebrow, title, accent, description }: { eyebrow: string; title: string; accent: string; description: string }) {
  return (
    <header className="subpage-hero">
      <p className="section-label">{eyebrow}</p>
      <h1>{title}<br /><em>{accent}</em></h1>
      <p>{description}</p>
    </header>
  );
}
