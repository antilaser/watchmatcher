import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      colors: {
        surface: {
          DEFAULT: "#0f1419",
          raised: "#161c24",
          border: "#243042",
        },
        accent: { DEFAULT: "#3d8bfd", muted: "#6b9ef5" },
      },
    },
  },
  plugins: [],
};

export default config;
