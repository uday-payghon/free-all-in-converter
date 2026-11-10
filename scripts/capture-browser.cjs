// Optional local visual review and lightweight performance evidence.
const {chromium}=require('@playwright/test');
const fs=require('node:fs');
(async()=>{
  const browser=await chromium.launch();const page=await browser.newPage({viewport:{width:1280,height:900}});
  await page.goto(process.env.BASE_URL||'http://127.0.0.1:10000');
  await page.screenshot({path:'docs/home-desktop.png',fullPage:true});
  const metrics=await page.evaluate(()=>({
    navigation:performance.getEntriesByType('navigation').map(n=>({domContentLoadedMs:n.domContentLoadedEventEnd,transferBytes:n.transferSize})),
    resources:performance.getEntriesByType('resource').map(r=>({url:r.name,transferBytes:r.transferSize})),
    horizontalOverflow:document.documentElement.scrollWidth>innerWidth
  }));
  fs.writeFileSync('docs/browser-metrics.json',JSON.stringify(metrics,null,2));
  await page.setViewportSize({width:390,height:844});await page.screenshot({path:'docs/home-mobile.png',fullPage:true});
  await page.setViewportSize({width:1280,height:900});await page.locator('#tools [data-mode="image"]').click();
  const data=await page.evaluate(()=>{const c=document.createElement('canvas');c.width=800;c.height=600;const x=c.getContext('2d');x.fillStyle='#dc2228';x.fillRect(0,0,400,600);x.fillStyle='#151515';x.fillRect(400,0,400,600);return c.toDataURL().split(',')[1]});
  await page.locator('#file').setInputFiles({name:'example.png',mimeType:'image/png',buffer:Buffer.from(data,'base64')});
  await page.locator('#open-crop').waitFor();await page.locator('#width').fill('320');await page.locator('#target').fill('40');
  await page.locator('#submit').click();await page.locator('#download').waitFor();
  await page.locator('#workspace').screenshot({path:'docs/image-workspace.png'});
  await page.locator('#open-crop').click();await page.locator('#crop-modal').screenshot({path:'docs/crop-editor.png'});
  console.log(JSON.stringify(metrics));await browser.close();
})().catch(e=>{console.error(e);process.exit(1)});
