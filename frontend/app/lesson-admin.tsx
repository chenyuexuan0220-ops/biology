'use client';
import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { tierNames, type LessonRevision, type LessonDocument } from '@/lib/lessons';
import LessonReader from './lesson-reader';

export default function LessonAdmin({ token }: { token: string }) {
  const queue = useQuery({ queryKey: ['lesson-reviews', token], queryFn: () => api<LessonRevision[]>('/admin/lessons', token) });
  const [selected, setSelected] = useState('');
  const [document, setDocument] = useState<LessonDocument | null>(null);
  const [editing, setEditing] = useState(false);
  const [note, setNote] = useState('');
  const [checks, setChecks] = useState<string[]>([]);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const rev = queue.data?.find(r => r.id === selected);
  function open(revision: LessonRevision) { setSelected(revision.id); setDocument(structuredClone(revision.document)); setEditing(false); setNote(''); setChecks([]); setError(''); }
  async function action(work: () => Promise<void>) { setBusy(true); setError(''); try { await work(); await queue.refetch(); } catch (e) { setError(e instanceof Error ? e.message : '操作失败'); } finally { setBusy(false); } }
  const checklist = ['知识与前置关系', '讲解、图示与例题', '选项、答案与解析', '难度与补习指向'];
  return <>
    <div className="notice">首批课程为待审核初稿。请逐项核对后审核，再发布。修订会另存为新版本，已学内容与证据保留。</div>
    {(error || queue.error) && <div className="notice error" role="alert">{error || queue.error?.message}</div>}
    <div className="lesson-review-layout"><aside className="panel lesson-review-list"><h3>分层课程 · {queue.data?.length || 0} 个版本</h3>{queue.data?.map(r => <button key={r.id} className={r.id === selected ? 'selected' : ''} onClick={() => open(r)}><span>{r.lesson.sequence} · {tierNames[r.lesson.tier]} · v{r.version}</span><strong>{r.document.title}</strong><small>{r.status === 'PUBLISHED' ? '已发布' : r.status === 'REVIEWED' ? '审核通过，待发布' : r.status === 'ARCHIVED' ? '已归档' : '待审核'}</small></button>)}</aside>
    {rev && document ? <section className="panel lesson-review-document"><div className="section-heading"><div><span className="eyebrow">内容版本 v{rev.version}</span><h2>{document.title}</h2></div><button className="secondary" onClick={() => setEditing(!editing)}>{editing ? '阅读预览' : '修订内容'}</button></div>
      {editing ? <form onSubmit={e => { e.preventDefault(); void action(async () => { const next = await api<LessonRevision>(`/admin/lessons/${rev.id}/revisions`, token, 'POST', { document }); setSelected(next.id); setEditing(false); setChecks([]); }); }}>
        <label>标题<input required value={document.title} onChange={e => setDocument({ ...document, title: e.target.value })} /></label><label>课程简介<textarea required value={document.summary} onChange={e => setDocument({ ...document, summary: e.target.value })} /></label>
        <label>低年级阅读引导<textarea value={document.adaptations?.junior || ''} onChange={e => setDocument({ ...document, adaptations: { junior: e.target.value, senior: document.adaptations?.senior || '' } })} /></label><label>高年级阅读引导<textarea value={document.adaptations?.senior || ''} onChange={e => setDocument({ ...document, adaptations: { senior: e.target.value, junior: document.adaptations?.junior || '' } })} /></label>
        {document.sections.map((section, index) => <div key={section.id}><label>章节 {index + 1} 标题<input value={section.title} onChange={e => setDocument({ ...document, sections: document.sections.map((s, i) => i === index ? { ...s, title: e.target.value } : s) })} /></label><label>章节正文<textarea style={{ minHeight: 180 }} value={section.text} onChange={e => setDocument({ ...document, sections: document.sections.map((s, i) => i === index ? { ...s, text: e.target.value } : s) })} /></label></div>)}
        {document.checks?.map((q, index) => <details key={q.id}><summary>修改检测题 {index + 1}</summary><label>题干<textarea value={q.stem} onChange={e => setDocument({ ...document, checks: document.checks?.map((item, i) => i === index ? { ...item, stem: e.target.value } : item) })} /></label>{Object.entries(q.options).map(([label, text]) => <label key={label}>选项 {label}<input value={text} onChange={e => setDocument({ ...document, checks: document.checks?.map((item, i) => i === index ? { ...item, options: { ...item.options, [label]: e.target.value } } : item) })} /></label>)}<label>答案<select value={q.answer} onChange={e => setDocument({ ...document, checks: document.checks?.map((item, i) => i === index ? { ...item, answer: e.target.value } : item) })}>{Object.keys(q.options).map(key => <option key={key}>{key}</option>)}</select></label><label>解析<textarea value={q.explanation} onChange={e => setDocument({ ...document, checks: document.checks?.map((item, i) => i === index ? { ...item, explanation: e.target.value } : item) })} /></label></details>)}
        <button className="primary" disabled={busy}>保存为新版本，重新审核</button>
      </form> : <><LessonReader document={{ ...document, grade_guidance: document.adaptations?.junior }} /><section className="lesson-review-checks"><h2>随堂检测与补习对应</h2>{document.checks?.map((q, i) => <div key={q.id}><h3>{i + 1}. {q.stem}</h3>{Object.entries(q.options).map(([label, text]) => <p key={label}>{label}. {text}</p>)}<p><strong>答案 {q.answer}</strong> · {q.explanation}</p><small>认知层次 L{q.cognitive_level} · 回看：{document.sections.find(s => s.id === q.revisit_section)?.title}{q.prerequisite_code ? ` · 前置概念 ${q.prerequisite_code}` : ''}</small></div>)}</section>
        {rev.status !== 'PUBLISHED' && rev.status !== 'ARCHIVED' && <div className="lesson-review-gate"><h3>发布前核对</h3>{checklist.map(label => <label key={label}><input type="checkbox" checked={checks.includes(label)} onChange={e => setChecks(e.target.checked ? [...checks, label] : checks.filter(c => c !== label))} />{label}</label>)}<label>审核结论<textarea value={note} minLength={5} onChange={e => setNote(e.target.value)} placeholder="记录核查结论和需要说明的内容边界" /></label><button className="primary" disabled={busy || note.trim().length < 5 || checks.length !== checklist.length} onClick={() => void action(async () => { await api(`/admin/lessons/${rev.id}/review`, token, 'POST', { decision: rev.status === 'REVIEWED' ? 'PUBLISHED' : 'REVIEWED', note }); setChecks([]); setNote(''); })}>{rev.status === 'REVIEWED' ? '确认发布这一版本' : '审核通过，进入待发布'}</button></div>}
      </>}
    </section> : <section className="empty-state"><h2>选择一节课，逐项核对</h2><p>学生只会学习已发布的版本。</p></section>}</div>
  </>;
}
