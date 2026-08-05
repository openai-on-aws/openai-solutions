import WorkshopClient from "@/components/WorkshopClient";
import { getResolvedTasks, getWorkshopIntroduction } from "@/app/lib/tasks";

export default function PreviewPage() {
  const tasks = getResolvedTasks();
  const introduction = getWorkshopIntroduction();
  return <WorkshopClient introduction={introduction} initialTasks={tasks} />;
}
