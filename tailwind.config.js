// Gera static/tailwind.css (as telas não dependem de internet). Depois de usar uma classe nova, rode:
//   npx tailwindcss@3.4.17 -i tailwind.input.css -o static/tailwind.css --minify
module.exports = { content: ['templates/**/*.html', 'routes/**/*.py', 'services/**/*.py'] };
