import { z } from 'zod';
export const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';
export const userSchema = z.object({ id: z.string(), name: z.string(), is_admin: z.boolean() });
export const authSchema = z.object({ access_token: z.string(), user: userSchema });
export type User = z.infer<typeof userSchema>;
export type Student = { id: string; name: string; role: string };
export type Context = { id: string; education_stage: string; school_grade: number; biology_level: string; competition_goal: string; weekly_hours: number; preferred_learning_days: number; status: string };
export type Metadata = { education_stages: string[]; biology_levels: string[]; competition_goals: string[] };
export type Knowledge = { id: string; name: string; code: string; domain_id: string; description: string; level: number };
export type Question = { id: string; stem: string | null; question_type: string; answer_format?: string; options: { label: string; text: string }[]; source_question_no: number; paper_id: string; learning_difficulty: number; competition_difficulty: number; answer?: string[] | null; explanation?: string; status: string; metadata_json?: { source_pages?: number[]; review_notes?: string[] } };
export type Task = { id: string; title: string; task_type: string; task_date: string; description: string; estimated_minutes: number; status: string; knowledge_ids: string[]; question_ids: string[]; reason: { lesson_id?: string; revision_id?: string; unit_progression?: boolean; primary_reason: string; knowledge_gap: number; prerequisite_reason: string; competition_reason: string; competency_reason: string; why_now: string } };
export type Plan = { plan: { id: string; estimated_minutes: number; start_date: string; end_date: string } | null; tasks: Task[] };
export type Report = { question_count: number; accuracy: number | null; learning_minutes: number; knowledge_count: number; evidence_count: number; average_mastery: number; due_reviews: number; note: string };
export type Mastery = { knowledge_id: string; name: string; overall_score: number; scores: number[]; exposure_count: number; next_review_at: string; confidence: number };
export type Competency = { id: string; name: string; score: number; evidence_count: number };
export type Attempt = { id: string; is_correct: boolean; correct_answer: string[]; explanation: string; error_type?: string; error_note?: string };
export type Diagnostic = { id: string; questions: Question[]; result?: { accuracy: number; recommended_level: string; note: string } };
export type Experiment = { id: string; title: string; description: string; safety: string; steps: { sequence: number; instruction: string }[] };
export async function api<T>(path: string, token = '', method = 'GET', body?: unknown): Promise<T> {
  const response = await fetch(`${API}${path}`, { method, headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) }, ...(body !== undefined ? { body: JSON.stringify(body) } : {}) });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : '提交内容格式不正确，请检查填写信息');
  return data as T;
}
