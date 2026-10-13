const FAQ_URL = "https://gamefaqs.gamespot.com/psp/939233-yu-gi-oh-gx-tag-force-2/faqs/50402";
const FAQ_PROXY = "https://r.jina.ai/http://gamefaqs.gamespot.com/psp/939233-yu-gi-oh-gx-tag-force-2/faqs/50402";
const LOCAL_DATA = "data/cards.json";
const CACHE_KEY = "tf2_card_images_v1";

const packNames = [
"Beginner Monsters","Beginner Spells","Beginner Traps","Time to Gear Up","Intermediate Spells","Intermediate Traps","It's Fusion Time","Expert Spells","Expert Traps","Creeping Darkness","Dueling with Fire","Raging Waters","A Gust of Wind","Light from Above","Earthly Powers","Taste the Attributes","Power of the Heroes","Machiner's Force","Cyber Girl Rhapsody","Ojama Strike","Control Your Destiny","Dino Power","A Maiden's Love","Over the Rainbow","Making the Team","Simple is Best","Test of Luck","Dramatic a la carte","Vanilla Flavored","Reserve Magic","A Fresh, New Taste","Magic Carpet","A Dragon's Tale","Back for More","Twilight Ruler","Celestial Sign","Banner Of Courage","Don't Stop!","Spice Up Your Deck","Rock-Solid Tactics","A Bug's Deal","Sadie's Special Pack","Ms. Dorothy's Special Pack","Champion's Pack","Crush on You","Midday Constellation","Double Triple Destiny Draw","Checkered Flag"
];

const aliases = {
  "The Flute fo Summoning Kuriboh":"The Flute of Summoning Kuriboh",
  "Toon Cannon Solider":"Toon Cannon Soldier",
  "Hade-Hane":"Hane-Hane",
  "Mulitiply":"Multiply",
  "Relinguished":"Relinquished",
  "Wicked-Breaking Flameerge - Baou":"Wicked-Breaking Flamberge - Baou",
  "Gearfired the Swordmaster":"Gearfried the Swordmaster",
  "Metamorph":"Metalmorph",
  "Mask of Resitrict":"Mask of Restrict",
  "Spatical Collapse":"Spatial Collapse",
  "Cermonial Bell":"Ceremonial Bell",
  "Statellite Cannon":"Satellite Cannon",
  "Penumbral Solider Lady":"Penumbral Soldier Lady",
  "Giant Turle Who Feeds on Flames":"Giant Turtle Who Feeds on Flames",
  "Return to the Doomed":"Return of the Doomed"
};

const $ = s => document.querySelector(s);
let packs = [];
let currentPack = null;
let imageCache = JSON.parse(localStorage.getItem(CACHE_KEY) || "{}");

function setStatus(msg, cls="") {
  $("#status").className = "status " + cls;
  $("#status").textContent = msg;
}

function slugForImage(id){ return `images/packs/${String(id).padStart(2,"0")}.jpg`; }

function makePackObjects(cardPacks=[]) {
  const byName = new Map(cardPacks.map(p=>[p.name.toLowerCase(),p]));
  return packNames.map((name,i)=>{
    const p = byName.get(name.toLowerCase());
    return p || {id:i+1,name,cards:[]};
  });
}

async function getData() {
  try {
    const r = await fetch(LOCAL_DATA, {cache:"no-store"});
    if(r.ok) return await r.json();
  } catch {}
  const candidates = [FAQ_PROXY, FAQ_URL];
  let lastErr;
  for(const url of candidates){
    try{
      const r = await fetch(url, {cache:"no-store"});
      if(!r.ok) throw new Error(`${r.status} ${r.statusText}`);
      const text = await r.text();
      const parsed = parseGameFAQs(text);
      if(parsed.filter(p=>p.cards.length).length >= 40){
        return {source:FAQ_URL, packs:parsed};
      }
      throw new Error("La guía se descargó, pero no se pudieron reconocer los packs.");
    }catch(e){ lastErr=e; }
  }
  throw lastErr || new Error("No se pudo cargar GameFAQs.");
}

function parseGameFAQs(text){
  const section = text.split("4. Cards within the Packs")[1] || text;
  const re = /^\s*(\d{1,2})\s*-\s*Pack Name:\s*(.*?)\s*\(complete\)\s*$/gm;
  const heads=[...section.matchAll(re)];
  const result=[];
  for(let i=0;i<heads.length;i++){
    const h=heads[i], id=Number(h[1]), name=h[2].replace(/\s+/g," ").trim();
    const start=h.index+h[0].length;
    const end=i+1<heads.length?heads[i+1].index:section.length;
    const chunk=section.slice(start,end);
    const cards=[];
    if(id!==48){
      for(const line of chunk.split(/\r?\n/)){
        const m=line.match(/^\s*(\d{1,3})\s+(.+?)\s*$/);
        if(!m) continue;
        const n=Number(m[1]), card=m[2].trim();
        if(n>0 && n<=500 && card && !/^(Cover Image:|How To Unlock:|#\s+Cards)/i.test(card)){
          cards.push({number:n,name:card,lookup:aliases[card]||card});
        }
      }
    }
    result.push({id,name,cards});
  }
  result.sort((a,b)=>a.id-b.id);
  const all=[]; const seen=new Set();
  for(const p of result.filter(x=>x.id!==48)){
    for(const c of p.cards){
      const k=(c.lookup||c.name).toLowerCase();
      if(!seen.has(k)){seen.add(k);all.push({...c,number:all.length+1});}
    }
  }
  const p48=result.find(x=>x.id===48);
  if(p48) p48.cards=all;
  return makePackObjects(result);
}

function renderPacks(filter=""){
  const grid=$("#packsGrid"); grid.innerHTML="";
  const q=filter.toLowerCase();
  const list=packs.filter(p=>p.name.toLowerCase().includes(q));
  $("#packCount").textContent=`${list.length} de ${packs.length} packs`;
  for(const p of list){
    const el=$("#packTemplate").content.firstElementChild.cloneNode(true);
    const img=el.querySelector(".pack-image");
    const fallback=el.querySelector(".no-image");
    img.src=slugForImage(p.id);
    img.alt=p.name;
    img.onerror=()=>{img.style.display="none";fallback.style.display="block";};
    img.onload=()=>{fallback.style.display="none";};
    el.querySelector("h3").textContent=p.name;
    el.querySelector(".pack-number").textContent=`Pack ${String(p.id).padStart(2,"0")} · ${p.cards.length} cartas`;
    el.onclick=()=>openPack(p.id);
    grid.appendChild(el);
  }
}

function openPack(id){
  currentPack=packs.find(p=>p.id===id);
  if(!currentPack)return;
  $("#packsView").classList.add("hidden");
  $("#cardsView").classList.remove("hidden");
  $("#backBtn").classList.remove("hidden");
  $("#cardSearch").value="";
  $("#selectedPack").textContent=currentPack.name;
  $("#selectedInfo").textContent=`Pack ${String(currentPack.id).padStart(2,"0")} · ${currentPack.cards.length} cartas · fuente: GameFAQs`;
  renderCards();
  window.scrollTo({top:0,behavior:"smooth"});
}

function renderCards(){
  const grid=$("#cardsGrid"); grid.innerHTML="";
  const q=$("#cardSearch").value.trim().toLowerCase();
  const list=currentPack.cards.filter(c=>c.name.toLowerCase().includes(q));
  for(const c of list){
    const el=$("#cardTemplate").content.firstElementChild.cloneNode(true);
    el.querySelector("h3").textContent=c.name;
    const img=el.querySelector(".card-image");
    const loading=el.querySelector(".card-loading");
    const lookup=c.lookup||aliases[c.name]||c.name;
    img.alt=c.name;
    getCardImage(lookup,c.name).then(url=>{
      if(url){img.src=url; img.onload=()=>loading.style.display="none"; img.onerror=()=>{loading.textContent="Imagen no disponible";};}
      else loading.textContent="Imagen no encontrada";
    });
    grid.appendChild(el);
  }
}

async function getCardImage(lookup, displayName){
  const key=(lookup||displayName).trim().toLowerCase();
  if(imageCache[key]) return imageCache[key];
  try{
    const url=`https://db.ygoprodeck.com/api/v7/cardinfo.php?name=${encodeURIComponent(lookup||displayName)}`;
    const r=await fetch(url);
    if(r.ok){
      const data=await r.json();
      const card=data.data?.[0];
      const image=card?.card_images?.[0]?.image_url_small || card?.card_images?.[0]?.image_url;
      if(image){ imageCache[key]=image; saveCache(); return image; }
    }
    // Fallback for names with small spelling differences in the old FAQ.
    const fuzzy=`https://db.ygoprodeck.com/api/v7/cardinfo.php?fname=${encodeURIComponent(lookup||displayName)}`;
    const fr=await fetch(fuzzy);
    if(fr.ok){
      const fd=await fr.json();
      const card=fd.data?.[0];
      const image=card?.card_images?.[0]?.image_url_small || card?.card_images?.[0]?.image_url;
      if(image){ imageCache[key]=image; saveCache(); return image; }
    }
  }catch{}
  return null;
}

function saveCache(){
  try{localStorage.setItem(CACHE_KEY,JSON.stringify(imageCache));}catch{}
}

async function load(){
  setStatus("Cargando la guía de GameFAQs…");
  try{
    const data=await getData();
    packs=makePackObjects(data.packs||[]);
    renderPacks();
    setStatus(`Listo: ${packs.length} packs cargados. Las imágenes de los packs se leen de images/packs/01.jpg … 48.jpg.`, "ok");
  }catch(e){
    packs=makePackObjects([]);
    renderPacks();
    setStatus(`No se pudo cargar automáticamente la guía. ${e.message} Podés ejecutar tools/build_data.py para generar data/cards.json y luego abrir la página de nuevo.`, "error");
  }
}

$("#packSearch").addEventListener("input",e=>renderPacks(e.target.value));
$("#cardSearch").addEventListener("input",renderCards);
$("#backBtn").addEventListener("click",()=>{
  currentPack=null;
  $("#cardsView").classList.add("hidden");
  $("#packsView").classList.remove("hidden");
  $("#backBtn").classList.add("hidden");
});
$("#refreshBtn").addEventListener("click",load);

load();
