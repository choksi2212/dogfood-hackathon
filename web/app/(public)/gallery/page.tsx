import { GalleryBrowser } from "@/components/gallery-browser";
import { PageHeading } from "@/components/portal-ui";
import { Badge } from "@/components/ui/badge";
export default function GalleryPage() {
  return (
    <div>
      <PageHeading
        eyebrow="THE CLASS OF 2026"
        title="Gallery"
        description="Explore the projects that made it out of the group chat. Fresh ideas, working prototypes, and a whole lot of late nights."
        action={
          <Badge variant="secondary" className="gap-2 py-2">
            <span className="size-1.5 rounded-full bg-success" />
            Hack Hamster 2026 gallery
          </Badge>
        }
      />
      <GalleryBrowser />
    </div>
  );
}
