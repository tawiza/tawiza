import nextConfig from "eslint-config-next";

export default [
  ...nextConfig,
  {
    rules: {
      // TODO: migrate data fetching away from setState-in-useEffect pattern
      "react-hooks/set-state-in-effect": "warn",
      // TODO: fix ref mutations to use useEffect
      "react-hooks/immutability": "warn",
      "react-hooks/refs": "warn",
      // TODO: extract inline component definitions outside render
      "react-hooks/static-components": "warn",
    },
  },
];
