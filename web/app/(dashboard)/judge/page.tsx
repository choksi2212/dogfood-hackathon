import { cookies } from "next/headers";
import { ClipboardCheck } from "lucide-react";
import { api, ApiError } from "@/lib/api/client";
import { EmptyState, LoadError, PageHeading } from "@/components/portal-ui";
import { JudgeBatch } from "./JudgeBatch";

export default async function JudgePage() {
  const cookieHeader = (await cookies()).toString();
  let batch;
  try {
    batch = await api.meBatch(undefined, cookieHeader);
  } catch (error) {
    if (error instanceof ApiError && error.status === 403) {
      return (
        <>
          <PageHeading
            eyebrow="JUDGING / YOUR WORKSPACE"
            title="Your batch"
            description="Give every project a considered review."
          />
          <EmptyState
            icon={ClipboardCheck}
            title="No batch assigned yet"
            description="The organizer assigns projects to each judge. Your workspace will be ready as soon as an assignment arrives."
          />
        </>
      );
    }
    return (
      <LoadError
        title="We couldn’t load your batch"
        description="Please try again to see your assigned projects."
        href="/judge"
      />
    );
  }

  const projects = Array.from(
    new Map(batch.projects.map((project) => [project.id, project])).values(),
  );
  return <JudgeBatch projects={projects} progress={batch.progress} />;
}
