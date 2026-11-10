const {test,expect} = require('@playwright/test');
const AxeBuilder = require('@axe-core/playwright').default;
const fs=require('node:fs');
const browserErrors=new WeakMap();
test.beforeEach(async({page})=>{browserErrors.set(page,[]);page.on('pageerror',e=>browserErrors.get(page).push(e.message))});
test.afterEach(async({page})=>{expect(browserErrors.get(page)).toEqual([])});
const image={name:'sample.png',mimeType:'image/png'};
// Generate the actual test image in the browser to avoid fixture codec assumptions.
async function chooseImage(page){
  const data=await page.evaluate(()=>{const c=document.createElement('canvas');c.width=400;c.height=300;const x=c.getContext('2d');x.fillStyle='white';x.fillRect(0,0,400,300);x.fillStyle='#dc2228';x.fillRect(0,0,200,300);return c.toDataURL().split(',')[1]});
  await page.locator('#file').setInputFiles({...image,buffer:Buffer.from(data,'base64')});
  await expect(page.locator('#open-crop')).toBeVisible();
}
async function images(page){await page.locator('#tools [data-mode="image"]').click();await chooseImage(page)}
async function audit(page){const r=await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21aa']).analyze();expect(r.violations.map(v=>({id:v.id,nodes:v.nodes.map(n=>n.target)}))).toEqual([])}

test('responsive layout, all categories and accessible picker',async({page})=>{
  await page.goto('/');
  for(const width of [320,390,768,1024,1440]){
    await page.setViewportSize({width,height:900});
    expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
  }
  await audit(page);
  await page.getByRole('button',{name:'Start converting'}).click();
  await expect(page.getByRole('button',{name:'Close selector'})).toBeFocused();
  await page.keyboard.press('Shift+Tab');
  await expect(page.locator('#category-modal [data-mode="document"]')).toBeFocused();
  await page.keyboard.press('Tab');
  await expect(page.getByRole('button',{name:'Close selector'})).toBeFocused();
  await audit(page);
  await page.keyboard.press('Escape');
  await expect(page.getByRole('button',{name:'Start converting'})).toBeFocused();
  for(const mode of ['image','video','audio','pdf','document']){
    await page.locator(`#tools [data-mode="${mode}"]`).click();
    await expect(page.locator('#workspace')).toBeVisible();
    await expect(page.locator('#workspace-title')).toBeFocused();
    await audit(page);
    for(const width of [320,390,768,1024]){await page.setViewportSize({width,height:900});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy()}
  }
});

test('keyboard crop, ratio, conversion, download and reset',async({page},testInfo)=>{
  await page.goto('/');await images(page);
  await page.locator('#open-crop').click();await audit(page);
  await page.locator('#crop-x').fill('0');await page.locator('#crop-y').fill('0');
  await page.locator('#crop-w').fill('190');await page.locator('#crop-h').fill('200');
  await page.locator('#apply-crop').click();
  await expect(page.locator('#crop-summary')).toHaveText('Crop: 190 × 200 px');
  await page.locator('#width').fill('95');await expect(page.locator('#height')).toHaveValue('100');
  await page.locator('#format').selectOption('png');await page.locator('#target').fill('10');
  await page.locator('#submit').click();await expect(page.locator('#result-panel')).toBeVisible();
  await expect(page.locator('#result-details')).toContainText('95 × 100');
  const downloadEvent=page.waitForEvent('download');await page.locator('#download').click();const download=await downloadEvent;
  expect(download.suggestedFilename()).toBe('sample_converted.png');
  const path=testInfo.outputPath('converted.png');await download.saveAs(path);
  expect(fs.statSync(path).size).toBeLessThanOrEqual(10*1024);
  const pixels=await page.evaluate(async()=>{const img=new Image();img.src=document.querySelector('#download').href;await img.decode();const c=document.createElement('canvas');c.width=img.width;c.height=img.height;const x=c.getContext('2d');x.drawImage(img,0,0);return [...x.getImageData(20,20,1,1).data]});
  expect(pixels[0]).toBeGreaterThan(180);expect(pixels[1]).toBeLessThan(80);
  await page.locator('#open-crop').click();await page.locator('#reset-crop').click();await page.locator('#apply-crop').click();
  await expect(page.locator('#crop-summary')).toHaveText('No custom crop');await expect(page.locator('#result-panel')).toBeHidden();
  await page.screenshot({path:testInfo.outputPath('image-workspace.png'),fullPage:true});
});

test('pointer crop and actionable invalid-file error',async({page})=>{
  await page.goto('/');await images(page);await page.locator('#open-crop').click();
  const box=await page.locator('#crop-image').boundingBox();
  await page.mouse.move(box.x+box.width*.1,box.y+box.height*.1);await page.mouse.down();
  await page.mouse.move(box.x+box.width*.6,box.y+box.height*.6,{steps:5});await page.mouse.up();
  await page.locator('#apply-crop').click();await expect(page.locator('#crop-summary')).toHaveText(/Crop: \d+ × \d+ px/);const cropText=await page.locator('#crop-summary').textContent();const cropSize=cropText.match(/(\d+) × (\d+)/);expect(cropSize).toBeTruthy();expect(Math.abs(Number(cropSize[1])-200)).toBeLessThanOrEqual(1);expect(Math.abs(Number(cropSize[2])-150)).toBeLessThanOrEqual(1);
  await page.locator('#file').setInputFiles({name:'broken.png',mimeType:'image/png',buffer:Buffer.from('broken')});
  await page.locator('#submit').click();await expect(page.locator('#status')).toContainText('Invalid or unsupported image');
  await expect(page.locator('#submit')).toBeEnabled();await expect(page.locator('#result-panel')).toBeHidden();
});

test('pending job locks settings and impossible size reports an error',async({page})=>{
  await page.goto('/');await images(page);
  await page.locator('#lock-ratio').uncheck();await page.locator('#width').fill('1000');await page.locator('#height').fill('1000');
  await page.locator('#resize-mode').selectOption('stretch');await page.locator('#format').selectOption('bmp');await page.locator('#target').fill('1');
  await page.route('**/api/convert',async route=>{await new Promise(r=>setTimeout(r,300));await route.continue()});
  await page.locator('#submit').click();await expect(page.locator('#format')).toBeDisabled();await expect(page.locator('[data-open-picker]').first()).toBeDisabled();
  await expect(page.locator('#status')).toContainText('Cannot achieve');await expect(page.locator('#format')).toBeEnabled();
});

for(const [mode,filename,format,magic] of [['video','clip.mp4','webm','1a45dfa3'],['audio','clip.mp4','mp3','494433'],['pdf','paper.pdf','docx','504b0304'],['document','paper.docx','pdf','25504446']]){
  test(`${mode} real conversion and download`,async({page})=>{
    await page.goto('/');await page.locator(`#tools [data-mode="${mode}"]`).click();
    await page.locator('#file').setInputFiles(`artifacts/fixtures/${filename}`);await page.locator('#format').selectOption(format);
    await page.locator('#submit').click();await expect(page.locator('#download')).toBeVisible({timeout:30000});
    const event=page.waitForEvent('download');await page.locator('#download').click();const download=await event;
    expect(download.suggestedFilename()).toBe(filename.replace(/\.[^.]+$/,'')+'_converted.'+format);
    const content=fs.readFileSync(await download.path());expect(content.subarray(0,magic.length/2).toString('hex')).toBe(magic);
    await audit(page);
  });
}

test('scanned PDF has explicit OCR message',async({page})=>{
  await page.goto('/');await page.locator('#tools [data-mode="pdf"]').click();
  await page.locator('#file').setInputFiles('artifacts/fixtures/scan.pdf');await page.locator('#submit').click();
  await expect(page.locator('#status')).toContainText('OCR');await expect(page.locator('#result-panel')).toBeHidden();
});

test('mobile touch crop',async({browser,browserName})=>{
  test.skip(browserName!=='chromium','CDP touch drag is Chromium-specific; pointer crop runs in all engines.');
  const context=await browser.newContext({viewport:{width:390,height:844},hasTouch:true,isMobile:true,reducedMotion:'reduce'});
  const page=await context.newPage();await page.goto(process.env.BASE_URL||'http://127.0.0.1:10000');await images(page);await page.locator('#open-crop').click();
  await page.locator('#crop-image').evaluate(async img=>{await img.decode();await new Promise(requestAnimationFrame)});
  const box=await page.locator('#crop-image').boundingBox();const session=await context.newCDPSession(page);
  await session.send('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[{x:box.x+box.width*.1,y:box.y+box.height*.1}]});
  for(let i=1;i<=5;i++){
    await session.send('Input.dispatchTouchEvent',{type:'touchMove',touchPoints:[{x:box.x+box.width*(.1+i*.1),y:box.y+box.height*(.1+i*.1)}]});
    await page.evaluate(()=>new Promise(requestAnimationFrame));
  }
  await session.send('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]});
  await expect(page.locator('#crop-coordinates')).toContainText('Crop area:');
  // CDP owns the touch gesture; use keyboard activation for Apply rather than
  // mixing CDP touch IDs with Playwright's separate touchscreen controller.
  await page.locator('#apply-crop').focus();
  await page.keyboard.press('Enter');await expect(page.locator('#crop-summary')).toHaveText(/Crop: \d+ × \d+ px/);const cropText=await page.locator('#crop-summary').textContent();const cropSize=cropText.match(/(\d+) × (\d+)/);expect(cropSize).toBeTruthy();expect(Math.abs(Number(cropSize[1])-200)).toBeLessThanOrEqual(1);expect(Math.abs(Number(cropSize[2])-150)).toBeLessThanOrEqual(1);await context.close();
});

test('reference-inspired hero keeps its information and theme on mobile',async({page})=>{
  await page.goto('/');
  await expect(page.locator('.hero-kicker')).toContainText('Fast, simple online file converter');
  await expect(page.locator('.hero h1')).toContainText('Convert Your Files');
  await expect(page.locator('.hero-stat-card')).toHaveCount(3);
  await expect(page.locator('.hero-stats')).toContainText('5');
  await expect(page.locator('.hero-stats')).toContainText('10+');
  await expect(page.locator('.hero-stats')).toContainText('0');
  await audit(page);
  await page.setViewportSize({width:390,height:844});
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
  await page.locator('#theme-toggle').click();
  await expect(page.locator('html')).toHaveAttribute('data-theme','dark');
  await audit(page);
  await page.reload();
  await expect(page.locator('html')).toHaveAttribute('data-theme','dark');
  await expect(page.locator('.hero-stat-card')).toHaveCount(3);
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
});

test('developer profile stays visible and hero preview does not clip at right edge',async({page})=>{
  await page.goto('/');
  await expect(page.locator('.developer-credit')).toContainText('Developed by:');
  await expect(page.locator('.developer-credit')).toContainText('Uday Payghon');
  const contact=page.locator('.developer-profile .developer-contact');
  await expect(contact).toBeVisible();
  await expect(contact).toHaveAttribute('href', 'https://www.linkedin.com/in/cyber-uday/');
  for(const width of [320,390,600,768,1024,1280,1440]){
    await page.setViewportSize({width,height:900});
    const positions=await page.evaluate(()=>{
      const viewport=window.innerWidth;
      const hero=document.querySelector('.hero-right').getBoundingClientRect();
      const preview=document.querySelector('.preview-window').getBoundingClientRect();
      const developer=document.querySelector('.developer-profile').getBoundingClientRect();
      const contact=document.querySelector('.developer-contact').getBoundingClientRect();
      return {viewport,documentWidth:document.documentElement.scrollWidth,
        heroLeft:hero.left,heroRight:hero.right,
        previewLeft:preview.left,previewRight:preview.right,
        developerLeft:developer.left,developerRight:developer.right,contactRight:contact.right};
    });
    expect(positions.documentWidth).toBeLessThanOrEqual(width);
    expect(positions.heroLeft).toBeGreaterThanOrEqual(-1);
    expect(positions.heroRight).toBeLessThanOrEqual(width+1);
    expect(positions.previewLeft).toBeGreaterThanOrEqual(positions.heroLeft-1);
    expect(positions.previewRight).toBeLessThanOrEqual(positions.heroRight+1);
    expect(positions.developerLeft).toBeGreaterThanOrEqual(-1);
    expect(positions.contactRight).toBeLessThanOrEqual(width+1);
  }
  await page.locator('#theme-toggle').click();
  await expect(page.locator('html')).toHaveAttribute('data-theme','dark');
  await expect(contact).toBeVisible();
  await audit(page);
});
