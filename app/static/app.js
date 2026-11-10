'use strict';
const $ = id => document.getElementById(id);
const themeToggle=$('theme-toggle');
function setTheme(next,save=true){
  const theme=next==='dark'?'dark':'light';
  document.documentElement.dataset.theme=theme;
  if(themeToggle) {
    themeToggle.setAttribute('aria-label',theme==='dark'?'Switch to light mode':'Switch to dark mode');
    themeToggle.setAttribute('title',theme==='dark'?'Switch to light mode':'Switch to dark mode');
    themeToggle.setAttribute('aria-pressed',String(theme==='dark'));
    const themeLabel=themeToggle.querySelector('.theme-label');
    if(themeLabel)themeLabel.textContent=theme==='dark'?'Light mode':'Dark mode';
  }
  const meta=$('theme-meta');if(meta)meta.setAttribute('content',theme==='dark'?'#121212':'#ffffff');
  if(save){try{localStorage.setItem('converter-theme',theme)}catch(e){}}
}
setTheme(document.documentElement.dataset.theme||'light',false);
themeToggle?.addEventListener('click',()=>setTheme(document.documentElement.dataset.theme==='dark'?'light':'dark'));
const themeMedia=matchMedia('(prefers-color-scheme: dark)');
themeMedia.addEventListener?.('change',event=>{
  try{if(localStorage.getItem('converter-theme'))return}catch(e){}
  setTheme(event.matches?'dark':'light',false);
});

const formats = {
  image:{title:'Image converter',subtitle:'Crop, resize and convert your images with control over file size.',accept:'.jpg,.jpeg,.png,.webp,.bmp,.tif,.tiff,.gif',hint:'JPG, PNG, WEBP, GIF, BMP, TIFF · Maximum 80 MB',outputs:['jpg','png','webp','bmp','tiff'],note:'Set the maximum size in KB or MB. Exact dimensions are preserved for Crop, Pad and Stretch; Fit stays within your bounds.'},
  video:{title:'Video converter',subtitle:'Convert video formats and reduce download size.',accept:'.mp4,.webm,.mov,.mkv,.avi',hint:'MP4, WEBM, MOV, MKV, AVI · Maximum 80 MB',outputs:['mp4','webm'],note:'Very low size targets can fail for long videos. Processing may take longer than image conversion.'},
  audio:{title:'Audio / MP3 converter',subtitle:'Convert your audio files or extract MP3 from an uploaded video.',accept:'.mp3,.wav,.ogg,.m4a,.flac,.aac,.wma,.mp4,.webm,.mov,.mkv,.avi',hint:'Audio or personal video files · Maximum 80 MB',outputs:['mp3','m4a','ogg','wav'],note:'For target file sizes, use MP3, M4A or OGG. WAV is uncompressed. External song downloads are not supported.'},
  pdf:{title:'PDF tools',subtitle:'Compress a PDF or extract editable text into a Word document.',accept:'.pdf',hint:'PDF documents · Maximum 80 MB',outputs:['pdf','docx'],note:'PDF → DOCX extracts selectable text, not complex formatting or scans. PDF → PDF uses best-effort compression.'},
  document:{title:'Document converter',subtitle:'Turn Word, Excel, PowerPoint and common document formats into PDF.',accept:'.doc,.docx,.ppt,.pptx,.xls,.xlsx,.odt,.odp,.ods,.rtf,.txt',hint:'DOC/DOCX, PPT/PPTX, XLS/XLSX, ODF, RTF, TXT · Maximum 80 MB',outputs:['pdf'],note:'Documents are processed by LibreOffice. Fonts and advanced layouts may differ from the original.'}
};
let mode=null, previewUrl=null, downloadUrl=null, sourceInfo=null, cropSelection=null, lastFocus=null;
let drawnCrop=null, pointerStart=null, busy=false, uploadLimit=80*1024*1024, maxImagePixels=16000000;
const dismissSuccess=()=>{$('success-toast').hidden=true};
$('dismiss-success').addEventListener('click',dismissSuccess);
const capabilitiesReady=fetch('/api/capabilities').then(r=>{if(!r.ok)throw new Error();return r.json()}).then(c=>{uploadLimit=c.max_upload_mb*1024*1024;maxImagePixels=c.max_image_pixels;Object.values(formats).forEach(f=>f.hint=f.hint.replace('80 MB',`${c.max_upload_mb} MB`));if(mode)$('file-hint').textContent=formats[mode].hint;const cap=$('video-capacity-note');if(cap)cap.textContent=c.max_upload_mb>=500?'This server accepts uploads up to 500 MB. Large files may still take significant time.':`This server currently accepts up to ${c.max_upload_mb} MB per file. 500 MB uploads require upgraded processing and upload infrastructure.`}).catch(()=>{});
const fileInput=$('file');
const sizeString=n=>!Number.isFinite(n)?'—':n>=1048576?`${(n/1048576).toFixed(2)} MB`:n>=1024?`${(n/1024).toFixed(1)} KB`:`${n} B`;
const cleanUrls=()=>{if(previewUrl){URL.revokeObjectURL(previewUrl);previewUrl=null}if(downloadUrl){URL.revokeObjectURL(downloadUrl);downloadUrl=null}};
const clearResult=()=>{dismissSuccess();$('status').textContent='';$('status').classList.remove('error');$('result-panel').hidden=true;if(downloadUrl){URL.revokeObjectURL(downloadUrl);downloadUrl=null}};
function modalBackground(inert){document.querySelectorAll('body > header, body > main, body > footer, .skip-link').forEach(el=>el.inert=inert);document.body.style.overflow=inert?'hidden':''}
function showPicker(){if(busy)return;lastFocus=document.activeElement;$('category-modal').hidden=false;modalBackground(true);$('category-modal').querySelector('button[data-close-picker]').focus()}
function hidePicker(){if($('category-modal').hidden)return;$('category-modal').hidden=true;modalBackground(false);lastFocus?.focus()}
document.querySelectorAll('[data-open-picker]').forEach(el=>el.addEventListener('click',showPicker));
document.querySelectorAll('[data-close-picker]').forEach(el=>el.addEventListener('click',hidePicker));
function syncCropFields(){const c=drawnCrop||{x:0,y:0,width:sourceInfo.width,height:sourceInfo.height};$('crop-x').value=c.x;$('crop-y').value=c.y;$('crop-w').value=c.width;$('crop-h').value=c.height}
function openCrop(){if(busy||!sourceInfo||mode!=='image'||!previewUrl)return;lastFocus=document.activeElement;$('crop-modal').hidden=false;modalBackground(true);$('crop-image').src=previewUrl;drawnCrop=cropSelection?{...cropSelection}:null;syncCropFields();$('crop-modal').querySelector('button[data-close-crop]').focus();requestAnimationFrame(renderCrop)}
function hideCrop(){if($('crop-modal').hidden)return;$('crop-modal').hidden=true;pointerStart=null;modalBackground(false);lastFocus?.focus()}
document.querySelectorAll('[data-close-crop]').forEach(el=>el.addEventListener('click',hideCrop));
document.addEventListener('keydown',e=>{
  const modal=['category-modal','crop-modal'].map($).find(el=>!el.hidden);if(!modal)return;
  if(e.key==='Escape'){e.preventDefault();hidePicker();hideCrop()}
  if(e.key==='Tab'){
    const items=[...modal.querySelectorAll('button, input, select, a[href]')].filter(el=>!el.disabled&&el.getClientRects().length);
    const first=items[0],last=items.at(-1);
    if(e.shiftKey&&document.activeElement===first){e.preventDefault();last.focus()}
    else if(!e.shiftKey&&document.activeElement===last){e.preventDefault();first.focus()}
  }
});
function setMode(next){
  if(busy||!formats[next])return;
  mode=next;hidePicker();fileInput.value='';sourceInfo=null;cropSelection=null;clearResult();cleanUrls();
  $('workspace').hidden=false;$('workspace-title').textContent=formats[next].title;$('workspace-subtitle').textContent=formats[next].subtitle;
  $('file-hint').textContent=formats[next].hint;fileInput.accept=formats[next].accept;
  const fmt=$('format');fmt.replaceChildren(...formats[next].outputs.map(item=>{const opt=document.createElement('option');opt.value=item;opt.textContent=item.toUpperCase();return opt}));
  if(next==='pdf')fmt.value='docx';
  $('note').textContent=formats[next].note;$('image-options').hidden=next!=='image';$('video-options').hidden=next!=='video';
  document.querySelectorAll('#image-options input, #image-options select').forEach(el=>el.disabled=next!=='image');$('video-width').disabled=next!=='video';
  $('file-preview').hidden=true;$('crop-trigger-row').hidden=true;$('size-goal').value='limit';$('width').value='';$('height').value='';$('target').value='';$('video-width').value='';$('lock-ratio').checked=true;$('resize-mode').value='contain';
  document.querySelectorAll('[data-mode]').forEach(el=>el.classList.toggle('active',el.dataset.mode===next));
  refreshSummary();$('workspace-title').focus({preventScroll:true});$('workspace').scrollIntoView({behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'auto':'smooth',block:'start'});
}
document.querySelectorAll('[data-mode]').forEach(el=>el.addEventListener('click',()=>setMode(el.dataset.mode)));
function chosenFile(){return fileInput.files?.[0]||null}
function refreshSummary(){
  const file=chosenFile();
  $('summary-original').textContent=file?`${file.name} · ${sizeString(file.size)}`:'Choose a file';
  $('summary-output').textContent=$('format').value?.toUpperCase()||'—';
  let dimensions='Keep original';
  if(mode==='image'){
    const w=$('width').value,h=$('height').value;
    if(w||h)dimensions=`${w||'Auto'} × ${h||'Auto'} px`;
    else if(cropSelection)dimensions=`${cropSelection.width} × ${cropSelection.height} px (crop)`;
    else if(sourceInfo)dimensions=`${sourceInfo.width} × ${sourceInfo.height} px`;
  }else if(mode==='video'&&$('video-width').value)dimensions=`Max width ${$('video-width').value} px`;
  else if(mode!=='image')dimensions='Not applicable';
  $('summary-dimensions').textContent=dimensions;
  $('summary-size').textContent=$('target').value?`≤ ${$('target').value} ${$('size-unit').value}`:'No limit set';
}
function showFile(){
  clearResult();cropSelection=null;sourceInfo=null;$('crop-summary').textContent='No custom crop';
  if(previewUrl){URL.revokeObjectURL(previewUrl);previewUrl=null}
  const file=chosenFile();$('file-preview').hidden=!file;$('crop-trigger-row').hidden=true;
  if(!file){refreshSummary();return}
  $('preview-name').textContent=file.name;$('preview-meta').textContent=sizeString(file.size);
  $('preview-image').hidden=true;$('detail-placeholder').hidden=false;
  if(file.size>uploadLimit){$('status').textContent=`Maximum upload size is ${sizeString(uploadLimit)}. Please choose a smaller file.`;$('status').classList.add('error');refreshSummary();return}
  if(mode==='image'){
    previewUrl=URL.createObjectURL(file);
    const image=new Image();image.onload=()=>{
      if(chosenFile()!==file)return;
      if(image.naturalWidth*image.naturalHeight>maxImagePixels){$('status').textContent=`Image exceeds the ${maxImagePixels/1000000}-megapixel limit.`;$('status').classList.add('error');return}
      sourceInfo={width:image.naturalWidth,height:image.naturalHeight};
      $('preview-image').src=previewUrl;$('preview-image').hidden=false;$('detail-placeholder').hidden=true;
      $('preview-meta').textContent=`${image.naturalWidth} × ${image.naturalHeight} px · ${sizeString(file.size)}`;
      $('crop-trigger-row').hidden=false;refreshSummary();
    };image.onerror=()=>{if(chosenFile()!==file)return;$('status').textContent='Preview unavailable in this browser. You can still convert supported files, including TIFF.';$('status').classList.add('error')};image.src=previewUrl;
  }
  refreshSummary();
}
fileInput.addEventListener('change',showFile);
$('clear-file').addEventListener('click',()=>{fileInput.value='';showFile()});
const drop=$('drop');['dragenter','dragover'].forEach(name=>drop.addEventListener(name,e=>{e.preventDefault();drop.classList.add('drag')}));['dragleave','drop'].forEach(name=>drop.addEventListener(name,e=>{e.preventDefault();drop.classList.remove('drag')}));
drop.addEventListener('drop',e=>{if(busy)return;if(e.dataTransfer?.files?.length>1){$('status').textContent='Choose one file at a time.';return}if(e.dataTransfer?.files?.length){const dt=new DataTransfer();dt.items.add(e.dataTransfer.files[0]);fileInput.files=dt.files;showFile()}});
$('format').addEventListener('change',()=>{clearResult();refreshSummary()});
['target','size-unit','video-width','resize-mode','size-goal'].forEach(id=>$(id).addEventListener('input',()=>{clearResult();refreshSummary()}));
$('size-goal').addEventListener('change',()=>{$('size-goal-hint').textContent=$('size-goal').value==='close'?'Best effort: the converter aims for good quality under your cap; exact byte-for-byte sizing cannot be guaranteed.':'The result will stay within your chosen limit where technically possible. If not, we’ll explain why.';});
function selectedRatio(){return cropSelection?cropSelection.width/cropSelection.height:sourceInfo?sourceInfo.width/sourceInfo.height:null}
function dimensionChange(changed){
  if($('lock-ratio').checked&&selectedRatio()){
    const ratio=selectedRatio(),value=Number($(changed).value);
    if(value>0){const paired=changed==='width'?'height':'width';$(paired).value=changed==='width'?Math.max(1,Math.round(value/ratio)):Math.max(1,Math.round(value*ratio))}
    else $(changed==='width'?'height':'width').value='';
  }
  clearResult();refreshSummary();
}
$('width').addEventListener('input',()=>dimensionChange('width'));
$('height').addEventListener('input',()=>dimensionChange('height'));
$('lock-ratio').addEventListener('change',()=>{if($('lock-ratio').checked&&$('width').value)dimensionChange('width')});
$('open-crop').addEventListener('click',openCrop);
function cropBoundPoint(e){
  const imageRect=$('crop-image').getBoundingClientRect();
  return {x:Math.min(imageRect.width,Math.max(0,e.clientX-imageRect.left)),y:Math.min(imageRect.height,Math.max(0,e.clientY-imageRect.top)),rect:imageRect};
}
function renderCrop(){
  const element=$('crop-rect');if(!drawnCrop||!sourceInfo){element.hidden=true;$('crop-coordinates').textContent='No crop selected — the whole image will be used.';return}
  const r=$('crop-image').getBoundingClientRect(),stage=$('crop-stage').getBoundingClientRect();
  element.hidden=false;element.style.left=`${r.left-stage.left+drawnCrop.x/sourceInfo.width*r.width}px`;element.style.top=`${r.top-stage.top+drawnCrop.y/sourceInfo.height*r.height}px`;
  element.style.width=`${drawnCrop.width/sourceInfo.width*r.width}px`;element.style.height=`${drawnCrop.height/sourceInfo.height*r.height}px`;
  $('crop-coordinates').textContent=`Crop area: ${drawnCrop.width} × ${drawnCrop.height} px · x=${drawnCrop.x}, y=${drawnCrop.y}`;
}
$('crop-stage').addEventListener('pointerdown',e=>{
  if(!sourceInfo)return;
  const p=cropBoundPoint(e);pointerStart={x:p.x,y:p.y};$('crop-stage').setPointerCapture(e.pointerId);
});
$('crop-stage').addEventListener('pointermove',e=>{
  if(!pointerStart||!sourceInfo)return;
  const p=cropBoundPoint(e),r=p.rect,x0=Math.min(pointerStart.x,p.x),y0=Math.min(pointerStart.y,p.y),x1=Math.max(pointerStart.x,p.x),y1=Math.max(pointerStart.y,p.y);
  drawnCrop={x:Math.round(x0/r.width*sourceInfo.width),y:Math.round(y0/r.height*sourceInfo.height),width:Math.round((x1-x0)/r.width*sourceInfo.width),height:Math.round((y1-y0)/r.height*sourceInfo.height)};
  drawnCrop.width=Math.min(drawnCrop.width,sourceInfo.width-drawnCrop.x);drawnCrop.height=Math.min(drawnCrop.height,sourceInfo.height-drawnCrop.y);syncCropFields();renderCrop();
});
function finishCrop(){pointerStart=null}
$('crop-stage').addEventListener('pointerup',finishCrop);$('crop-stage').addEventListener('pointercancel',finishCrop);
$('crop-image').addEventListener('load',renderCrop);
window.addEventListener('resize',()=>{if(!$('crop-modal').hidden)renderCrop()});
['crop-x','crop-y','crop-w','crop-h'].forEach(id=>$(id).addEventListener('input',()=>{
  drawnCrop={x:Number($('crop-x').value),y:Number($('crop-y').value),width:Number($('crop-w').value),height:Number($('crop-h').value)};renderCrop();
}));
$('reset-crop').addEventListener('click',()=>{drawnCrop=null;syncCropFields();renderCrop()});
$('apply-crop').addEventListener('click',()=>{
  if(drawnCrop&&(!Object.values(drawnCrop).every(Number.isInteger)||drawnCrop.x<0||drawnCrop.y<0||drawnCrop.width<1||drawnCrop.height<1||drawnCrop.x+drawnCrop.width>sourceInfo.width||drawnCrop.y+drawnCrop.height>sourceInfo.height)){
    $('crop-coordinates').textContent='Enter whole pixels inside the image, with width and height of at least 1.';return;
  }
  cropSelection=drawnCrop?{...drawnCrop}:null;$('crop-summary').textContent=cropSelection?`Crop: ${cropSelection.width} × ${cropSelection.height} px`:'No custom crop';
  if($('lock-ratio').checked&&$('width').value)dimensionChange('width');
  clearResult();refreshSummary();hideCrop();
});
function setBusy(value){
  busy=value;$('convert-form').setAttribute('aria-busy',String(value));
  document.querySelectorAll('button, #convert-form input, #convert-form select').forEach(el=>{
    if(value){el.dataset.wasDisabled=String(el.disabled);el.disabled=true}else{el.disabled=el.dataset.wasDisabled==='true';delete el.dataset.wasDisabled}
  });
}
$('convert-form').addEventListener('submit',async e=>{
  e.preventDefault();if(busy)return;await capabilitiesReady;if(busy)return;const selected=chosenFile();const state=$('status');clearResult();
  if(!selected){state.textContent='Choose a file first.';state.classList.add('error');return}
  if(selected.size>uploadLimit){state.textContent=`Maximum upload size is ${sizeString(uploadLimit)}.`;state.classList.add('error');return}
  if(!selected.size){state.textContent='Please choose a nonempty file.';state.classList.add('error');return}
  const extension='.'+selected.name.split('.').pop().toLowerCase();if(!formats[mode].accept.split(',').includes(extension)){state.textContent='Unsupported file type for this category.';state.classList.add('error');return}
  let targetMb=null;
  if($('target').value){const value=Number($('target').value);targetMb=$('size-unit').value==='KB'?value/1024:value;if(!Number.isFinite(targetMb)||targetMb<1/1024||targetMb>500){state.textContent='Target must be between 1 KB and 500 MB.';state.classList.add('error');return}}
  const btn=$('submit');const requestedFormat=$('format').value;setBusy(true);btn.innerHTML='Converting your file…';state.textContent='Processing your file. Larger videos and documents may take longer.';
  try{
    const data=new FormData();data.append('file',selected);data.append('category',mode);data.append('output_format',$('format').value);
    if(targetMb!==null)data.append('target_mb',String(targetMb));
    if(mode==='image'){
      if($('width').value)data.append('max_width',$('width').value);
      if($('height').value)data.append('max_height',$('height').value);
      data.append('resize_mode',$('resize-mode').value);
      if(cropSelection){data.append('crop_x',cropSelection.x);data.append('crop_y',cropSelection.y);data.append('crop_width',cropSelection.width);data.append('crop_height',cropSelection.height)}
    }
    if(mode==='video'&&$('video-width').value)data.append('max_width',$('video-width').value);
    const res=await fetch('/api/convert',{method:'POST',body:data});
    if(!res.ok){const response=await res.json().catch(()=>({}));throw new Error(typeof response.detail==='string'?response.detail:`Conversion failed (HTTP ${res.status})`)}
    const blob=await res.blob();downloadUrl=URL.createObjectURL(blob);
    const name=(selected.name.replace(/\.[^.]+$/,'').replace(/[^a-zA-Z0-9_-]/g,'_').slice(0,65)||'file')+'_converted.'+requestedFormat;
    $('download').href=downloadUrl;$('download').download=name;
    $('result-details').textContent=`${name} · ${sizeString(blob.size)}`;
    $('result-panel').hidden=false;state.textContent='Conversion complete. Your download is ready.';
     $('toast-details').textContent=`${sizeString(blob.size)} · ${requestedFormat.toUpperCase()} · ready to download`;
     $('toast-download').href=downloadUrl;$('toast-download').download=name;$('success-toast').hidden=false;
     $('download').focus();
    if(mode==='image'){const resultImage=new Image();resultImage.onload=()=>{$('result-details').textContent=`${resultImage.naturalWidth} × ${resultImage.naturalHeight} px · ${sizeString(blob.size)}`};resultImage.src=downloadUrl}
  }catch(error){state.textContent=error?.message||'Unable to convert this file.';state.classList.add('error')}
  finally{setBusy(false);btn.innerHTML='Convert file <span aria-hidden="true">↗</span>'}
});
