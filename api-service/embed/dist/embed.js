"use strict";(()=>{function X(e){var v;let t=h=>{var f;return(f=e==null?void 0:e.getAttribute(h))!=null?f:""},n=window,a=(v=n.__EMBED_CONFIG)!=null?v:n.EMBED_CONFIG,r=(h,f)=>{var b;return t(f)||(a?String((b=a[h])!=null?b:""):"")},i=r("agent","data-agent");i||console.error("[Helperium Widget] Missing data-agent attribute");let s=r("lang","data-lang"),c=navigator.language.startsWith("ru")?"ru":"en";return Object.freeze({agent:i,apiBase:r("apiBase","data-api-base")||window.location.origin,title:r("title","data-title")||"Assistant",greeting:r("greeting","data-greeting")||"How can I help?",accent:r("accent","data-accent")||"#0f766e",position:r("position","data-position")==="left"?"left":"right",lang:s==="ru"||s==="en"?s:c,placeholder:r("placeholder","data-placeholder")||"Ask a question...",width:r("width","data-width")||"min(380px, calc(100vw - 28px))",height:r("height","data-height")||"min(620px, calc(100vh - 44px))",triggerOffsetBottom:r("triggerOffsetBottom","data-trigger-offset-bottom")||"16px",headerColor:r("headerColor","data-header-color"),showHeader:r("showHeader","data-show-header")!=="false",botBubbleColor:r("botBubbleColor","data-bot-bubble-color")||"#eef3f4",botBubbleText:r("botBubbleText","data-bot-bubble-text")||"var(--ink)",voiceInput:r("voiceInput","data-voice-input")!=="false",voiceOutput:r("voiceOutput","data-voice-output")!=="false",voiceToggle:r("voiceToggle","data-voice-toggle")==="classic"?"classic":"telegram"})}var Z=`<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
  <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
</svg>
`;var Q=`<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
  <line x1="6" y1="12" x2="18" y2="12"/>
</svg>
`;var tt=`<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
  <line x1="22" y1="2" x2="11" y2="13"/>
  <polygon points="22 2 15 22 11 13 2 9 22 2"/>
</svg>
`;var et=`<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
  <rect x="10" y="3" width="4" height="8" rx="2" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/>
  <path d="M7 11a5 5 0 0 0 10 0" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/>
  <path d="M12 16v3" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/>
  <path d="M9 19h6" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/>
</svg>
`;var nt=`<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
  <rect x="10" y="3" width="4" height="8" rx="2" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/>
  <path d="M7 11a5 5 0 0 0 10 0" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/>
  <path d="M12 16v3" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/>
  <path d="M9 19h6" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/>
  <line x1="3" y1="3" x2="21" y2="21" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/>
</svg>
`;var T={chat:Z,close:Q,send:tt,mic:et,micOff:nt,thinking:'<div class="at-thinking-dots"><span></span><span></span><span></span></div>'};function L(e){return String(e).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;").replace(/'/g,"&#039;")}function z(e){try{let n=sessionStorage.getItem(e);if(n)return n}catch(n){}let t=typeof crypto!="undefined"&&crypto.randomUUID?crypto.randomUUID():"sess-"+Date.now()+"-"+Math.random().toString(36).slice(2,10);try{sessionStorage.setItem(e,t)}catch(n){}return t}function at(e){try{let t=sessionStorage.getItem(e);if(!t)return[];let n=JSON.parse(t);return Array.isArray(n)?n:[]}catch(t){return[]}}function rt(e,t){try{sessionStorage.setItem(e,JSON.stringify(t))}catch(n){}}function N(e,t){function n(){return at(e).filter(i=>i.sessionId===t).map(i=>({kind:i.kind,text:i.text,tools:i.tools||[]}))}function a(r,i,s){let c=at(e);c.push({sessionId:t,kind:r,text:String(i||""),tools:s||[],ts:Date.now()});let v=c.filter(h=>h.sessionId===t);if(v.length>100){let h=v.length-100,f=0,b=c.filter(p=>p.sessionId===t&&f<h?(f++,!1):!0);rt(e,b);return}rt(e,c)}return{readStored:n,appendStored:a}}function S(e,t,n){let a=document.createElement(e);return a.className=t,n!==void 0&&(a.innerHTML=n),a}function V(){return!!(navigator.mediaDevices&&navigator.mediaDevices.getUserMedia)}function it(e,t){let n=t.position==="left"?"at-left":"at-right",a=S("button","at-trigger "+n,T.chat);e.appendChild(a);let r=S("div","at-panel "+n+" at-hidden");e.appendChild(r);let i=S("div","at-head"),s=S("div","at-head-info");s.innerHTML="<strong>"+L(t.title)+"</strong><span>"+L(t.agent)+"</span>";let c=S("div","at-head-status");c.innerHTML='<span class="at-dot"></span> '+(t.lang==="ru","Online"),s.appendChild(c);let v=S("button","at-close",T.close);i.appendChild(s),i.appendChild(v),r.appendChild(i);let h=S("div","at-messages");r.appendChild(h);let f=document.createElement("form");f.className="at-form";let b=document.createElement("textarea");b.rows=1,b.placeholder=t.placeholder,b.style.height="38px";let p=S("button","at-mic-btn",T.mic);p.type="button",p.title=t.lang==="ru"?"\u0417\u0430\u0436\u043C\u0438\u0442\u0435 \u0434\u043B\u044F \u0437\u0430\u043F\u0438\u0441\u0438":"Hold to record";let g=S("button","at-send-btn",T.send);g.type="submit";let o=t.voiceToggle==="telegram"&&t.voiceInput&&V(),m=S("div","at-swap-btn "+(o?"at-show-mic":"at-show-send"));m.appendChild(p),m.appendChild(g),!o&&t.voiceInput&&V()&&m.classList.add("at-legacy"),(!t.voiceInput||!V())&&(p.style.display="none");let x=S("div","at-form-row");x.appendChild(b),x.appendChild(m),f.appendChild(x);let y=S("div","at-mic-timer");return f.insertBefore(y,x),r.appendChild(f),{trigger:a,panel:r,messages:h,form:f,textarea:b,closeBtn:v,sendBtn:g,head:i,micBtn:p,micTimer:y,swapBtn:m}}function W(e){return e.classList.contains("at-msg-row")?e.querySelector(".at-msg")||e:(e.classList.contains("at-msg"),e)}function st(e){let t=e.closest(".at-msg-row");if(t){t.remove();return}e.remove()}function M(e){e&&(e.scrollTop=e.scrollHeight)}function ot(e){return!!(e&&e.scrollHeight-e.scrollTop-e.clientHeight<48)}function St(e,t,n){let a=e.body.getReader(),r=new TextDecoder,i="";function s(){return a.read().then(c=>{var h;if(c.done)return;i+=r.decode(c.value,{stream:!0});let v=i.split(`

`);i=v.pop();for(let f of v){let b=f.split(`
`).find(g=>g.indexOf("data:")===0);if(!b)continue;let p;try{p=JSON.parse(b.slice(5).trim())}catch(g){continue}switch(t.classList.contains("at-thinking")&&t.classList.remove("at-thinking"),p.type){case"token":n.callbacks.onToken(p.text||"");break;case"final":n.callbacks.onFinal(p.text||"");break;case"tool_call":{let o=t.dataset.tools||"[]",m=t.dataset.displayNames||"{}",x=JSON.parse(o),y=JSON.parse(m);p.name&&x.indexOf(p.name)===-1&&(x.push(p.name),t.dataset.tools=JSON.stringify(x)),p.display_name&&p.name&&!y[p.name]&&(y[p.name]=p.display_name,t.dataset.displayNames=JSON.stringify(y)),n.callbacks.onToolCall(p.name||"",p.display_name);break}case"audio":n.config.voiceOutput&&p.data&&n.callbacks.onAudio(p.data);break;case"done":if(t.classList.contains("at-error"))return;(h=t.dataset.raw)!=null&&h.trim()||n.callbacks.onFinal(n.config.lang==="ru"?"\u041D\u0435 \u0443\u0434\u0430\u043B\u043E\u0441\u044C \u043F\u043E\u043B\u0443\u0447\u0438\u0442\u044C \u043E\u0442\u0432\u0435\u0442.":"No response.");let g=[];try{g=JSON.parse(t.dataset.tools||"[]")}catch(o){}n.callbacks.onDone(t.dataset.raw||"",g),t.dataset.saved="true",n.scrollToBottom(n.messagesEl);break;case"error":t.classList.remove("at-thinking"),t.classList.add("at-error"),t.textContent=p.text||(n.config.lang==="ru"?"\u041F\u0440\u043E\u0438\u0437\u043E\u0448\u043B\u0430 \u043E\u0448\u0438\u0431\u043A\u0430.":"An error occurred.");break}}return s()})}return s()}function $(e){let{message:t,targetNode:n,config:a,sessionId:r,messagesEl:i,retryAttempts:s,maxRetries:c,callbacks:v,addMessage:h,removeMsgRow:f,scheduleRetry:b,retryChat:p,scrollToBottom:g}=e;n.classList.add("at-thinking");let o=a.apiBase+"/api/chat/"+encodeURIComponent(a.agent);fetch(o,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({message:t,session_id:r})}).then(m=>{if(m.status===429){n.classList.remove("at-thinking"),f(n);let x=m.headers.get("Retry-After"),y=5;if(x){let k=parseInt(x,10);!isNaN(k)&&k>0&&(y=k)}if(s.set(t,(s.get(t)||0)+1),s.get(t)>=c){let k=document.createElement("div");k.className="at-msg at-assistant at-error",k.innerHTML="\u26A0\uFE0F Server overloaded.";let H=document.createElement("button");H.className="at-retry-btn",H.textContent="Retry",k.appendChild(H),i.appendChild(k),g(i),H.addEventListener("click",()=>{s.delete(t),k.remove(),p(t)});return}let C=document.createElement("div");C.className="at-msg at-assistant",C.textContent="\u26A0\uFE0F "+(a.lang==="ru"?"\u0421\u0435\u0440\u0432\u0435\u0440 \u043F\u0435\u0440\u0435\u0433\u0440\u0443\u0436\u0435\u043D. \u041F\u043E\u0432\u0442\u043E\u0440 \u0447\u0435\u0440\u0435\u0437":"Server overloaded. Retry in")+" "+y+"s.",i.appendChild(C),g(i),b(t,y*1e3);return}if(!m.ok){n.classList.remove("at-thinking"),n.classList.add("at-error"),n.textContent="Error: "+m.status;return}return St(m,n,e)}).catch(()=>{n.classList.remove("at-thinking"),n.classList.add("at-error"),n.innerHTML="\u26A0\uFE0F "+(a.lang==="ru"?"\u041D\u0435\u0442 \u0441\u043E\u0435\u0434\u0438\u043D\u0435\u043D\u0438\u044F \u0441 \u0441\u0435\u0440\u0432\u0435\u0440\u043E\u043C.":"No connection to server.")+'<br><button class="at-retry-btn">'+(a.lang==="ru"?"\u041F\u043E\u0432\u0442\u043E\u0440\u0438\u0442\u044C":"Retry")+"</button>";let m=n.querySelector(".at-retry-btn");m&&m.addEventListener("click",()=>{n.classList.remove("at-error"),n.innerHTML=T.thinking,$(e)})})}function lt(e,t,n,a="en"){let r=e.body.getReader(),i=new TextDecoder,s="";function c(){return r.read().then(v=>{var f;if(v.done)return;s+=i.decode(v.value,{stream:!0});let h=s.split(`

`);s=h.pop();for(let b of h){let p=b.split(`
`).find(o=>o.startsWith("data:"));if(!p)continue;let g;try{g=JSON.parse(p.slice(5).trim())}catch(o){continue}switch(t.classList.contains("at-thinking")&&t.classList.remove("at-thinking"),g.type){case"token":n.onToken(g.text||"");break;case"final":n.onFinal(g.text||"");break;case"tool_call":{let m=JSON.parse(t.dataset.tools||"[]"),x=JSON.parse(t.dataset.displayNames||"{}");g.name&&!m.includes(g.name)&&(m.push(g.name),t.dataset.tools=JSON.stringify(m)),g.display_name&&g.name&&!x[g.name]&&(x[g.name]=g.display_name,t.dataset.displayNames=JSON.stringify(x)),n.onToolCall(g.name||"",g.display_name);break}case"audio":g.data&&n.onAudio(g.data);break;case"done":if(t.classList.contains("at-error"))return;(f=t.dataset.raw)!=null&&f.trim()||n.onFinal(a==="ru"?"\u041D\u0435 \u0443\u0434\u0430\u043B\u043E\u0441\u044C \u043F\u043E\u043B\u0443\u0447\u0438\u0442\u044C \u043E\u0442\u0432\u0435\u0442.":"No response.");let o=[];try{o=JSON.parse(t.dataset.tools||"[]")}catch(m){}n.onDone(t.dataset.raw||"",o),t.dataset.saved="true";break;case"error":t.classList.remove("at-thinking"),t.classList.add("at-error"),t.textContent=g.text||(a==="ru"?"\u041F\u0440\u043E\u0438\u0437\u043E\u0448\u043B\u0430 \u043E\u0448\u0438\u0431\u043A\u0430.":"An error occurred.");break}}return c()})}return c()}var ct=120,Mt="audio/webm;codecs=opus",Lt="audio/webm";function pt(){return{mediaRecorder:null,micChunks:[],micStream:null,micStartTime:0,micDuration:0,micTimerInterval:null}}function dt(e,t){e.micDuration=Math.floor((Date.now()-e.micStartTime)/1e3);let n=Math.floor(e.micDuration/60),a=e.micDuration%60;t.textContent=(n>0?n+"m ":"")+a+"s"}function I(e,t){if(!(e.mediaRecorder&&e.mediaRecorder.state==="recording")){if(!navigator.mediaDevices||!navigator.mediaDevices.getUserMedia){t.micBtn.classList.add("at-mic-disabled");return}navigator.mediaDevices.getUserMedia({audio:!0}).then(n=>{e.micStream=n,e.micChunks=[];let a=Mt;MediaRecorder.isTypeSupported(a)||(a=Lt),e.mediaRecorder=new MediaRecorder(n,{mimeType:a}),e.mediaRecorder.ondataavailable=r=>{r.data.size>0&&e.micChunks.push(r.data)},e.mediaRecorder.onstop=()=>{n.getTracks().forEach(c=>c.stop()),e.micStream=null,t.micBtn.innerHTML=T.mic,t.micBtn.classList.remove("at-mic-recording"),t.micTimer.classList.remove("at-mic-timer-visible"),e.micTimerInterval&&(clearInterval(e.micTimerInterval),e.micTimerInterval=null);let r=new Blob(e.micChunks,{type:a});if(r.size===0)return;let i=t.micTimer.textContent||e.micDuration+"s";t.addMessage("user","\u{1F3A4} "+i,{persist:!0});let s=t.addMessage("assistant","",{thinking:!0,persist:!1,scroll:!1});t.onStreamVoice(r,s)},e.mediaRecorder.start(),t.micBtn.innerHTML=T.micOff,t.micBtn.classList.add("at-mic-recording"),t.micTimer.classList.add("at-mic-timer-visible"),e.micStartTime=Date.now(),e.micDuration=0,dt(e,t.micTimer),e.micTimerInterval=window.setInterval(()=>dt(e,t.micTimer),1e3),ct>0&&setTimeout(()=>{e.mediaRecorder&&e.mediaRecorder.state==="recording"&&e.mediaRecorder.stop()},ct*1e3)}).catch(n=>{n.name==="NotAllowedError"||n.name==="PermissionDeniedError"?t.addMessage("assistant",t.config.lang==="ru"?"\u274C \u0420\u0430\u0437\u0440\u0435\u0448\u0438\u0442\u0435 \u0434\u043E\u0441\u0442\u0443\u043F \u043A \u043C\u0438\u043A\u0440\u043E\u0444\u043E\u043D\u0443 \u0432 \u043D\u0430\u0441\u0442\u0440\u043E\u0439\u043A\u0430\u0445 \u0431\u0440\u0430\u0443\u0437\u0435\u0440\u0430":"\u274C Please allow microphone access in browser settings",{persist:!1}):t.micBtn.classList.add("at-mic-disabled")})}}function j(e){e.mediaRecorder&&e.mediaRecorder.state==="recording"&&e.mediaRecorder.stop()}function gt(e,t,n){t.classList.add("at-thinking");let a=n.config.apiBase+"/api/chat/voice",r=new FormData;r.append("audio",e,"voice.webm"),r.append("session_id",n.sessionId),r.append("agent",n.config.agent),r.append("lang",n.config.lang),fetch(a,{method:"POST",body:r}).then(i=>{if(i.status===429){t.classList.remove("at-thinking"),t.remove();let s=document.createElement("div");s.className="at-msg at-assistant",s.textContent=n.config.lang==="ru"?"\u26A0\uFE0F \u0421\u0435\u0440\u0432\u0435\u0440 \u043F\u0435\u0440\u0435\u0433\u0440\u0443\u0436\u0435\u043D. \u041F\u043E\u043F\u0440\u043E\u0431\u0443\u0439\u0442\u0435 \u043F\u043E\u0437\u0436\u0435.":"\u26A0\uFE0F Server overloaded. Try again later.",n.messagesEl.appendChild(s),n.scrollToBottom(n.messagesEl);return}if(!i.ok){t.classList.remove("at-thinking"),t.classList.add("at-error"),t.textContent="Error: "+i.status;return}return lt(i,t,n.callbacks,n.config.lang)}).catch(()=>{t.classList.remove("at-thinking"),t.classList.add("at-error"),t.innerHTML="\u26A0\uFE0F "+(n.config.lang==="ru"?"\u041E\u0448\u0438\u0431\u043A\u0430 \u0441\u043E\u0435\u0434\u0438\u043D\u0435\u043D\u0438\u044F.":"Connection error.")})}function J(e){try{let t=atob(e),n=new Uint8Array(t.length);for(let s=0;s<t.length;s++)n[s]=t.charCodeAt(s);let a=new Blob([n],{type:"audio/mpeg"}),r=URL.createObjectURL(a);new Audio(r).play().catch(()=>{})}catch(t){}}function mt(e){let t=e.toLowerCase();return/поиск|найти|find|search/i.test(t)?"\u{1F50D}":/чтение|get|получени/i.test(t)?"\u{1F4CB}":/запрос|query/i.test(t)?"\u{1F4CA}":/list|список/i.test(t)?"\u{1F4CB}":"\u26A1"}function A(e,t){let n=t||{},a=[...new Set(e)];if(!a.length)return null;let r=document.createElement("div");return r.className="at-tool-strip",r.innerHTML=a.map(i=>{let s=n[i]||i;return`<span>${mt(s)} ${L(s)}</span>`}).join(""),r}function U(e,t,n,a){var v;let r=[...new Set(t)];if(!r.length)return;let i=((v=e.closest)==null?void 0:v.call(e,".at-msg-row"))||e,s=i.previousElementSibling;if(s&&s.className==="at-tool-strip"){s.innerHTML=r.map(h=>{let f=n[h]||h;return`<span>${mt(f)} ${L(f)}</span>`}).join("");return}let c=A(r,n);c&&a.insertBefore(c,i)}function B(e){let t=[],n=(e||"").split(`
`),a=0;for(;a<n.length;){let r=n[a];if(ut(n,a)){let s=[];for(;a<n.length&&n[a].trim().charAt(0)==="|";)s.push(n[a]),a++;t.push(Ct(s));continue}if(/^\s*[-*]\s+/.test(r)){let s=[];for(;a<n.length&&/^\s*[-*]\s+/.test(n[a]);)s.push(n[a].replace(/^\s*[-*]\s+/,"")),a++;t.push("<ul>"+s.map(c=>"<li>"+D(c)+"</li>").join("")+"</ul>");continue}if(/^\s*\d+\.\s+/.test(r)){let s=[];for(;a<n.length&&/^\s*\d+\.\s+/.test(n[a]);)s.push(n[a].replace(/^\s*\d+\.\s+/,"")),a++;t.push("<ol>"+s.map(c=>"<li>"+D(c)+"</li>").join("")+"</ol>");continue}let i=[];for(;a<n.length&&n[a].trim()&&!ut(n,a)&&!/^\s*[-*]\s+/.test(n[a])&&!/^\s*\d+\.\s+/.test(n[a]);)i.push(n[a]),a++;i.length&&t.push("<p>"+D(i.join(`
`)).replace(/\n/g,"<br>")+"</p>"),a<n.length&&!n[a].trim()&&a++}return t.join("")}function ut(e,t){let n=e[t],a=e[t+1];return!n||!a?!1:n.trim().charAt(0)==="|"&&/^\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?$/.test(a)}function Ct(e){let t=[];for(let r=0;r<e.length;r++){let i=e[r];if(/^\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?$/.test(i))continue;let s=i.trim().replace(/^\|/,"").replace(/\|$/,"").split("|").map(c=>c.trim());t.push(s)}if(!t.length)return"";let n=t[0],a=t.slice(1);return'<div class="at-table-wrap"><table><thead><tr>'+n.map(r=>"<th>"+D(r)+"</th>").join("")+"</tr></thead><tbody>"+a.map(r=>"<tr>"+r.map(i=>"<td>"+D(i)+"</td>").join("")+"</tr>").join("")+"</tbody></table></div>"}function D(e){return L(e).replace(/\*\*([^*]+)\*\*/g,"<strong>$1</strong>").replace(/\*([^*]+)\*/g,"<em>$1</em>").replace(/`([^`]+)`/g,"<code>$1</code>").replace(/\[([^\]]+)\]\(([^)]+)\)/g,'<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>')}var Et=20,Ht=3;function P(e,t,n){let a=e.dataset.raw||"";e.dataset.raw=a+t,e.dataset.typewriterRunning?e.dataset.typewriterBuffer=(e.dataset.typewriterBuffer||"")+t:(e.dataset.typewriterRunning="1",e.dataset.typewriterBuffer=a+t,e.dataset.typewriterDisplayed=a,ft(e,n))}function ft(e,t){let n=e.dataset.typewriterBuffer||"",a=e.dataset.typewriterDisplayed||"";if(a.length>=n.length){e.dataset.typewriterRunning="",e.innerHTML=B(n),M(t);return}let r=Math.min(Ht,n.length-a.length),i=n.slice(0,a.length+r);e.dataset.typewriterDisplayed=i;let s=B(i);if(i.length<n.length)e.classList.add("at-typing-cursor"),e.innerHTML=s;else{e.classList.remove("at-typing-cursor"),e.innerHTML=s,e.dataset.typewriterRunning="",M(t);return}ot(t)&&M(t),setTimeout(()=>ft(e,t),Et)}function Y(e,t){e.classList.remove("at-thinking"),e.dataset.raw=t,e.innerHTML=B(t)}function ht(e,t,n,a){let r=a||{};if(e==="assistant"){let i=document.createElement("div");i.className="at-msg-row";let s=document.createElement("div");s.className="at-avatar",s.textContent="AI";let c=document.createElement("div");c.className="at-msg at-assistant",r.thinking?(c.dataset.raw="",c.innerHTML=T.thinking):(c.dataset.raw=t||"",c.innerHTML=B(t||"")),i.appendChild(c),i.appendChild(s),r.before?n.insertBefore(i,r.before):n.appendChild(i)}else{let i=document.createElement("div");i.className="at-msg at-user",i.textContent=t||"",r.before?n.insertBefore(i,r.before):n.appendChild(i)}return r.scroll!==!1&&M(n),n.lastElementChild}function q(e,t,n,a){let r=n();if(!r.length){a("assistant",e.greeting,{persist:!1,scroll:!1});return}t.innerHTML="";let i=[];for(let s of r)if(s.kind==="user")a("user",s.text,{persist:!1,scroll:!1});else if(s.kind==="assistant"){let c=(s.tools||[]).filter(Boolean),v=String(s.text||"");if(!v.trim()&&c.length>0){i=i.concat(c);continue}let h=i.concat(c);if(i=[],h.length>0){let g=A(h);g&&t.appendChild(g)}let f=document.createElement("div");f.className="at-msg-row";let b=document.createElement("div");b.className="at-avatar",b.textContent="AI";let p=document.createElement("div");p.className="at-msg at-assistant",p.dataset.raw=v,p.innerHTML=B(v),f.appendChild(p),f.appendChild(b),t.appendChild(f)}if(i.length>0){let s=A(i);s&&t.appendChild(s)}M(t)}var bt=`/*
 * Design Tokens
 *
 * Glassmorphism palette with frosted glass surfaces.
 * All visual variables in one place.
 */
:host {
  all: initial;
  --accent: #0f766e;
  --accent-rgb: 15, 118, 110;
  --accent-strong: #0b5f59;
  --accent-soft: #14b8a6;
  --ink: #0f172a;
  --ink-light: #475569;
  --muted: #94a3b8;
  --line: rgba(0, 0, 0, 0.06);
  --panel: rgba(255, 255, 255, 0.92);
  --panel-solid: #ffffff;
  --glass-bg: rgba(255, 255, 255, 0.72);
  --glass-border: rgba(255, 255, 255, 0.45);
  --glass-blur: 20px;
  --rose: #e11d48;
  --blue: #2563eb;
  --shadow-panel:
    0 4px 6px -1px rgba(0, 0, 0, 0.05),
    0 10px 15px -3px rgba(0, 0, 0, 0.08),
    0 20px 50px -12px rgba(0, 0, 0, 0.15);
  --shadow-trigger:
    0 4px 14px rgba(var(--accent-rgb), 0.35),
    0 1px 3px rgba(0, 0, 0, 0.08);
  --radius: 12px;
  --radius-lg: 18px;
  --radius-xl: 20px;
  --ease-spring: cubic-bezier(0.34, 1.56, 0.64, 1);
  --ease-smooth: cubic-bezier(0.25, 0.1, 0.25, 1);
  --font: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
}

.at-root {
  all: initial;
  display: block;
  font-family: var(--font);
  font-size: 14px;
  line-height: 1.5;
  color: var(--ink);
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}
/*
 * Root Container
 *
 * Base styles for the Shadow DOM root element.
 */
.at-root {
  all: initial;
  display: block;
  font-family: var(--font);
  font-size: 14px;
  line-height: 1.5;
  color: var(--ink);
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}
/*
 * Trigger Button
 *
 * Floating glass-morphic action button.
 * Spring-animated entrance, pulse ring, hover lift.
 */
.at-trigger {
  position: fixed;
  bottom: 20px;
  width: 58px;
  height: 58px;
  border: 0;
  border-radius: 50%;
  background: linear-gradient(135deg, var(--accent), var(--accent-soft));
  color: white;
  cursor: pointer;
  box-shadow: var(--shadow-trigger);
  z-index: 2147483647;
  font-size: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: transform 0.35s var(--ease-spring), box-shadow 0.3s var(--ease-smooth);
  padding: 0;
  outline: none;
  animation: at-trigger-in 0.6s var(--ease-spring) both;
  animation-delay: 0.3s;
}

/* Pulse ring \u2014 subtle breathing */
.at-trigger::after {
  content: "";
  position: absolute;
  inset: -4px;
  border-radius: 50%;
  background: var(--accent);
  opacity: 0;
  animation: at-pulse-ring 3s ease-out infinite;
  animation-delay: 2s;
}

/* Hover: lift + glow */
.at-trigger:hover {
  transform: scale(1.1) translateY(-2px);
  box-shadow:
    0 6px 20px rgba(var(--accent-rgb), 0.4),
    0 2px 6px rgba(0, 0, 0, 0.1);
}

/* Active: press down */
.at-trigger:active {
  transform: scale(0.92);
  transition-duration: 0.1s;
}

/* Position variants */
.at-trigger.at-right { right: 20px; }
.at-trigger.at-left { left: 20px; }

/* SVG icon */
.at-trigger svg {
  width: 26px;
  height: 26px;
  position: relative;
  z-index: 1;
  transition: transform 0.2s var(--ease-spring);
}

.at-trigger:hover svg {
  transform: scale(1.05);
}
/*
 * Chat Panel
 *
 * Frosted glass panel with backdrop-blur.
 * Spring-animated open/close from bottom corner.
 */
.at-panel {
  position: fixed;
  bottom: 20px;
  width: min(400px, calc(100vw - 24px));
  height: min(640px, calc(100vh - 40px));
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: var(--panel);
  backdrop-filter: blur(var(--glass-blur));
  -webkit-backdrop-filter: blur(var(--glass-blur));
  border: 1px solid var(--glass-border);
  border-radius: var(--radius-xl);
  box-shadow: var(--shadow-panel);
  z-index: 2147483646;
  transition: opacity 0.3s var(--ease-smooth),
              transform 0.4s var(--ease-spring);
  transform-origin: bottom right;
}

/* Position variants */
.at-panel.at-right {
  right: 20px;
  transform-origin: bottom right;
}
.at-panel.at-left {
  left: 20px;
  transform-origin: bottom left;
}

/* Hidden state: scale down + fade */
.at-panel.at-hidden {
  opacity: 0;
  transform: translateY(16px) scale(0.92);
  pointer-events: none;
}

/* Visible state: spring up */
.at-panel:not(.at-hidden) {
  animation: at-panel-in 0.45s var(--ease-spring) both;
}
/*
 * Header
 *
 * Glass-morphic top bar with gradient accent.
 * Clean typography, subtle separator.
 */
.at-head {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
  padding: 16px 16px 14px;
  background: linear-gradient(135deg,
    rgba(var(--accent-rgb), 0.95),
    rgba(var(--accent-rgb), 0.88));
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  color: white;
  flex-shrink: 0;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}

/* Agent info */
.at-head-info strong {
  display: block;
  font-size: 15px;
  font-weight: 600;
  color: white;
  letter-spacing: -0.01em;
}

.at-head-info span {
  display: block;
  margin-top: 1px;
  font-size: 12px;
  opacity: 0.7;
  font-weight: 400;
}

/* Online status */
.at-head-status {
  display: flex;
  align-items: center;
  gap: 5px;
  margin-top: 2px;
  font-size: 11px;
  opacity: 0.8;
  font-weight: 500;
}

.at-head-status .at-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #34d399;
  box-shadow: 0 0 6px rgba(52, 211, 153, 0.5);
  animation: at-dot-pulse 2.5s ease-in-out infinite;
}

/* Close button */
.at-close {
  width: 32px;
  height: 32px;
  border: 0;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.15);
  backdrop-filter: blur(4px);
  color: white;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  padding: 0;
  transition: background 0.2s, transform 0.2s var(--ease-spring);
}

.at-close:hover {
  background: rgba(255, 255, 255, 0.25);
  transform: scale(1.08);
}

.at-close:active {
  transform: scale(0.92);
}

.at-close svg {
  width: 16px;
  height: 16px;
}
/*
 * Messages Area
 *
 * Scrollable container with frosted background.
 * Smooth message entrance, modern bubble design.
 */

/* Scrollable container */
.at-messages {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  overflow-x: hidden;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 4px;
  background: rgba(248, 250, 252, 0.5);
}

/* Custom scrollbar \u2014 thin, modern */
.at-messages::-webkit-scrollbar { width: 5px; }
.at-messages::-webkit-scrollbar-track { background: transparent; }
.at-messages::-webkit-scrollbar-thumb {
  background: rgba(0, 0, 0, 0.12);
  border-radius: 10px;
}
.at-messages::-webkit-scrollbar-thumb:hover {
  background: rgba(0, 0, 0, 0.2);
}

/* \u2500\u2500\u2500 Message row (assistant with avatar) \u2500\u2500\u2500 */
.at-msg-row {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  margin-bottom: 2px;
  animation: at-msg-in 0.35s var(--ease-spring) both;
}

/* AI avatar \u2014 glass circle */
.at-avatar {
  width: 38px;
  height: 38px;
  border-radius: 50%;
  background: linear-gradient(135deg, var(--accent), var(--accent-soft));
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  font-size: 13px;
  font-weight: 700;
  margin-left: 14px;
  margin-top: -7px;
  position: relative;
  z-index: 1;
  border: 2px solid var(--panel-solid);
  box-shadow: 0 2px 8px rgba(var(--accent-rgb), 0.25);
}

/* \u2500\u2500\u2500 Base message bubble \u2500\u2500\u2500 */
.at-msg {
  min-width: 0;
  max-width: 88%;
  flex: 0 0 auto;
  padding: 10px 14px;
  font-size: 14px;
  line-height: 1.5;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

/* User: right-aligned, accent gradient */
.at-msg.at-user {
  align-self: flex-end;
  background: linear-gradient(135deg, var(--accent), var(--accent-soft));
  color: white;
  border-radius: var(--radius) var(--radius) 4px var(--radius);
  box-shadow: 0 2px 8px rgba(var(--accent-rgb), 0.2);
  animation: at-msg-in 0.3s var(--ease-spring) both;
}

/* Assistant: left-aligned, frosted glass */
.at-msg.at-assistant {
  align-self: flex-start;
  background: var(--glass-bg);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
  border: 1px solid var(--glass-border);
  color: var(--ink);
  white-space: normal;
  margin-top: -2px;
  border-radius: var(--radius) var(--radius) var(--radius) 4px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.04);
}

/* Thinking state */
.at-msg.at-assistant.at-thinking {
  padding: 16px 20px 14px;
  min-height: 40px;
  display: flex;
  align-items: center;
}

/* Error message */
.at-msg.at-error {
  background: rgba(254, 242, 242, 0.9);
  backdrop-filter: blur(8px);
  color: var(--rose);
  border: 1px solid rgba(254, 202, 202, 0.6);
  border-radius: var(--radius);
  font-size: 13px;
}

/* \u2500\u2500\u2500 Markdown inside assistant messages \u2500\u2500\u2500 */
.at-msg.at-assistant p { margin: 0 0 6px; }
.at-msg.at-assistant p:last-child,
.at-msg.at-assistant ul:last-child,
.at-msg.at-assistant ol:last-child { margin-bottom: 0; }
.at-msg.at-assistant ul,
.at-msg.at-assistant ol { margin: 0 0 10px; padding-left: 22px; }
.at-msg.at-assistant li { margin: 3px 0; }
.at-msg.at-assistant strong { font-weight: 700; }

.at-msg.at-assistant code {
  padding: 2px 6px;
  border-radius: 6px;
  background: rgba(var(--accent-rgb), 0.08);
  color: var(--accent-strong);
  font-size: 0.9em;
  font-family: 'SF Mono', 'Fira Code', 'Cascadia Code', monospace;
}

.at-msg.at-assistant a {
  color: var(--accent);
  text-decoration: underline;
  text-underline-offset: 2px;
}

.at-msg.at-assistant a:hover {
  color: var(--accent-strong);
}

/* \u2500\u2500\u2500 Thinking dots \u2500\u2500\u2500 */
.at-thinking-dots {
  display: flex;
  align-items: center;
  gap: 6px;
}

.at-thinking-dots span {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--accent-soft);
  animation: at-dot-bounce 1.4s ease-in-out infinite both;
}

.at-thinking-dots span:nth-child(1) { animation-delay: -0.32s; }
.at-thinking-dots span:nth-child(2) { animation-delay: -0.16s; }
.at-thinking-dots span:nth-child(3) { animation-delay: 0s; }

/* Typing cursor */
.at-typing-cursor::after {
  content: "\u258C";
  display: inline;
  animation: at-cursor-blink 0.8s step-end infinite;
  color: var(--accent-soft);
  font-size: 14px;
  margin-left: 1px;
}
/*
 * Input Form
 *
 * Glass-morphic bottom bar with frosted textarea.
 * Smooth focus transitions, modern button design.
 */

/* Form container */
.at-form {
  padding: 8px 12px 12px;
  border-top: 1px solid var(--line);
  background: rgba(255, 255, 255, 0.6);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  flex-shrink: 0;
}

/* Horizontal row */
.at-form-row {
  display: flex;
  gap: 8px;
  align-items: flex-end;
}

/* Textarea \u2014 glass input, matches button height */
.at-form textarea {
  flex: 1;
  resize: none;
  min-height: 38px;
  max-height: 120px;
  border: 1px solid var(--line);
  border-radius: 19px;
  padding: 8px 14px;
  font-family: var(--font);
  font-size: 14px;
  line-height: 1.45;
  outline: none;
  color: var(--ink);
  background: rgba(255, 255, 255, 0.8);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
  transition: border-color 0.2s, box-shadow 0.2s, background 0.2s;
  box-sizing: border-box;
}

.at-form textarea:focus {
  border-color: rgba(var(--accent-rgb), 0.5);
  box-shadow: 0 0 0 3px rgba(var(--accent-rgb), 0.08);
  background: rgba(255, 255, 255, 0.95);
}

.at-form textarea::placeholder {
  color: var(--muted);
  font-weight: 400;
}

/* Mic button */
.at-mic-btn {
  width: 38px;
  height: 38px;
  border: 0;
  border-radius: 50%;
  background: rgba(0, 0, 0, 0.04);
  color: var(--ink-light);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0;
  flex-shrink: 0;
  transition: background 0.2s, color 0.2s, transform 0.25s var(--ease-spring);
}

.at-mic-btn:hover {
  background: rgba(0, 0, 0, 0.08);
  color: var(--ink);
  transform: scale(1.08);
}

/* Recording state */
.at-mic-btn.at-mic-recording {
  background: var(--rose);
  color: white;
  transform: scale(1.1);
  animation: at-mic-pulse 1.2s ease-in-out infinite;
}

/* Disabled */
.at-mic-btn.at-mic-disabled {
  opacity: 0.25;
  cursor: not-allowed;
  transform: none;
}

/* Send button \u2014 gradient accent */
.at-send-btn {
  width: 38px;
  height: 38px;
  border: 0;
  border-radius: 50%;
  background: linear-gradient(135deg, var(--accent), var(--accent-soft));
  color: white;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0;
  flex-shrink: 0;
  transition: transform 0.25s var(--ease-spring), opacity 0.2s, box-shadow 0.2s;
  box-shadow: 0 2px 8px rgba(var(--accent-rgb), 0.25);
}

.at-send-btn:hover {
  transform: scale(1.08);
  box-shadow: 0 4px 12px rgba(var(--accent-rgb), 0.35);
}

.at-send-btn:active {
  transform: scale(0.9);
  transition-duration: 0.1s;
}

.at-send-btn:disabled {
  opacity: 0.3;
  cursor: not-allowed;
  transform: none;
  box-shadow: none;
}

.at-send-btn svg { width: 18px; height: 18px; }

/* Mic recording timer */
.at-mic-timer {
  text-align: center;
  color: var(--rose);
  font-size: 12px;
  font-weight: 700;
  padding: 4px 0 2px;
  letter-spacing: 0.03em;
  display: none;
}

.at-mic-timer-visible { display: block; }

/* \u2500\u2500\u2500 Telegram-style animated button swap \u2500\u2500\u2500 */

/* Container for the morphing mic/send button */
.at-swap-btn {
  position: relative;
  width: 38px;
  height: 38px;
  flex-shrink: 0;
}

/* Both buttons stacked absolutely */
.at-swap-btn .at-mic-btn,
.at-swap-btn .at-send-btn {
  position: absolute;
  inset: 0;
  transition: transform 0.3s var(--ease-spring), opacity 0.25s ease;
}

/* Mic visible, send hidden */
.at-swap-btn.at-show-mic .at-mic-btn {
  transform: scale(1) rotate(0deg);
  opacity: 1;
  pointer-events: auto;
}
.at-swap-btn.at-show-mic .at-send-btn {
  transform: scale(0.3) rotate(-90deg);
  opacity: 0;
  pointer-events: none;
}

/* Send visible, mic hidden */
.at-swap-btn.at-show-send .at-send-btn {
  transform: scale(1) rotate(0deg);
  opacity: 1;
  pointer-events: auto;
}
.at-swap-btn.at-show-send .at-mic-btn {
  transform: scale(0.3) rotate(90deg);
  opacity: 0;
  pointer-events: none;
}

/* Hold-to-record visual feedback */
.at-swap-btn .at-mic-btn.at-mic-holding {
  transform: scale(1.15);
  background: var(--rose);
  color: white;
}

/* Legacy mode: both visible side by side (no swap, overrides at-show-*) */
.at-swap-btn.at-legacy .at-mic-btn,
.at-swap-btn.at-legacy .at-send-btn {
  position: static;
  transform: none;
  opacity: 1;
  pointer-events: auto;
}
.at-swap-btn.at-legacy {
  display: contents;
}
.at-swap-btn.at-legacy .at-mic-btn {
  display: flex;
}
.at-swap-btn.at-legacy .at-send-btn {
  display: flex;
}
/*
 * Tool Strip & Tables
 *
 * Tool call pills with glass effect.
 * Modern table styling with subtle borders.
 */

/* Tool call pills */
.at-tool-strip {
  align-self: flex-start;
  max-width: 92%;
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 2px;
}

.at-tool-strip span {
  display: inline-flex;
  align-items: center;
  min-height: 24px;
  padding: 3px 10px;
  border-radius: 999px;
  background: rgba(var(--accent-rgb), 0.06);
  border: 1px solid rgba(var(--accent-rgb), 0.1);
  color: var(--accent);
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.01em;
  animation: at-msg-in 0.3s var(--ease-spring) both;
}

/* Markdown table */
.at-table-wrap {
  max-width: 100%;
  overflow-x: auto;
  margin: 10px 0 14px;
  border: 1px solid var(--line);
  border-radius: var(--radius);
  background: rgba(255, 255, 255, 0.6);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
}

.at-table-wrap table {
  min-width: 520px;
  width: 100%;
  border-collapse: collapse;
}

.at-table-wrap th,
.at-table-wrap td {
  padding: 10px 12px;
  border-bottom: 1px solid var(--line);
  font-size: 13px;
  line-height: 1.4;
}

.at-table-wrap th {
  background: rgba(0, 0, 0, 0.02);
  color: var(--muted);
  font-weight: 600;
  text-align: left;
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0.03em;
}

.at-table-wrap tr:last-child td { border-bottom: 0; }
.at-table-wrap tr:hover td { background: rgba(0, 0, 0, 0.015); }

/* Retry button */
.at-retry-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  margin-top: 10px;
  padding: 8px 18px;
  border: 1px solid rgba(var(--accent-rgb), 0.3);
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.8);
  backdrop-filter: blur(8px);
  color: var(--accent);
  cursor: pointer;
  font-size: 13px;
  font-weight: 500;
  font-family: var(--font);
  outline: none;
  transition: all 0.2s var(--ease-smooth);
}

.at-retry-btn:hover {
  background: var(--accent);
  color: white;
  border-color: var(--accent);
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(var(--accent-rgb), 0.25);
}

.at-retry-btn:active {
  transform: translateY(0);
}

/* Retry countdown */
.at-msg.at-retry-countdown {
  align-self: center;
  background: transparent;
  color: var(--muted);
  font-size: 12px;
  text-align: center;
  max-width: 100%;
  font-weight: 500;
}
/*
 * Animations & Keyframes
 *
 * Spring-based, smooth animations for all interactive elements.
 */

/* Trigger button entrance \u2014 spring from below */
@keyframes at-trigger-in {
  0% {
    opacity: 0;
    transform: translateY(20px) scale(0.6);
  }
  100% {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}

/* Panel entrance \u2014 spring from corner */
@keyframes at-panel-in {
  0% {
    opacity: 0;
    transform: translateY(16px) scale(0.92);
  }
  100% {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}

/* Trigger pulse ring \u2014 slow breathing */
@keyframes at-pulse-ring {
  0% { transform: scale(1); opacity: 0.25; }
  50% { transform: scale(1.2); opacity: 0; }
  100% { transform: scale(1.2); opacity: 0; }
}

/* Status dot pulse */
@keyframes at-dot-pulse {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.5; transform: scale(0.8); }
}

/* Message entrance \u2014 slide up + fade */
@keyframes at-msg-in {
  0% {
    opacity: 0;
    transform: translateY(8px);
  }
  100% {
    opacity: 1;
    transform: translateY(0);
  }
}

/* Thinking dots \u2014 wave bounce */
@keyframes at-dot-bounce {
  0%, 80%, 100% {
    transform: translateY(0) scale(0.75);
    opacity: 0.35;
  }
  40% {
    transform: translateY(-7px) scale(1);
    opacity: 0.85;
  }
}

/* Typing cursor blink */
@keyframes at-cursor-blink {
  50% { opacity: 0; }
}

/* Mic recording pulse */
@keyframes at-mic-pulse {
  0% { box-shadow: 0 0 0 0 rgba(225, 29, 72, 0.3); }
  70% { box-shadow: 0 0 0 10px rgba(225, 29, 72, 0); }
  100% { box-shadow: 0 0 0 0 rgba(225, 29, 72, 0); }
}
/*
 * Responsive
 *
 * Full-screen takeover on mobile devices.
 */

@media (max-width: 480px) {
  .at-panel {
    width: 100vw !important;
    height: 100vh !important;
    bottom: 0 !important;
    right: 0 !important;
    left: 0 !important;
    border-radius: 0 !important;
    border: 0 !important;
    backdrop-filter: none;
    -webkit-backdrop-filter: none;
  }

  .at-trigger { bottom: 14px; }
  .at-trigger.at-right { right: 14px; }
  .at-trigger.at-left { left: 14px; }

  .at-head { padding: 14px 14px 12px; }
  .at-messages { padding: 14px; }
  .at-form { padding: 8px 10px 10px; }
}
`;var Bt=3;function Dt(){let e=document.currentScript;if(e&&e instanceof HTMLScriptElement)return e;let t=document.querySelector("script[data-agent]");if(t)return t;let n=document.querySelector('script[src*="embed.js"]');return n||null}function It(e){let t=e.replace("#",""),n=parseInt(t.length===3?t.split("").map(a=>a+a).join(""):t,16);return`${n>>16&255}, ${n>>8&255}, ${n&255}`}function At(e){let t=e.headerColor||e.accent;return`:host {
  --accent: ${e.accent};
  --accent-rgb: ${It(e.accent)};
  --accent-strong: ${e.accent};
  --trigger-offset-bottom: ${e.triggerOffsetBottom};
  --panel-width: ${e.width};
  --panel-height: ${e.height};
  --header-bg: ${t};
  --bot-bubble-bg: ${e.botBubbleColor};
  --bot-bubble-text: ${e.botBubbleText};
}
${e.showHeader?"":".at-head { display: none; }"}`}function xt(){var G,K;let e=Dt(),t=X(e);if(!t.agent)return;let n,a,r,i="at_messages_"+t.agent,s="at_session_"+t.agent;r=z(s),{readStored:n,appendStored:a}=N(i,r);let c=pt(),v=new Map,h=document.createElement("div");h.id="helperium-widget-"+t.agent.replace(/[^a-zA-Z0-9_-]/g,"");let f=h.attachShadow({mode:"open"}),b=document.createElement("style");b.textContent=bt,f.appendChild(b);let p=document.createElement("style");p.textContent=At(t),f.appendChild(p);let g=document.createElement("div");g.className="at-root",f.appendChild(g);let o=it(g,t),m=o.messages;function x(d,u,l){let w=ht(d,u,m,l);return l!=null&&l.persist&&a(d,u,l.tools),w}function y(d,u){let l=Math.ceil(u/1e3),w=document.createElement("div");w.className="at-msg at-retry-countdown",w.textContent=(t.lang==="ru"?"\u041F\u043E\u0432\u0442\u043E\u0440 \u0447\u0435\u0440\u0435\u0437":"Retry in")+" "+l+"s...",m.appendChild(w),M(m);let E=setInterval(()=>{l--,l<=0?(clearInterval(E),w.remove(),O(d)):w.textContent=(t.lang==="ru"?"\u041F\u043E\u0432\u0442\u043E\u0440 \u0447\u0435\u0440\u0435\u0437":"Retry in")+" "+l+"s..."},1e3)}function O(d){let u=x("assistant","",{thinking:!0,persist:!1,scroll:!1}),l=W(u);C(d,l)}function C(d,u){$({message:d,targetNode:u,config:t,sessionId:r,messagesEl:m,retryAttempts:v,maxRetries:Bt,callbacks:{onToken:l=>P(u,l,m),onFinal:l=>Y(u,l),onToolCall:(l,w)=>{let E=JSON.parse(u.dataset.tools||"[]"),R=JSON.parse(u.dataset.displayNames||"{}");E.includes(l)||(E.push(l),u.dataset.tools=JSON.stringify(E)),w&&!R[l]&&(R[l]=w,u.dataset.displayNames=JSON.stringify(R)),U(u,E,R,m)},onAudio:l=>J(l),onDone:(l,w)=>{a("assistant",l,w)},onError:l=>{u.classList.remove("at-thinking"),u.classList.add("at-error"),u.textContent=l}},addMessage:x,removeMsgRow:st,scheduleRetry:(l,w)=>y(l,w),retryChat:O,scrollToBottom:M})}o.trigger.addEventListener("click",()=>{o.panel.classList.remove("at-hidden"),o.trigger.style.display="none",o.textarea.focus(),M(m)}),o.closeBtn.addEventListener("click",()=>{o.panel.classList.add("at-hidden"),o.trigger.style.display="flex"});function k(){let d=o.textarea.value.trim();if(!d)return;o.textarea.value="",o.textarea.style.height="auto",H(),x("user",d,{persist:!0});let u=x("assistant","",{thinking:!0,persist:!1,scroll:!1}),l=W(u);C(d,l)}o.textarea.addEventListener("input",function(){this.style.height="auto",this.style.height=Math.min(this.scrollHeight,120)+"px",H()}),o.textarea.addEventListener("keydown",d=>{d.key==="Enter"&&!d.shiftKey&&(d.preventDefault(),k())}),o.form.addEventListener("submit",d=>{d.preventDefault(),k()});function H(){if(t.voiceToggle!=="telegram"||!_)return;o.textarea.value.trim().length>0?(o.swapBtn.classList.remove("at-show-mic"),o.swapBtn.classList.add("at-show-send")):(o.swapBtn.classList.remove("at-show-send"),o.swapBtn.classList.add("at-show-mic"))}let _=t.voiceInput&&typeof((G=navigator.mediaDevices)==null?void 0:G.getUserMedia)=="function";if(t.voiceToggle==="telegram"&&_){let d=!1;o.micBtn.addEventListener("mousedown",l=>{l.preventDefault(),!d&&(d=!0,o.micBtn.classList.add("at-mic-holding"),I(c,{micBtn:o.micBtn,micTimer:o.micTimer,config:t,sessionId:r,addMessage:x,onStreamVoice:F(),onStreamChat:C}))});let u=()=>{d&&(d=!1,o.micBtn.classList.remove("at-mic-holding"),j(c))};o.micBtn.addEventListener("mouseup",u),o.micBtn.addEventListener("mouseleave",u),o.micBtn.addEventListener("touchstart",l=>{l.preventDefault(),!d&&(d=!0,o.micBtn.classList.add("at-mic-holding"),I(c,{micBtn:o.micBtn,micTimer:o.micTimer,config:t,sessionId:r,addMessage:x,onStreamVoice:F(),onStreamChat:C}))},{passive:!1}),o.micBtn.addEventListener("touchend",u),o.micBtn.addEventListener("touchcancel",u)}else _&&(o.micBtn.style.display="flex",o.micBtn.addEventListener("mousedown",d=>{d.preventDefault(),o.micBtn.classList.contains("at-mic-recording")?j(c):I(c,{micBtn:o.micBtn,micTimer:o.micTimer,config:t,sessionId:r,addMessage:x,onStreamVoice:F(),onStreamChat:C})}));function F(){return(d,u)=>{gt(d,u,{config:t,sessionId:r,messagesEl:m,callbacks:{onToken:l=>P(u,l,m),onFinal:l=>Y(u,l),onToolCall:(l,w)=>{U(u,[l],w?{[l]:w}:{},m)},onAudio:l=>J(l),onDone:(l,w)=>{a("assistant",l,w)},onError:l=>{u.classList.remove("at-thinking"),u.classList.add("at-error"),u.textContent=l}},scrollToBottom:M})}}q(t,m,n,x),document.body.appendChild(h),window.__agentTutorSetAgent=d=>{if(!d)return;t.agent=d;let u="at_messages_"+d,l="at_session_"+d,w=z(l),E=N(u,w);n=E.readStored,a=E.appendStored,r=w;let R=o.head.querySelector(".at-head-info");R&&(R.innerHTML="<strong>"+L(t.title)+"</strong><span>"+L(d)+"</span>"),m.innerHTML="",q(t,m,n,x);try{localStorage.setItem("agentTutorAgentId",d)}catch(Ot){}};try{let d=localStorage.getItem("agentTutorAgentId");d&&t.agent!==d&&((K=window.__agentTutorSetAgent)==null||K.call(window,d))}catch(d){}}document.readyState==="loading"?document.addEventListener("DOMContentLoaded",xt):xt();})();
//# sourceMappingURL=embed.js.map
