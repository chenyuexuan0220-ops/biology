'use client';
import { useEffect, useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { ArrowRight, ArrowLeft, Check, Clock3, LockKeyhole, BookOpen, RefreshCw } from 'lucide-react';
import { api, type Attempt, type Task } from '@/lib/api';
import { tierNames, type LessonCard, type LessonCatalog, type LessonRun } from '@/lib/lessons';
import LessonReader from './lesson-reader';

export default function Lessons({ token, studentId, contextId, writable, requestedTask, refresh }: { token: string; studentId: string; contextId: string; writable: boolean; requestedTask: Task | null; refresh: () => Promise<void> }) {
  const catalog = useQuery({ queryKey: ['lessons', token, studentId, contextId], queryFn: () => api<LessonCatalog>(`/students/${studentId}/lessons`, token), enabled: !!studentId && !!contextId });
  const [run, setRun] = useState<LessonRun | null>(null);
  const [tab, setTab] = useState('read');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notes, setNotes] = useState('');
  const [saved, setSaved] = useState(false);
  const requested = useRef('');
  const items = catalog.data?.lessons || [];
  const units = Array.from(new Map(items.map(item => [item.unit_code, { code: item.unit_code, title: item.unit_title }])).values());

  async function action(work: () => Promise<void>) { setBusy(true); setError(''); try { await work(); } catch (error) { setError(error instanceof Error ? error.message : '操作失败，请重试'); } finally { setBusy(false); } }
  function adopt(next: LessonRun) { setRun(next); setNotes(next.notes); setTab(next.result ? 'result' : next.mode === 'CHECK' ? 'check' : 'read'); }
  async function start(lesson: LessonCard, mode = 'STUDY', taskId?: string) {
    await action(async () => { adopt(await api<LessonRun>(`/students/${studentId}/lessons/${lesson.id}/start`, token, 'POST', { learning_context_id: contextId, mode, task_id: taskId || null })); await catalog.refetch(); });
  }
  useEffect(() => {
    const lessonId = requestedTask?.reason.lesson_id;
    if (!lessonId || !requestedTask || requested.current === requestedTask.id || !catalog.data) return;
    const lesson = catalog.data.lessons.find(l => l.id === lessonId);
    if (lesson) { requested.current = requestedTask.id; void start(lesson, 'STUDY', requestedTask.id); }
    // Task actions are consumed once. A new student/context remounts this component.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [requestedTask, catalog.data]);

  if (!contextId) return <section className="empty-state"><BookOpen size={34} /><h2>先设置学习起点</h2><p>保存实际生物能力后，就能看到适合的分层课程。</p></section>;
  const statusNames = { READY: '可以开始', LOCKED: '先学前置', PASSED: '本层次已达标', REINFORCE: '建议巩固', UNPUBLISHED: '内容待审核' };
  return <>
    {(error || catalog.error) && <div className="notice error" role="alert">{error || catalog.error?.message}</div>}
    {!run ? <>
      <div className="page-heading"><div><span className="eyebrow">LEARN. CONNECT. UNDERSTAND.</span><h1>把四个概念，连成真正的理解。</h1><p>细胞 → 细胞膜 → 扩散 → 渗透。每节课都包含讲解、图示、例题和检测。</p></div>{items[0] && <span className="badge">当前深度 · {tierNames[items[0].tier]}</span>}</div>
      {units.map(unit => <div className="lesson-unit-intro" key={unit.code}><div><BookOpen size={28} /><strong>{unit.title}</strong><p>先完成前置检测，再沿着知识关系前进。</p></div><span>{items.filter(l => l.unit_code === unit.code && l.state === 'PASSED').length} / {items.filter(l => l.unit_code === unit.code).length} 课时达标</span></div>)}
      {catalog.isLoading && <p className="inline-empty">正在匹配课程深度…</p>}
      <div className="lesson-path">{items.map((lesson, i) => <section key={lesson.id} className={`panel lesson-path-card state-${lesson.state.toLowerCase()}`}>
        <span className="lesson-path-index">{lesson.state === 'PASSED' ? <Check size={22} /> : String(i + 1).padStart(2, '0')}</span>
        <div className="lesson-card-body"><div className="task-tags"><span>{tierNames[lesson.tier]}</span><small>{statusNames[lesson.state]}</small>{lesson.estimated_minutes && <small><Clock3 size={12} />{lesson.estimated_minutes} 分钟</small>}</div><h2>{lesson.title}</h2><p>{lesson.summary}</p>
          {lesson.missing_prerequisites.length > 0 && <div className="lesson-blocked"><LockKeyhole size={14} /><span>需要先完成：{lesson.missing_prerequisites.map(p => p.name).join('、')}</span></div>}
          <div className="lesson-card-actions">
            {lesson.state === 'LOCKED' ? <button className="secondary" disabled={!writable || busy} onClick={() => { const target = items.find(l => lesson.missing_prerequisites.some(p => p.id === l.knowledge_id) && l.state !== 'LOCKED'); if (target) void start(target); else setError('请从当前单元第一节尚未完成的前置课开始。'); }}>去补齐前置概念<ArrowRight size={15} /></button>
              : <button className="primary" disabled={lesson.state === 'UNPUBLISHED' || !writable || busy} onClick={() => void start(lesson)}>{lesson.active_run_id ? '继续这一课' : lesson.state === 'PASSED' ? '再学一次' : lesson.state === 'REINFORCE' ? '巩固这个概念' : '开始学习'}<ArrowRight size={15} /></button>}
            {['READY', 'REINFORCE'].includes(lesson.state) && !lesson.active_run_id && <button className="text-button" disabled={!writable || busy} onClick={() => void start(lesson, 'CHECK')}>已有基础，先做检测</button>}
          </div>
        </div>
      </section>)}</div>
      {!items.length && !catalog.isLoading && <div className="empty-state"><h2>课程正在准备中</h2><p>内容发布后将按实际能力匹配。</p></div>}
      <p className="muted">{catalog.data?.note}</p>
    </> : <>
      <button className="text-button" onClick={() => { setRun(null); setError(''); }}><ArrowLeft size={15} />返回单元路径</button>
      <div className="page-heading lesson-title"><div><span className="eyebrow">{tierNames[run.lesson.tier]} · 第 {run.lesson.sequence} 课</span><h1>{run.document.title}</h1><p>{run.document.summary}</p></div><span className="date-pill"><Clock3 size={14} />约 {run.document.estimated_minutes} 分钟</span></div>
      <nav className="lesson-tabs" aria-label="课时内容"><button className={tab === 'read' ? 'selected' : ''} onClick={() => setTab('read')}>学习讲解</button><button className={tab === 'check' ? 'selected' : ''} onClick={() => setTab('check')}>随堂检测 {Object.keys(run.answers).length}/{run.questions.length}</button><button className={tab === 'notes' ? 'selected' : ''} onClick={() => setTab('notes')}>我的笔记</button>{run.result && <button className={tab === 'result' ? 'selected' : ''} onClick={() => setTab('result')}>结果与下一步</button>}</nav>
      {tab === 'read' && <section className="panel lesson-article"><LessonReader document={run.document} revisit={run.result?.revisit_sections} onCheck={() => setTab('check')} /></section>}
      {tab === 'notes' && <section className="panel"><h2>用自己的话，再解释一次。</h2><p className="muted">记录一个例子、一条推理和一个还没想清的问题。笔记不会直接增加掌握度。</p><label style={{ marginTop: 20 }}>我的学习笔记<textarea style={{ minHeight: 240 }} value={notes} maxLength={12000} onChange={e => { setNotes(e.target.value); setSaved(false); }} /></label><button className="primary" disabled={busy || !writable} onClick={() => void action(async () => { await api(`/lesson-runs/${run.id}/notes`, token, 'PATCH', { notes }); setRun({ ...run, notes }); setSaved(true); })}>保存笔记<Check size={16} /></button>{saved && <p role="status" className="muted" style={{ marginTop: 12 }}>笔记已保存，重新打开也能继续。</p>}</section>}
      {tab === 'check' && <LessonQuiz key={run.id} run={run} busy={busy || !writable} submit={(qid, eventId, answer, confidence, seconds) => action(async () => {
        const feedback = await api<Attempt>(`/lesson-runs/${run.id}/answer`, token, 'POST', { question_id: qid, event_id: eventId, answer: [answer], confidence, time_seconds: seconds });
        setRun({ ...run, answers: { ...run.answers, [qid]: { event_id: eventId, answer: [answer], correct: feedback.is_correct, feedback } } }); await refresh();
      })} finish={() => action(async () => { await api(`/lesson-runs/${run.id}/notes`, token, 'PATCH', { notes }); await api(`/lesson-runs/${run.id}/finish`, token, 'POST'); const current = await api<LessonRun>(`/lesson-runs/${run.id}`, token); adopt(current); await refresh(); })} />}
      {tab === 'result' && run.result && <section className={`panel lesson-result ${run.result.passed ? 'passed' : ''}`}><div className="result-symbol">{run.result.passed ? <Check size={30} /> : <RefreshCw size={30} />}</div><h2>{run.result.message}</h2><strong className="lesson-score">{Math.round(run.result.accuracy * 100)}<small>%</small></strong><p>达标要求：正确率至少 {Math.round(run.result.threshold * 100)}%，且前置概念题全部正确。</p><p className="muted">{run.result.mastery_note}</p>{run.result.revisit_sections.length > 0 && <button className="secondary" onClick={() => setTab('read')}>回看标记的章节</button>}<div className="lesson-next"><span className="eyebrow">YOUR NEXT STEP</span>{run.result.next_tasks.length ? run.result.next_tasks.map(task => <div key={task.id}><div><strong>{task.title}</strong><p>已更新到你的学习计划</p></div><button className="primary" disabled={busy || !writable} onClick={() => { const lesson = items.find(l => l.id === task.lesson_id); if (lesson) void start(lesson, 'STUDY', task.id); }}>开始下一步<ArrowRight size={16} /></button></div>) : <p>这个单元当前已无待推进课时。之后仍可通过复习巩固理解。</p>}</div></section>}
    </>}
  </>;
}

function LessonQuiz({ run, busy, submit, finish }: { run: LessonRun; busy: boolean; submit: (qid: string, eventId: string, answer: string, confidence: number, seconds: number) => Promise<void>; finish: () => Promise<void> }) {
  const first = run.questions.findIndex(q => !run.answers[q.id]);
  const [index, setIndex] = useState(first < 0 ? run.questions.length - 1 : first);
  const [choice, setChoice] = useState('');
  const [confidence, setConfidence] = useState(.7);
  const [eventId, setEventId] = useState(() => crypto.randomUUID());
  const timer = useRef(Date.now());
  const q = run.questions[index];
  const saved = run.answers[q.id];
  const complete = Object.keys(run.answers).length === run.questions.length;
  function selectQuestion(i: number) { setIndex(i); setChoice(''); setEventId(crypto.randomUUID()); timer.current = Date.now(); }
  return <section className="panel lesson-quiz"><div className="section-heading"><div><span className="eyebrow">CHECK YOUR UNDERSTANDING</span><h2>把理解放进一个问题</h2></div><span className="badge">{index + 1} / {run.questions.length}</span></div><div className="quiz-steps">{run.questions.map((item, i) => <button key={item.id} aria-label={`检测题 ${i + 1}`} className={index === i ? 'current' : run.answers[item.id] ? 'answered' : ''} onClick={() => selectQuestion(i)}>{run.answers[item.id] ? <Check size={15} /> : i + 1}</button>)}</div><h3 className="question-stem">{q.stem}</h3><div className="options">{q.options.map(option => <button key={option.label} disabled={!!saved || busy} className={`option ${(saved?.answer[0] || choice) === option.label ? 'selected' : ''} ${saved?.feedback.correct_answer.includes(option.label) ? 'correct' : ''}`} onClick={() => setChoice(option.label)}><span>{option.label}</span>{option.text}</button>)}</div>{saved ? <div className={`answer-result ${saved.correct ? 'right' : 'wrong'}`}><h3>{saved.correct ? '判断正确' : '这个概念值得再想一想'}</h3><p>{saved.feedback.explanation}</p><p>参考答案：{saved.feedback.correct_answer.join('、')}</p></div> : <div className="question-submit"><label>你有多确定？<select value={confidence} onChange={e => setConfidence(Number(e.target.value))}><option value={.9}>很确定</option><option value={.7}>比较确定</option><option value={.3}>不太确定</option></select></label><button className="primary" disabled={busy || !choice} onClick={() => void submit(q.id, eventId, choice, confidence, Math.min(3600, Math.round((Date.now() - timer.current) / 1000)))}>提交本题<ArrowRight size={16} /></button></div>}<div className="quiz-footer">{saved && index < run.questions.length - 1 && <button className="secondary" onClick={() => selectQuestion(index + 1)}>下一题<ArrowRight size={15} /></button>}{complete && <button className="primary" disabled={busy} onClick={() => void finish()}>{run.result ? '查看结果' : '完成检测并更新学习计划'}</button>}</div></section>;
}
