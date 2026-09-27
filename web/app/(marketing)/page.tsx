import Link from "next/link";
import { ArrowRight, Gavel, LayoutDashboard, Rocket } from "lucide-react";
import { buttonVariants } from "@/components/ui/button";
import { Card, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";

const ROLES = [
  {
    icon: Rocket,
    title: "Submit",
    description: "Build something, tell us about it, and see it go live in the public gallery.",
  },
  {
    icon: Gavel,
    title: "Judge",
    description: "Score your assigned batch against the published rubric, or compare projects head-to-head.",
  },
  {
    icon: LayoutDashboard,
    title: "Organize",
    description: "Invite judges, run assignment, normalize scores, and publish results and certificates.",
  },
];

export default function Home() {
  return (
    <div>
      <section className="mx-auto max-w-5xl px-4 py-24 sm:py-32">
        <span className="text-sm font-semibold uppercase tracking-wide text-primary">
          Hackathon judging portal
        </span>
        <h1 className="mt-3 max-w-2xl text-4xl font-bold tracking-tight sm:text-5xl">
          Dogfood Portal
        </h1>
        <p className="mt-4 max-w-xl text-lg text-muted-foreground">
          Submit a project, judge a batch, cast a vote, or browse what shipped — one
          platform for every role in the event.
        </p>
        <div className="mt-8 flex flex-wrap gap-3">
          <Link href="/login" className={cn(buttonVariants({ size: "lg" }))}>
            Log in <ArrowRight className="size-4" />
          </Link>
          <Link
            href="/gallery"
            className={cn(buttonVariants({ size: "lg", variant: "outline" }))}
          >
            Browse gallery
          </Link>
        </div>
      </section>

      <section className="border-t bg-muted/30">
        <div className="mx-auto grid max-w-5xl gap-4 px-4 py-16 sm:grid-cols-3">
          {ROLES.map(({ icon: Icon, title, description }) => (
            <Card key={title}>
              <CardHeader>
                <Icon className="size-6 text-primary" />
                <CardTitle className="mt-2">{title}</CardTitle>
                <CardDescription>{description}</CardDescription>
              </CardHeader>
            </Card>
          ))}
        </div>
      </section>
    </div>
  );
}
