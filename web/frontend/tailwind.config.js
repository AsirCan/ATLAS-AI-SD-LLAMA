/** @type {import('tailwindcss').Config} */
export default {
    content: [
        "./index.html",
        "./src/**/*.{js,ts,jsx,tsx}",
    ],
    darkMode: 'class',
    theme: {
        extend: {
            colors: {
                dark: {
                    900: '#030014', // Deep Space Blue/Black
                    800: '#0f0c29', // Galactic Purple/Black
                    700: '#1a1b4b', // Deep Void
                },
                primary: '#7000ff', // Electric Violet
                accent: '#00d4ff',  // Cyan Neon
                secondary: '#ff0055', // Hot Pink Neon
            },
            animation: {
                'blob': 'blob 7s infinite',
                'float': 'float 6s ease-in-out infinite',
                'glow': 'glow 2s ease-in-out infinite alternate',
            },
            keyframes: {
                blob: {
                    '0%': { transform: 'translate(0px, 0px) scale(1)' },
                    '33%': { transform: 'translate(30px, -50px) scale(1.1)' },
                    '66%': { transform: 'translate(-20px, 20px) scale(0.9)' },
                    '100%': { transform: 'translate(0px, 0px) scale(1)' },
                },
                float: {
                    '0%, 100%': { transform: 'translateY(0)' },
                    '50%': { transform: 'translateY(-20px)' },
                },
                glow: {
                    'from': { boxShadow: '0 0 10px #7000ff, 0 0 20px #7000ff' },
                    'to': { boxShadow: '0 0 20px #00d4ff, 0 0 30px #00d4ff' },
                }
            }
        },
    },
    plugins: [],
}
