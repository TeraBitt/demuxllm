import { LogoMark } from "@/components/brand";
import { Button } from "@/components/ui/primitives";

export default function NotFound() {
  return (
    <div className="relative overflow-hidden">
      <div
        aria-hidden
        className="bg-grid mask-fade-b pointer-events-none absolute inset-0"
      />
      <div className="relative mx-auto flex max-w-xl flex-col items-center px-5 py-28 text-center sm:py-36">
        <LogoMark className="h-10 w-10" />
        <p className="mt-6 text-[0.8125rem] font-medium text-accent">404</p>
        <h1 className="mt-2 text-3xl font-semibold tracking-[-0.035em] sm:text-4xl">
          We couldn&rsquo;t route that one
        </h1>
        <p className="mt-4 text-[1.0625rem] leading-relaxed text-ink-muted">
          The page you were after does not exist. Everything else still does.
        </p>
        <div className="mt-8 flex flex-wrap justify-center gap-2.5">
          <Button href="/" className="h-11 px-5 text-[0.9375rem]">
            Back home
          </Button>
          <Button
            href="/models"
            variant="secondary"
            className="h-11 px-5 text-[0.9375rem]"
          >
            Browse models
          </Button>
        </div>
      </div>
    </div>
  );
}
