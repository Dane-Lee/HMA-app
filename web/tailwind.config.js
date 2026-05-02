export default {
    content: ["./index.html", "./src/**/*.{ts,tsx}"],
    theme: {
        extend: {
            colors: {
                // CSS-variable tokens — swap automatically on theme change
                depth:   "rgb(var(--color-depth) / <alpha-value>)",
                surface: "rgb(var(--color-surface) / <alpha-value>)",
                ink:     "rgb(var(--color-ink) / <alpha-value>)",
                mist:    "rgb(var(--color-mist) / <alpha-value>)",
                // Semi-transparent overlay tokens (no opacity modifier needed)
                panel:      "var(--color-panel)",
                "panel-mid":"var(--color-panel-mid)",
                "panel-hi": "var(--color-panel-hi)",
                rim:        "var(--color-rim)",
                // Static tokens — never change between themes
                accent: "#c8192e",
                brand:  "#0e1d27",
                clay:   "#e8754e",
                sand:   "#c4b99a",
            },
            boxShadow: {
                card: "0 8px 32px rgba(0,0,0,0.4), 0 1px 0 rgba(255,255,255,0.06)"
            },
            fontFamily: {
                sans: ["Avenir Next", "Trebuchet MS", "sans-serif"]
            }
        }
    },
    plugins: []
};
