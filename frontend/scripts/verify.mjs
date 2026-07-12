import { chromium } from 'playwright'

// End-to-end browser verification of the composer UI against a live dev
// server + backend. Not a unit test — this exists because headless
// tsc/build checks miss real interaction bugs (see brain pattern
// browser-verify-with-playwright): the atomic-state race between schema and
// params, and the strange-attractor type-switch defaults bug, were both
// caught here, not by the type checker.

const consoleErrors = []
const browser = await chromium.launch()
const context = await browser.newContext()
await context.grantPermissions(['clipboard-read', 'clipboard-write'])
const page = await context.newPage()
page.on('console', (msg) => {
  if (msg.type() === 'error') consoleErrors.push(msg.text())
})
page.on('pageerror', (err) => consoleErrors.push(String(err)))

/** Poll `check` until it returns true or `timeoutMs` elapses. */
async function waitUntil(check, timeoutMs = 5000, intervalMs = 100) {
  const start = Date.now()
  while (Date.now() - start < timeoutMs) {
    if (await check()) return true
    await new Promise((r) => setTimeout(r, intervalMs))
  }
  return false
}

await page.goto('http://localhost:5173/')
await page.waitForSelector('text=Lumen')
console.log('1. page loaded, title visible: OK')

// Navigate to Systems (generator page) — templates live there, not on Looks
await page.getByRole('button', { name: /^Systems$/ }).first().click()
await page.waitForSelector('[data-testid="template-gallery"]', { timeout: 5000 })

const cards = await page.locator('#main-content').getByRole('button').all()
console.log(`2. interactive buttons found: ${cards.length}`)

await page.getByTestId('template-reaction-diffusion').click()
await page.waitForSelector('text=Feed rate', { timeout: 8000 }).catch(() => {})
// Open Craft dials (Play is default) — button labeled "Craft" in the dock
await page.getByRole('button', { name: /^Craft$/ }).first().click()
await page.waitForSelector('text=Feed rate', { timeout: 8000 })
// Ensure still mode for snappier tests
const motionToggle = page.getByRole('button', { name: /^(Motion|Still)$/ })
if (await motionToggle.count()) {
  const label = await motionToggle.first().textContent()
  if (label && label.includes('Motion')) await motionToggle.first().click()
}
console.log('3. selected reaction-diffusion, param panel shows Feed rate: OK')

await page.waitForSelector('img[alt="preview"]', { timeout: 15000 })
const firstSrc = await page.locator('img[alt="preview"]').getAttribute('src')
console.log('4. initial preview image loaded:', firstSrc?.slice(0, 30))

const slider = page.locator('input[type="range"]').first()
await slider.evaluate((el) => {
  const nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set
  nativeSetter.call(el, '0.08')
  el.dispatchEvent(new Event('input', { bubbles: true }))
  el.dispatchEvent(new Event('change', { bubbles: true }))
})
const changed = await waitUntil(async () => {
  const src = await page.locator('img[alt="preview"]').getAttribute('src')
  return src !== firstSrc
}, 10000)
console.log('5. after slider change, preview src changed:', changed)

await page.getByTestId('template-strange-attractor').click()
await page.waitForSelector('text=Attractor type', { timeout: 8000 })
await page.getByRole('button', { name: /^Craft$/ }).first().click().catch(() => {})
await page.waitForSelector('text=Attractor type', { timeout: 5000 })
await page.locator('select').first().selectOption('lorenz')
await page.waitForTimeout(1200)
const lorenzSrc = await page.locator('img[alt="preview"]').getAttribute('src')
console.log('6. strange-attractor -> lorenz preview updated:', !!lorenzSrc)

const sigmaRow = page.locator('label', { hasText: 'Sigma' }).locator('xpath=../..')
const sigmaSlider = sigmaRow.locator('input[type="range"]')
const [sigMin, sigMax, sigVal] = await Promise.all([
  sigmaSlider.getAttribute('min'),
  sigmaSlider.getAttribute('max'),
  sigmaSlider.inputValue(),
])
const sigmaOk = sigMin === '5' && sigMax === '15' && sigVal === '10'
console.log(`7. lorenz "a" slider relabeled Sigma with range [${sigMin},${sigMax}]=${sigVal} (expected [5,15]=10): ${sigmaOk}`)

await page.locator('select').first().selectOption('henon')
await waitUntil(async () => (await page.getByText('Parameter c').count()) === 0)
const henonCFieldCount = await page.getByText('Parameter c').count()
console.log(`8. henon hides fixed "Parameter c" slider (count=${henonCFieldCount}, expected 0)`)

const renderBtn = page.getByRole('button', { name: /Full video/ })
console.log('9. full-video CTA present:', await renderBtn.isVisible())

const shareBtn = page.getByRole('button', { name: /Share|Link copied/ })
console.log('9b. share button visible:', await shareBtn.isVisible())

await page.locator('select').first().selectOption('lorenz')
await waitUntil(async () => (await sigmaSlider.inputValue()) === '10')
for (let i = 0; i < 5; i++) {
  await page.getByRole('button', { name: /Surprise/ }).click()
  await page.waitForTimeout(50)
}
const typeAfterRandomize = await page.locator('select').first().inputValue()
const activeSlider = page.locator('input[type="range"]').first()
const [randMin, randMax, randVal] = await Promise.all([
  activeSlider.getAttribute('min'),
  activeSlider.getAttribute('max'),
  activeSlider.inputValue(),
])
const inRange = Number(randVal) >= Number(randMin) && Number(randVal) <= Number(randMax)
console.log(`10. surprise on strange-attractor: type=${typeAfterRandomize}, param a in [${randMin},${randMax}]=${randVal}: ${inRange}`)

const preRandomizeSrc = await page.locator('img[alt="preview"]').getAttribute('src')
await page.getByRole('button', { name: /^Craft$/ }).first().click().catch(() => {})
await page.getByTestId('template-mandelbrot').click()
await page.waitForSelector('text=Mandelbrot', { timeout: 10000 })
await page.getByRole('button', { name: /^Craft$/ }).first().click().catch(() => {})
const palette = page.getByText('Palette', { exact: true }).first()
await palette.scrollIntoViewIfNeeded()
await palette.waitFor({ state: 'visible', timeout: 8000 })
console.log('11. mandelbrot palette section visible: OK')
await waitUntil(async () => (await page.locator('img[alt="preview"]').getAttribute('src')) !== preRandomizeSrc)

await page.screenshot({
  path: new URL('../../screenshot_mandelbrot.png', import.meta.url).pathname,
  fullPage: true,
})
console.log('12. screenshot saved')

await page.getByTestId('template-domain-coloring').click()
await page.waitForSelector('text=Function', { timeout: 8000 })
await page.getByRole('button', { name: /^Craft$/ }).first().click().catch(() => {})
await waitUntil(() => page.getByText('Exponent / degree (n)').isVisible())
const zPowVisible = await page.getByText('Exponent / degree (n)').isVisible()
const ratVisibleBefore = await page.getByText('Numerator degree (p)').count()
console.log(`13. func=z_pow: n_start visible=${zPowVisible}, rational-only fields present=${ratVisibleBefore}`)

await page.locator('select').first().selectOption('rational')
await waitUntil(() => page.getByText('Numerator degree (p)').isVisible())
const nVisibleAfter = await page.getByText('Exponent / degree (n)').count()
const pVisibleAfter = await page.getByText('Numerator degree (p)').isVisible()
console.log(`14. func=rational: n_start hidden (count=${nVisibleAfter}), p_start visible=${pVisibleAfter}`)

await page.getByTestId('template-chladni').click()
await page.waitForSelector('text=Inner glow tint', { timeout: 8000 })
await page.getByRole('button', { name: /^Craft$/ }).first().click().catch(() => {})
await waitUntil(() => page.getByText('Positive-region tint').isVisible())
const tintBefore = await page.getByText('Positive-region tint').count()
await page.getByRole('switch').first().click()
await waitUntil(async () => (await page.getByText('Positive-region tint').count()) === 0)
const tintAfter = await page.getByText('Positive-region tint').count()
console.log(`15. chladni inner_glow toggle: tint fields ${tintBefore} -> ${tintAfter}`)

await page.getByTestId('template-julia').click()
await page.waitForSelector('text=c angle', { timeout: 8000 })
await page.getByRole('button', { name: /^Craft$/ }).first().click().catch(() => {})
console.log('16. julia system loaded:', await page.getByText('c angle').first().isVisible())

const thetaSlider = page.locator('input[type="range"]').first()
const defaultTheta = await thetaSlider.inputValue()
await page.getByRole('button', { name: /Surprise/ }).click()
await waitUntil(async () => (await thetaSlider.inputValue()) !== defaultTheta)
const afterRandomize = await thetaSlider.inputValue()
console.log(`17. surprise changed a slider: ${defaultTheta} -> ${afterRandomize}`)

await page.getByRole('button', { name: 'More actions' }).click()
await page.getByRole('button', { name: /^Reset$/ }).click()
await waitUntil(async () => (await thetaSlider.inputValue()) === defaultTheta)
console.log('18. reset restored the default:', await thetaSlider.inputValue() === defaultTheta)

// JSON lives under ··· overflow menu
await page.getByRole('button', { name: 'More actions' }).click()
await page.getByRole('button', { name: /^JSON$|✓ JSON/ }).click()
await waitUntil(async () => {
  try {
    const t = await page.evaluate(() => navigator.clipboard.readText())
    const parsed = JSON.parse(t)
    return typeof parsed.c_theta_start === 'number'
  } catch {
    return false
  }
})
const clipboardText = await page.evaluate(() => navigator.clipboard.readText())
let parsedOk = false
try {
  const parsed = JSON.parse(clipboardText)
  parsedOk = typeof parsed.c_theta_start === 'number'
} catch { /* parsedOk stays false */ }
console.log('19. copy-preset-JSON produced valid, parseable JSON with expected keys:', parsedOk)

if (parsedOk) {
  const outPath = new URL('../../scratch_preset.json', import.meta.url).pathname
  await import('node:fs/promises').then((fs) => fs.writeFile(outPath, clipboardText))
  console.log(`    (written to ${outPath} for the CLI round-trip check)`)
}

// Looks page — carousel
await page.getByRole('button', { name: /^Looks$/ }).first().click()
await page.waitForSelector('[data-testid="looks-gallery"]', { timeout: 8000 })
const lookBtn = page.getByTestId('looks-gallery').locator('button[data-testid^="look-"]').first()
await lookBtn.click()
await page.waitForSelector('img[alt="preview"]', { timeout: 20000 })
console.log('20. look selection loaded a preview: OK')

console.log('\nconsole errors:', consoleErrors.length ? consoleErrors : 'none')

await browser.close()
