import { cookies } from "next/headers";
import { notFound } from "next/navigation";
import { api } from "@/lib/api/client";
import { ScoreForm } from "./ScoreForm";
import { PageHeader } from "@/components/PageHeader";

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
      <PageHeader title={project.name} description={project.tagline} />
      <ScoreForm projectId={project.id} criteria={criteria} />
    </div>
  );
}
