// Gera finana/static/tailwind.css (as telas não dependem de internet). Depois de usar uma classe nova, rode:
//   npm run css
// Cores e tamanhos do app ficam aqui: nos templates use as classes (bg-cartao, border-borda, text-2xs...),
// nunca hex solto como bg-[#18181f].
module.exports = {
  content: ['finana/templates/**/*.html', 'finana/routes/**/*.py', 'finana/services/**/*.py'],
  theme: {
    extend: {
      colors: {
        fundo: '#0f0f13', // fundo da página
        painel: '#141419', // menu lateral e campos
        cartao: '#18181f', // cartões
        borda: '#23232d', // bordas e divisórias
        realce: '#1f1f28', // item do menu com o mouse em cima
      },
      backgroundImage: {
        marca: 'linear-gradient(135deg, #ec4899 0%, #dc2626 100%)', // rosa -> vermelho dos botões
      },
      fontSize: {
        '2xs': ['0.6875rem', '1rem'], // 11px: selos e notas pequenas
      },
    },
  },
};
