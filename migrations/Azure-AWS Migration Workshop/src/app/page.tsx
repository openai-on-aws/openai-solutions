import { getResolvedTasks, getWorkshopIntroduction } from "@/app/lib/tasks";
import WorkshopClient from "@/components/WorkshopClient";

export default function HomePage() {
  const tasks = getResolvedTasks();
  const introduction = getWorkshopIntroduction();
  return <WorkshopClient introduction={introduction} initialTasks={tasks} />;
}
