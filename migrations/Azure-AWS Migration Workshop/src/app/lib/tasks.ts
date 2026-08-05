import fs from "fs";
import path from "path";
import { z } from "zod";
import { TASK_ORDER } from "./taskOrder";

export type ResolvedTask = {
  id: string;
  title: string;
  summary: string;
  phase: string;
  content: string;
};

const TASKS_DIR = path.join(process.cwd(), "data", "tasks", "en");
const INTRODUCTION_ID = "understand-migration-journey";

const frontmatterSchema = z
  .object({
    id: z.string().min(1),
    title: z.string().min(1),
    summary: z.string().min(1),
    phase: z.string().min(1),
  })
  .strict();

function parseFrontmatter(raw: string) {
  if (!raw.startsWith("---")) {
    throw new Error("Task file is missing frontmatter.");
  }
  const closing = raw.indexOf("\n---", 3);
  if (closing === -1) {
    throw new Error("Task frontmatter is not closed.");
  }

  const header = raw.slice(3, closing).trim();
  const body = raw.slice(closing + 4).replace(/^\s+/, "");
  const data: Record<string, unknown> = {};

  for (const line of header.split("\n")) {
    const trimmed = line.trim();
    if (!trimmed) continue;
    const colon = trimmed.indexOf(":");
    if (colon === -1) {
      throw new Error(`Invalid frontmatter line: ${line}`);
    }
    const key = trimmed.slice(0, colon).trim();
    const value = trimmed.slice(colon + 1).trim();
    data[key] = parseFrontmatterValue(value);
  }

  return { data, body };
}

function parseFrontmatterValue(value: string): unknown {
  if (value.startsWith("[") && value.endsWith("]")) {
    const inner = value.slice(1, -1).trim();
    if (!inner) return [];
    return inner.split(",").map((item) => item.trim().replace(/^["']|["']$/g, ""));
  }
  return value.replace(/^["']|["']$/g, "");
}

function loadTask(filePath: string): ResolvedTask {
  const raw = fs.readFileSync(filePath, "utf8");
  const { data, body } = parseFrontmatter(raw);
  const parsed = frontmatterSchema.safeParse(data);
  if (!parsed.success) {
    throw new Error(`Invalid frontmatter in ${path.basename(filePath)}: ${parsed.error.message}`);
  }

  const fileId = path.basename(filePath, ".md");
  if (fileId !== parsed.data.id) {
    throw new Error(`Task file ${fileId} does not match id ${parsed.data.id}.`);
  }

  const content = body.trim();
  if (!content) {
    throw new Error(`Task ${parsed.data.id} must include content.`);
  }

  return {
    ...parsed.data,
    content,
  };
}

export function getResolvedTasks(): ResolvedTask[] {
  const files = fs
    .readdirSync(TASKS_DIR)
    .filter((file) => file.endsWith(".md") && file !== "README.md")
    .map((file) => path.join(TASKS_DIR, file));

  const byId = new Map(files.map((file) => {
    const task = loadTask(file);
    return [task.id, task] as const;
  }));

  return TASK_ORDER.map((id) => {
    const task = byId.get(id);
    if (!task) {
      throw new Error(`TASK_ORDER references missing task ${id}.`);
    }
    return task;
  });
}

export function getWorkshopIntroduction(): ResolvedTask {
  return loadTask(path.join(TASKS_DIR, `${INTRODUCTION_ID}.md`));
}
