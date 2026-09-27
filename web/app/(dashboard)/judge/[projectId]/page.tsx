import { cookies } from "next/headers";
import { notFound } from "next/navigation";
import { api } from "@/lib/api/client";
import { ScoreForm } from "./ScoreForm";

export default async function JudgeScorePage({
  params,
}: {
  params: Promise<{ projectId: string }>;
}) {
  const { projectId } = await params;
  const cookieHeader = (await cookies()).toString();

  const [batch, event] = await Promise.all([
    api.meBatch(undefined, cookieHeader),
    api.eventDetail(undefined, cookieHeader),
  ]);

  const project = batch.projects.find((p) => p.id === projectId);
  if (!project) {
    notFound();
  }

  const criteria = event.rubric?.criteria ?? [];

  return (
    <div>
      <h1 className="text-2xl font-bold tracking-tight">{project.name}</h1>
      <p className="mt-1 text-muted-foreground">{project.tagline}</p>
      <div className="mt-6">
        <ScoreForm projectId={project.id} criteria={criteria} />
      </div>
    </div>
  );
}
