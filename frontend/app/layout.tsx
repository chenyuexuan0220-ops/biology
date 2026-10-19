import type { Metadata } from 'next';
import './globals.css';
export const metadata: Metadata = { title: '知生 · 生物竞赛学习', description: '以证据为基础，为每位学生生成生物学习路径' };
export default function RootLayout({ children }: { children: React.ReactNode }) {
  return <html lang="zh-CN"><body>{children}</body></html>;
}
