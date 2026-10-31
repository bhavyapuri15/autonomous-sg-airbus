import core from "eslint-config-next/core-web-vitals";
import ts from "eslint-config-next/typescript";
const eslintConfig = [...core, ...ts, { ignores: [".next/**", "node_modules/**", "next-env.d.ts"] }];
export default eslintConfig;
