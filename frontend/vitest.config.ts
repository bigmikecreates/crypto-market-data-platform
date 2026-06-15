import path from "path";
import { defineConfig } from "vitest/config";

export default defineConfig({
  oxc: {
    jsx: "automatic",
  },
  test: {
    environment: "jsdom",
    globals: true,
    include: ["**/*.test.{ts,tsx}"],
    setupFiles: ["./test-setup.ts"],
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "."),
    },
  },
});
