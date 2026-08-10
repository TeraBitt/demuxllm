import Link from "next/link";
import { Logo } from "@/components/brand";
import { GithubIcon, LinkedinIcon, XIcon } from "@/components/icons/social";
import { FOOTER_LINKS } from "@/lib/data";

const SOCIALS = [
  { label: "GitHub", Icon: GithubIcon },
  { label: "X", Icon: XIcon },
  { label: "LinkedIn", Icon: LinkedinIcon },
];

export function Footer() {
  return (
    <footer className="border-t border-line bg-surface">
      <div className="mx-auto max-w-6xl px-5 py-14 sm:px-8">
        <div className="grid gap-10 sm:grid-cols-2 lg:grid-cols-[minmax(0,1.4fr)_minmax(0,2fr)]">
          <div>
            <Logo />
            <p className="mt-4 max-w-xs text-sm leading-relaxed text-ink-muted">
              One key for every AI model, and a bill that reflects what each
              question actually needed.
            </p>
            <div className="mt-5 flex items-center gap-1">
              {SOCIALS.map(({ label, Icon }) => (
                <Link
                  key={label}
                  href="/"
                  aria-label={label}
                  className="grid size-9 place-items-center rounded-lg text-ink-faint transition-colors hover:bg-elevated hover:text-ink"
                >
                  <Icon size={16} />
                </Link>
              ))}
            </div>
          </div>

          <nav className="grid grid-cols-2 gap-8 sm:grid-cols-3">
            {FOOTER_LINKS.map((group) => (
              <div key={group.title}>
                <h2 className="text-[0.8125rem] font-medium text-ink">
                  {group.title}
                </h2>
                <ul className="mt-3.5 flex flex-col gap-2.5">
                  {group.links.map((l) => (
                    <li key={l.label}>
                      <Link
                        href={l.href}
                        className="text-sm text-ink-muted transition-colors hover:text-ink"
                      >
                        {l.label}
                      </Link>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </nav>
        </div>

        <div className="mt-12 flex flex-col gap-2 border-t border-line pt-6 sm:flex-row sm:items-center">
          <p className="text-[0.8125rem] text-ink-faint">
            © {new Date().getFullYear()} DemuxLLM
          </p>
          <p className="text-[0.8125rem] text-ink-faint sm:ml-auto">
            Figures shown are planning estimates, not guarantees.
          </p>
        </div>
      </div>
    </footer>
  );
}
