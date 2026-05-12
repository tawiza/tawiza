// Type declarations for non-code assets imported via Next.js. TypeScript 6
// is stricter about side-effect imports of files that have no type
// declarations (TS2882), so we declare every CSS-style extension as a
// known module returning whatever the bundler exposes (here unknown,
// since we never read the value).

declare module "*.css";
declare module "*.scss";
declare module "*.sass";
declare module "*.less";
