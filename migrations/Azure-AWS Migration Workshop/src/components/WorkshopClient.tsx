"use client";

import { useEffect, useState } from "react";
import type { ResolvedTask } from "@/app/lib/tasks";
import MarkdownContent from "@/components/MarkdownContent";

type WorkshopClientProps = {
  introduction: ResolvedTask;
  initialTasks: ResolvedTask[];
};

type ProgressMap = Record<string, boolean>;

const STORAGE_KEY = "azure-bedrock-migration-workshop-progress-v1";

export default function WorkshopClient({ introduction, initialTasks }: WorkshopClientProps) {
  const [expandedTasks, setExpandedTasks] = useState<Record<string, boolean>>({});
  const [progress, setProgress] = useState<ProgressMap>({});

  useEffect(() => {
    const saved = window.localStorage.getItem(STORAGE_KEY);
    if (!saved) return;

    let restored: ProgressMap;
    try {
      restored = JSON.parse(saved) as ProgressMap;
    } catch {
      window.localStorage.removeItem(STORAGE_KEY);
      return;
    }

    const frame = window.requestAnimationFrame(() => setProgress(restored));
    return () => window.cancelAnimationFrame(frame);
  }, []);

  const completed = initialTasks.filter((task) => progress[task.id]).length;
  const total = initialTasks.length;
  const percent = total ? Math.round((completed / total) * 100) : 0;
  const remaining = Math.max(total - completed, 0);

  function updateCompletion(taskId: string, done: boolean) {
    const next = { ...progress };
    if (done) next[taskId] = true;
    else delete next[taskId];
    setProgress(next);
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
  }

  function toggleTaskDetails(taskId: string) {
    setExpandedTasks((current) => ({ ...current, [taskId]: !current[taskId] }));
  }

  return (
    <main className="training-page">
      <section className="top-progress" aria-label="Overall progress">
        <div className="top-progress-meta">
          <span>Overall progress</span>
          <span>
            {completed}/{total} tasks · {remaining} {remaining === 1 ? "task" : "tasks"} left
          </span>
        </div>
        <div className="progress-track">
          <div className="progress-fill" style={{ width: `${percent}%` }} />
        </div>
      </section>

      <section className="training-hero">
        <div>
          <p className="eyebrow">Workshop</p>
          <h1>Azure OpenAI To AWS Migration Workshop</h1>
          <p>
            Migrate an Azure OpenAI Chat Completions application to Amazon Bedrock Responses with
            Codex Desktop. Progress is stored privately in this browser.
          </p>
        </div>
      </section>

      <section className="workshop-content-grid single">
        <section className="tasks-panel" aria-label="Workshop tasks">
          <div className="tasks-panel-header">
            <div>
              <h2>Tasks</h2>
              <p>Work through the migration in order. Your progress is saved locally.</p>
            </div>
            <strong>
              {completed}/{total}
            </strong>
          </div>

          <div className="task-list">
            <div>
              <h3 className="phase-heading">{introduction.phase}</h3>
              <article className="task-card intro-card" aria-label="Workshop introduction">
                <div className="task-main">
                  <div className="task-title-row">
                    <h3 className="task-title intro-title">{introduction.title}</h3>
                  </div>
                  <p className="task-summary">{introduction.summary}</p>
                  <div className="task-body">
                    <MarkdownContent content={introduction.content} />
                  </div>
                </div>
              </article>
            </div>

            {initialTasks.map((task, index) => {
              const done = Boolean(progress[task.id]);
              const isExpanded = !done || Boolean(expandedTasks[task.id]);
              const phaseChanged = index === 0 || initialTasks[index - 1].phase !== task.phase;
              const checkboxId = `task-checkbox-${task.id}`;
              const bodyId = `task-body-${task.id}`;

              return (
                <div key={task.id}>
                  {phaseChanged ? <h3 className="phase-heading">{task.phase}</h3> : null}
                  <article className={`task-card ${isExpanded ? "expanded" : ""} ${done ? "done" : ""}`}>
                    <div className="task-shell">
                      <input
                        id={checkboxId}
                        type="checkbox"
                        className="task-checkbox"
                        checked={done}
                        onChange={() => updateCompletion(task.id, !done)}
                      />
                      <div className="task-main">
                        <div className="task-title-row">
                          <label htmlFor={checkboxId} className="task-title">
                            {task.title}
                          </label>
                        </div>
                        <p className="task-summary">{task.summary}</p>

                        {isExpanded ? (
                          <div id={bodyId} className="task-body">
                            <MarkdownContent content={task.content} />
                          </div>
                        ) : (
                          <p id={bodyId} className="task-collapsed">
                            Completed.
                            <button
                              type="button"
                              className="details-toggle"
                              onClick={() => toggleTaskDetails(task.id)}
                              aria-controls={bodyId}
                              aria-expanded={isExpanded}
                            >
                              Show details
                            </button>
                          </p>
                        )}

                        {done && isExpanded ? (
                          <button
                            type="button"
                            className="details-toggle details-toggle-block"
                            onClick={() => toggleTaskDetails(task.id)}
                            aria-controls={bodyId}
                            aria-expanded={isExpanded}
                          >
                            Hide details
                          </button>
                        ) : null}
                      </div>
                    </div>
                  </article>
                </div>
              );
            })}
          </div>
        </section>
      </section>
    </main>
  );
}
