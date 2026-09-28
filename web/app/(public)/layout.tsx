import { SiteHeader } from "@/components/site-header";
import { SiteFooter } from "@/components/site-footer";
import { PageTransition } from "@/components/page-transition";
export default function PublicLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="flex min-h-screen flex-col">
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:fixed focus:top-20 focus:left-6 focus:z-50 focus:rounded-lg focus:bg-accent focus:p-3 focus:text-white"
      >
        Skip to content
      </a>
      <SiteHeader minimal />
      <main
        id="main-content"
        className="container-shell min-h-[70vh] flex-1 pt-28 pb-16"
      >
        <PageTransition>{children}</PageTransition>
      </main>
      <SiteFooter />
    </div>
  );
}
