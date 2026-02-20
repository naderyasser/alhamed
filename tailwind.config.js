/** @type {import('tailwindcss').Config} */
module.exports = {
    content: [
        "./templates/**/*.html",
        "./static/**/*.js",
    ],
    theme: {
        extend: {
            colors: {
                'sage': {
                    50: '#f8faf8',
                    100: '#e8f0e9',
                    200: '#c8deca',
                    300: '#a0c5a3',
                    400: '#72a876',
                    500: '#4e8c53',
                    600: '#3a7040',
                    700: '#2e5933',
                    800: '#244428',
                    900: '#1a321e',
                },
                'dark': {
                    50: '#1a1a1a',
                    100: '#161616',
                    200: '#111111',
                    300: '#0a0a0a',
                    400: '#080808',
                    500: '#050505',
                },
                'accent': {
                    400: '#e53935',
                    500: '#d32f2f',
                    600: '#b71c1c',
                }
            }
        }
    },
    plugins: [],
}
