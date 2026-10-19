import type { Question, Attempt } from './api';
export type Tier = 'INTRO' | 'APPLICATION' | 'COMPETITION';
export const tierNames: Record<Tier, string> = { INTRO: '入门理解', APPLICATION: '情境应用', COMPETITION: '竞赛推理' };
export type LessonDocument = {
  title: string; summary: string; objectives: string[]; estimated_minutes: number; prerequisites: string[];
  sections: { id: string; title: string; text: string }[];
  diagram: { kind: 'CELL' | 'MEMBRANE' | 'DIFFUSION' | 'OSMOSIS' | 'TISSUES'; caption: string; labels: string[] };
  examples: { prompt: string; reasoning: string }[]; misconceptions: { claim: string; correction: string }[];
  pass_ratio: number; sources: string[]; grade_guidance?: string; adaptations?: { junior: string; senior: string };
  checks?: { id: string; stem: string; options: Record<string, string>; answer: string; explanation: string; cognitive_level: number; competency_code: string; revisit_section: string; prerequisite_code: string | null; evidence_kind: string }[];
};
export type Lesson = { id: string; code: string; unit_code: string; unit_title: string; tier: Tier; knowledge_id: string; sequence: number; min_level: number; max_level: number };
export type LessonResult = { run_id: string; accuracy: number; passed: boolean; threshold: number; prerequisite_gaps: string[]; revisit_sections: string[]; message: string; mastery_note: string; next_tasks: { id: string; title: string; lesson_id: string }[] };
export type LessonCard = Lesson & { name: string; state: 'UNPUBLISHED' | 'LOCKED' | 'PASSED' | 'REINFORCE' | 'READY'; title: string; summary: string; estimated_minutes: number | null; revision_id: string | null; active_run_id: string | null; missing_prerequisites: { id: string; code: string; name: string }[]; last_result: LessonResult | null };
export type LessonCatalog = { learning_context_id: string; biology_level: string; lessons: LessonCard[]; note: string };
export type LessonRun = { id: string; student_id: string; learning_context_id: string; revision_id: string; mode: string; status: string; lesson: Lesson; document: LessonDocument; notes: string; questions: Question[]; answers: Record<string, { event_id: string; answer: string[]; correct: boolean; feedback: Attempt }>; result: LessonResult | null };
export type LessonRevision = { id: string; lesson_id: string; version: number; status: string; document: LessonDocument; lesson: Lesson };
