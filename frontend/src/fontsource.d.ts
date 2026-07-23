// A versão publicada de @fontsource/big-shoulders-display não tem a entrada
// `"./*.css"` no `exports` do package.json (outras famílias como Manrope
// já têm — inconsistência do pacote upstream). O import sem extensão usa a
// entrada `"./*"` que existe, e resolve certinho no bundler; só falta a
// declaração de tipo para o TypeScript não reclamar do import de efeito
// colateral.
declare module '@fontsource/big-shoulders-display/800'
declare module '@fontsource/big-shoulders-display/900'
