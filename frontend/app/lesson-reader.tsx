'use client';
import { useId } from 'react';
import { BookOpen, Lightbulb, ShieldCheck } from 'lucide-react';
import type { LessonDocument } from '@/lib/lessons';

export function LessonDiagram({ diagram }: { diagram: LessonDocument['diagram'] }) {
  const marker = useId().replaceAll(':', '');
  const membrane = diagram.kind === 'MEMBRANE';
  return <figure className="lesson-diagram">
    <svg viewBox="0 0 640 250" role="img" aria-label={diagram.caption}>
      <defs><marker id={marker} markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto"><path d="M0,0 L6,3 L0,6" fill="none" stroke="#42745b" strokeWidth="1.5" /></marker></defs>
      {diagram.kind === 'TISSUES' ? <>
        <rect x="32" y="28" width="276" height="88" rx="12" fill="#f1f5e9" stroke="#b7c7a7" />
        {Array.from({ length: 8 }, (_, i) => <ellipse key={'e' + i} cx={62 + i * 32} cy="70" rx="13" ry="24" fill="#d7e3c7" stroke="#78956d" />)}
        <text x="42" y="105">{diagram.labels[0]}</text>
        <rect x="332" y="28" width="276" height="88" rx="12" fill="#f7f2e8" stroke="#d5c4a4" />
        <path d="M355 52 C400 104 452 36 496 91 S560 48 590 82" fill="none" stroke="#b59668" strokeWidth="5" />
        {[370, 440, 520, 575].map((x, i) => <circle key={'c' + i} cx={x} cy={i % 2 ? 78 : 58} r="8" fill="#dbc89e" />)}
        <text x="342" y="105">{diagram.labels[1]}</text>
        <rect x="32" y="136" width="276" height="88" rx="12" fill="#f7ece9" stroke="#d5aaa2" />
        {[0, 1, 2].map(i => <g key={'m' + i}><rect x="52" y={151 + i * 21} width="230" height="13" rx="6" fill="#d89c91" /><path d={`M65 ${157 + i * 21} h200`} stroke="#fff5ee" strokeDasharray="12 8" /></g>)}
        <text x="42" y="214">{diagram.labels[2]}</text>
        <rect x="332" y="136" width="276" height="88" rx="12" fill="#edf2f4" stroke="#aabdc2" />
        <circle cx="450" cy="176" r="18" fill="#a4bdc1" /><path d="M450 158 V145 M434 166 L395 150 M434 185 L390 205 M467 176 H555 M555 176 l28 -18 M555 176 l28 18" stroke="#698c92" strokeWidth="4" fill="none" />
        <text x="342" y="214">{diagram.labels[3]}</text>
      </> : diagram.kind === 'CELL' ? <>
        <ellipse cx="265" cy="125" rx="158" ry="96" fill="#eef4e2" stroke="#59805d" strokeWidth="5" />
        <ellipse cx="283" cy="122" rx="47" ry="40" fill="#d5dfb2" stroke="#91a776" strokeWidth="2" /><circle cx="290" cy="125" r="13" fill="#9eae7f" />
        {[0, 1, 2].map(i => <ellipse key={i} cx={178 + i * 84} cy={i === 1 ? 182 : 82} rx="20" ry="9" fill="#e0e8ca" stroke="#93a779" />)}
        <path d="M415 101 L461 60 H514 M187 147 L93 202 H59 M306 125 H500" stroke="#829a79" fill="none" />
        <text x="464" y="47">{diagram.labels[0]}</text><text x="47" y="229">{diagram.labels[1]}</text><text x="504" y="129">{diagram.labels[2]}</text>
      </> : membrane ? <>
        <rect x="44" y="72" width="552" height="98" rx="18" fill="#f3f5e8" />
        {Array.from({ length: 21 }, (_, i) => <g key={i}><circle cx={62 + i * 25} cy="89" r="8" fill="#98b185" /><path d={`M${58 + i * 25} 97 v22 m8 -22 v22 M${58 + i * 25} 144 v-22 m8 22 v-22`} stroke="#b8c695" strokeWidth="3" /><circle cx={62 + i * 25} cy="152" r="8" fill="#98b185" /></g>)}
        <rect x="278" y="61" width="67" height="125" rx="24" fill="#718e68" /><path d="M311 78 V170" stroke="#edf3df" strokeWidth="12" />
        <text x="52" y="41">{diagram.labels[0]}</text><text x="52" y="222">{diagram.labels[3]}</text><text x="440" y="210">{diagram.labels[1]}</text><text x="282" y="219">{diagram.labels[2]}</text>
      </> : <>
        <rect x="50" y="47" width="540" height="160" rx="14" fill="#f2f7ed" stroke="#b5c5a7" />
        {diagram.kind === 'OSMOSIS' && <path d="M320 47 V207" stroke="#8aab8d" strokeWidth="8" strokeDasharray="7 5" />}
        {Array.from({ length: diagram.kind === 'OSMOSIS' ? 5 : 14 }, (_, i) => <circle key={'l' + i} cx={81 + (i % 5) * 42} cy={78 + Math.floor(i / 5) * 42} r="7" fill="#769c70" />)}
        {Array.from({ length: diagram.kind === 'OSMOSIS' ? 14 : 5 }, (_, i) => <circle key={'r' + i} cx={367 + (i % 5) * 42} cy={78 + Math.floor(i / 5) * 42} r="7" fill="#769c70" />)}
        <path d="M240 181 H391" stroke="#42745b" strokeWidth="3" markerEnd={`url(#${marker})`} />
        <text x="50" y="30">{diagram.labels[0]}</text><text x="367" y="30">{diagram.labels[diagram.labels.length - 1]}</text>
        <text x="240" y="237">{diagram.kind === 'OSMOSIS' ? diagram.labels[2] : diagram.labels[1]}</text>
      </>}
    </svg><figcaption>{diagram.caption}</figcaption>
  </figure>;
}

export default function LessonReader({ document, revisit = [], onCheck }: { document: LessonDocument; revisit?: string[]; onCheck?: () => void }) {
  return <div className="lesson-reading">
    <div className="lesson-objectives"><span className="eyebrow">TODAY, YOU WILL UNDERSTAND</span><h2>这节课，你会学到</h2><ul>{document.objectives.map(o => <li key={o}>{o}</li>)}</ul></div>
    {document.grade_guidance && <p className="lesson-guidance"><Lightbulb size={19} />{document.grade_guidance}</p>}
    <LessonDiagram diagram={document.diagram} />
    {document.sections.map((section, i) => <section key={section.id} id={`lesson-${section.id}`} className={`lesson-section ${revisit.includes(section.id) ? 'needs-review' : ''}`}><span className="section-counter">0{i + 1}</span><div>{revisit.includes(section.id) && <span className="badge amber">本次错题建议回看</span>}<h2>{section.title}</h2><p>{section.text}</p></div></section>)}
    <section className="lesson-examples"><span className="eyebrow">THINK IT THROUGH</span><h2><BookOpen size={20} />跟着一个例子想清楚</h2>{document.examples.map((example, i) => <div key={i}><h3>{example.prompt}</h3><details><summary>先自己想一想，再展开推理</summary><p>{example.reasoning}</p></details></div>)}</section>
    <section className="lesson-misconceptions"><h2><ShieldCheck size={20} />容易混淆的地方</h2>{document.misconceptions.map((item, i) => <div key={i}><h3>“{item.claim}”</h3><p>{item.correction}</p></div>)}</section>
    <details className="lesson-sources"><summary>内容来源与模型边界</summary>{document.sources.map(s => <p key={s}>{s}</p>)}</details>
    {onCheck && <div className="lesson-check-invite"><div><strong>读懂之后，用一个新问题检验自己。</strong><p>完成全部检测后，我们会安排巩固、前置补习或下一课。</p></div><button className="primary" onClick={onCheck}>开始随堂检测 →</button></div>}
  </div>;
}
