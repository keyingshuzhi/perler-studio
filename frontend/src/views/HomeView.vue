<script setup lang="ts">
const beads = [
  'violet', 'violet', 'mint', 'clear', 'clear', 'coral', 'coral', 'clear',
  'violet', 'mint', 'mint', 'clear', 'coral', 'coral', 'clear', 'clear',
  'clear', 'mint', 'ink', 'ink', 'ink', 'clear', 'clear', 'violet',
  'clear', 'clear', 'ink', 'sun', 'ink', 'mint', 'violet', 'violet',
  'coral', 'clear', 'ink', 'ink', 'ink', 'sun', 'sun', 'clear',
  'coral', 'coral', 'clear', 'mint', 'sun', 'sun', 'violet', 'clear',
]
</script>

<template>
  <main class="home">
    <section class="hero">
      <div class="hero__copy">
        <p class="eyebrow">Perler pattern workspace</p>
        <h1>让每一颗拼豆<br><em>都有准确的位置。</em></h1>
        <p class="intro">从图片到可制作图纸：智能匹配 291 色、逐格修正、统计材料，并输出适合打印与设计软件的矢量文件。</p>
        <div class="hero__actions">
          <RouterLink class="button" to="/convert">开始新图纸 <span>→</span></RouterLink>
          <RouterLink class="button button--quiet" to="/create">空白创作</RouterLink>
        </div>
        <nav class="hero__secondary" aria-label="探索工作台"><span>继续探索</span><RouterLink to="/projects">我的图纸</RouterLink><RouterLink to="/gallery">灵感社区</RouterLink><RouterLink to="/templates">模板库</RouterLink></nav>
        <div class="hero__proof"><span><b>291</b> 色参考色卡</span><span><b>SVG</b> 矢量交付</span><span><b>PDF</b> 格内标识</span><span><b>审核</b> 公开作品</span></div>
      </div>
      <div class="hero__visual" aria-hidden="true">
        <div class="preview-card">
          <div class="preview-card__top"><span>COLOR STUDY / 01</span><i /></div>
          <div class="bead-art"><span v-for="(bead, index) in beads" :key="index" :class="`bead bead--${bead}`" /></div>
          <div class="preview-card__bottom"><span>64 × 64</span><span>96 COLORS</span></div>
        </div>
        <div class="float-card float-card--palette"><i /><span>边缘保留</span><b>已启用</b></div>
        <div class="float-card float-card--count"><b>4,096</b><span>颗拼豆</span></div>
      </div>
    </section>

    <section class="workflow">
      <div class="section-heading"><p class="eyebrow">A clear workflow</p><h2>从灵感到制作，只保留必要步骤。</h2></div>
      <div class="steps">
        <article><span class="step-number">01</span><div class="step-icon step-icon--upload">↑</div><h3>导入与优化</h3><p>上传图片，选择成品尺寸；边缘保留算法让轮廓更干净。</p></article>
        <article><span class="step-number">02</span><div class="step-icon step-icon--edit">✦</div><h3>逐格精修</h3><p>画笔、填充和吸管工具都在同一个专注编辑器中完成。</p></article>
        <article><span class="step-number">03</span><div class="step-icon step-icon--export">↗</div><h3>放心交付</h3><p>导出带标识的 PDF、PNG、SVG 与材料清单，直接开始制作。</p></article>
      </div>
    </section>
  </main>
</template>

<style scoped>
.home { max-width: 1240px; margin: 0 auto; padding: clamp(46px, 7vw, 92px) clamp(18px, 4vw, 48px) 64px; }
.hero { display: grid; grid-template-columns: minmax(0, 1.05fr) minmax(360px, .75fr); gap: clamp(44px, 8vw, 112px); align-items: center; min-height: 520px; }.hero__copy { max-width: 680px; }.hero h1 { max-width: 700px; margin: 15px 0 0; color: var(--ink); font-family: Fraunces, Georgia, serif; font-size: clamp(44px, 5.6vw, 75px); font-weight: 700; letter-spacing: -3.7px; line-height: .99; }.hero h1 em { color: var(--violet); font-style: normal; }.intro { max-width: 610px; margin: 27px 0 0; color: var(--ink-soft); font-size: 16px; line-height: 1.8; }.hero__actions { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 29px; }.hero__actions .button span { margin-left: 8px; font-size: 18px; line-height: 0; }.hero__secondary { display: flex; flex-wrap: wrap; align-items: center; gap: 5px 13px; margin-top: 15px; color: #6b7590; font-size: 11px; font-weight: 700; }.hero__secondary span { color: #9aa3b5; font-family: "DM Mono", monospace; font-size: 9px; letter-spacing: .06em; text-transform: uppercase; }.hero__secondary a { color: #5b4ab8; text-decoration: underline; text-decoration-color: #d4cdfb; text-underline-offset: 3px; }.hero__secondary a:hover { color: #34248f; text-decoration-color: currentColor; }.hero__proof { display: flex; flex-wrap: wrap; gap: 13px 18px; margin-top: 31px; color: #687386; font-size: 11px; font-weight: 700; }.hero__proof span { display: inline-flex; align-items: center; gap: 5px; }.hero__proof b { color: #4852ad; font-family: "DM Mono", monospace; font-size: 12px; }
.hero__visual { position: relative; min-height: 410px; }.preview-card { position: absolute; inset: 18px 20px 18px 0; display: grid; grid-template-rows: auto 1fr auto; gap: 22px; padding: 23px; border: 1px solid #313e63; border-radius: 27px; background: linear-gradient(145deg, #1d2947, #121a2e); box-shadow: 0 28px 55px rgb(21 30 55 / 26%); transform: rotate(2.5deg); }.preview-card::after { position: absolute; inset: 1px; border-radius: 26px; background: linear-gradient(145deg, rgb(255 255 255 / 11%), transparent 23%); content: ''; pointer-events: none; }.preview-card__top, .preview-card__bottom { display: flex; justify-content: space-between; color: #bdc6dc; font-family: "DM Mono", monospace; font-size: 10px; letter-spacing: .04em; }.preview-card__top i { width: 9px; height: 9px; border-radius: 50%; background: #63d9bd; box-shadow: 0 0 0 5px rgb(99 217 189 / 12%); }.bead-art { position: relative; z-index: 1; display: grid; grid-template-columns: repeat(8, 1fr); gap: 9px; align-self: center; max-width: 292px; margin: 0 auto; }.bead { aspect-ratio: 1; border-radius: 37%; box-shadow: inset -3px -4px 5px rgb(0 0 0 / 16%), inset 3px 3px 5px rgb(255 255 255 / 28%), 0 4px 9px rgb(0 0 0 / 22%); }.bead--clear { opacity: .12; background: #dfe7f7; }.bead--violet { background: #8e7cff; }.bead--mint { background: #50cfb2; }.bead--coral { background: #ff8a75; }.bead--ink { background: #34466c; }.bead--sun { background: #f9ce63; }.float-card { position: absolute; z-index: 2; display: grid; gap: 2px; padding: 11px 13px; border: 1px solid rgb(255 255 255 / 70%); border-radius: 13px; background: rgb(255 255 255 / 91%); box-shadow: 0 13px 28px rgb(30 41 68 / 15%); backdrop-filter: blur(10px); color: #4b586d; font-size: 10px; font-weight: 800; }.float-card--palette { right: -4px; bottom: 40px; grid-template-columns: auto 1fr; column-gap: 7px; }.float-card--palette i { grid-row: span 2; width: 21px; height: 21px; border-radius: 7px; background: linear-gradient(135deg, #826ff6, #4ed2b2); }.float-card--palette b { color: #2b927d; font-size: 9px; }.float-card--count { top: 0; right: 32px; }.float-card--count b { color: #4b3ac5; font-family: Fraunces, Georgia, serif; font-size: 20px; line-height: 1; }.float-card--count span { color: #7f8999; }
.workflow { margin-top: 80px; padding-top: 47px; border-top: 1px solid var(--line); }.section-heading { display: grid; grid-template-columns: 1fr 2fr; gap: 25px; align-items: start; }.section-heading h2 { max-width: 620px; margin: 0; font-family: Fraunces, Georgia, serif; font-size: clamp(27px, 3.2vw, 42px); letter-spacing: -1.6px; line-height: 1.15; }.steps { display: grid; grid-template-columns: repeat(3, 1fr); gap: 15px; margin-top: 34px; }.steps article { position: relative; min-height: 220px; padding: 22px; overflow: hidden; border: 1px solid var(--line); border-radius: 18px; background: rgb(255 255 255 / 70%); transition: transform .2s ease, box-shadow .2s ease, border-color .2s ease; }.steps article:hover { border-color: #c9c2f5; box-shadow: var(--shadow-md); transform: translateY(-4px); }.step-number { position: absolute; top: 16px; right: 18px; color: #c2c8d3; font-family: "DM Mono", monospace; font-size: 11px; }.step-icon { display: grid; width: 39px; height: 39px; place-items: center; border-radius: 12px; color: #fff; font-size: 19px; font-weight: 700; }.step-icon--upload { background: #6854e8; }.step-icon--edit { background: #ec7664; }.step-icon--export { background: #31ae92; }.steps h3 { margin: 28px 0 7px; font-size: 16px; }.steps p { margin: 0; color: var(--ink-soft); font-size: 13px; line-height: 1.65; }
@media (max-width: 820px) { .hero { grid-template-columns: 1fr; }.hero__visual { max-width: 460px; width: min(100%, 460px); margin: 10px auto 0; }.section-heading { grid-template-columns: 1fr; }.steps { grid-template-columns: 1fr; }.steps article { min-height: auto; } } @media (max-width: 480px) { .home { padding-top: 45px; }.hero h1 { letter-spacing: -2.5px; }.hero__visual { min-height: 340px; }.preview-card { inset: 18px 8px 18px 0; }.bead-art { gap: 6px; max-width: 230px; }.float-card--count { right: 8px; }.float-card--palette { right: -7px; bottom: 28px; }.hero__proof { gap: 8px 12px; } }
</style>
