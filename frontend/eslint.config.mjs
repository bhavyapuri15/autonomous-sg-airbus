import core from "eslint-config-next/core-web-vitals";
import ts from "eslint-config-next/typescript";
const eslintConfig = [...core, ...ts, // components/reactbits: vendored third-party React Bits source, kept as upstream wrote it
  { ignores: [".next/**", "node_modules/**", "next-env.d.ts", "components/reactbits/**"] }];
export default eslintConfig;
