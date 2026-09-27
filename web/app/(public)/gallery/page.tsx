import Link from "next/link";
import { api } from "@/lib/api/client";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Card, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

export default async function GalleryPage() {
  const data = await api.gallery();

  return (
    <div>
      <h1 className="text-2xl font-bold tracking-tight">Gallery</h1>
      <p className="mt-1 text-muted-foreground">Every project submitted to this event.</p>
      {data.items.length === 0 ? (
        <Alert className="mt-6">
          <AlertDescription>No projects have been submitted yet.</AlertDescription>
        </Alert>
      ) : (
        <ul className="mt-6 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {data.items.map((item) => (
            <li key={item.id}>
              {/* Wrap the entire card in a Link so the whole tile is
                  clickable, not just the title. */}
              <Link href={`/gallery/${item.id}`} className="block h-full">
                <Card className="h-full gap-2 py-4 transition hover:border-primary hover:shadow-md">
                  <CardHeader className="gap-2">
                    <CardTitle>{item.name}</CardTitle>
                    {item.tagline && item.tagline !== item.name && (
                      <CardDescription>{item.tagline}</CardDescription>
                    )}
                    <Badge variant="secondary" className="w-fit">
                      {item.track_slug}
                    </Badge>
                  </CardHeader>
                </Card>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
