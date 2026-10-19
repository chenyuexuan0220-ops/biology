'use client';

import { useState, type FormEvent } from 'react';
import JSZip from 'jszip';
import { Download, FileUp } from 'lucide-react';
import { API } from '@/lib/api';

type Draft = { kind: 'textbook' | 'exam'; title: string; files: Record<string, string>; warnings: string[]; characters: number; file_count: number };

export default function SourceUpload({ token }: { token: string }) {
  const [kind, setKind] = useState<'textbook' | 'exam'>('exam');
  const [draft, setDraft] = useState<Draft | null>(null);
  const [selected, setSelected] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  async function upload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError('');
    setDraft(null);
    const form = new FormData(event.currentTarget);
    form.set('kind', kind);
    try {
      const response = await fetch(`${API}/admin/source-drafts`, { method: 'POST', headers: { Authorization: `Bearer ${token}` }, body: form });
      const result = await response.json();
      if (!response.ok) throw new Error(typeof result.detail === 'string' ? result.detail : '文件提取失败');
      const next = result as Draft;
      setDraft(next);
      setSelected(Object.keys(next.files)[0]);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : '文件提取失败');
    } finally {
      setBusy(false);
    }
  }

  async function download() {
    if (!draft) return;
    const archive = new JSZip();
    for (const [name, content] of Object.entries(draft.files)) archive.file(name, content);
    const blob = await archive.generateAsync({ type: 'blob' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = `${draft.kind === 'exam' ? 'questions' : 'resources'}-draft.zip`;
    link.click();
    setTimeout(() => URL.revokeObjectURL(link.href), 1000);
  }

  return <div className="source-upload">
    <section className="panel">
      <h2>上传电子资料</h2>
      <form onSubmit={e => void upload(e)}>
        <div className="source-mode" role="group" aria-label="资料类型">
          <button type="button" className={kind === 'exam' ? 'primary' : 'secondary'} aria-pressed={kind === 'exam'} onClick={() => { setKind('exam'); setDraft(null); }}>试卷</button>
          <button type="button" className={kind === 'textbook' ? 'primary' : 'secondary'} aria-pressed={kind === 'textbook'} onClick={() => { setKind('textbook'); setDraft(null); }}>教材</button>
        </div>
        <div className="form-grid">
          <label>PDF 或 Word 文件<input type="file" name="file" accept=".pdf,.docx" required /></label>
          <label>{kind === 'exam' ? '试卷标题' : '教材标题'}<input name="title" maxLength={200} required /></label>
          {kind === 'exam' ? <label>试卷编码<input name="code" pattern="[A-Za-z0-9_]+" maxLength={80} required placeholder="league_2024" /></label> : <input type="hidden" name="code" value="textbook" />}
        </div>
        <label className="source-ai-option"><input type="checkbox" name="ai_enhance" value="true" />使用 AI 辅助识别知识点与关系（单次最多 40 个文本片段）</label>
        <p className="muted">启用 AI 后，章节或题目文字会发送到你在后端配置的模型服务。结果仍需在 knowledge_review.yaml 核对。单文件最多 20 MB；扫描版 PDF 需先 OCR，.doc 请另存为 .docx。</p>
        <button className="primary" disabled={busy}><FileUp size={16} />{busy ? '正在提取…' : '提取 YAML 草稿'}</button>
      </form>
      {error && <p className="notice" role="alert">{error}</p>}
    </section>
    {draft && <section className="panel">
      <div className="section-heading"><div><h2>{draft.title}</h2><p className="muted">提取 {draft.characters.toLocaleString()} 字，生成 {draft.file_count} 个 YAML 文件</p></div><button className="secondary" onClick={() => void download()}><Download size={16} />下载全部 ZIP</button></div>
      <div className="notice">{draft.warnings.join('；')}。请先看 knowledge_review.yaml，核对各章节或题目的候选知识点与关系，再把确认后的 YAML 放入 seed 目录。</div>
      <div className="source-preview"><select aria-label="预览 YAML 文件" value={selected} onChange={e => setSelected(e.target.value)}>{Object.keys(draft.files).map(name => <option key={name}>{name}</option>)}</select><pre>{draft.files[selected]}</pre></div>
    </section>}
  </div>;
}
