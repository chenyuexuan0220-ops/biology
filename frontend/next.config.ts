import type { NextConfig } from 'next';
const config: NextConfig = { output: 'standalone', distDir: process.env.NEXT_BUILD_DIR || '.next' };
export default config;
