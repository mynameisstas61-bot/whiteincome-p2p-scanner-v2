const tg = window.Telegram?.WebApp;
if (tg) { tg.ready(); tg.expand(); }
const $ = (id) => document.getElementById(id);
const deposit = $("deposit"), depositNumber = $("depositNumber"), display = $("depositDisplay");
function formatNumber(n){return new Intl.NumberFormat("ru-RU",{maximumFractionDigits:2}).format(n)}
function syncDeposit(value){let n=Number(value);if(!Number.isFinite(n))n=1000;n=Math.min(100000,Math.max(10,n));deposit.value=n;depositNumber.value=n;display.textContent=formatNumber(n)}
deposit.addEventListener("input",()=>syncDeposit(deposit.value));
depositNumber.addEventListener("change",()=>syncDeposit(depositNumber.value));
document.querySelectorAll(".chip").forEach(btn=>btn.addEventListener("click",()=>btn.classList.toggle("active")));
function selectedAssets(){return [...document.querySelectorAll(".chip.active")].map(x=>x.dataset.asset)}
function selectedExchanges(){return [...$("exchangeChecks").querySelectorAll("input:checked")].map(x=>x.value)}
function escapeHtml(s){return String(s).replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]))}
function card(x){return `<article class="result-card"><div class="result-top"><div class="pair">${escapeHtml(x.symbol)}</div><div class="profit">${Number(x.estimated_net_pct_before_transfer_costs).toFixed(2)}%</div></div><div class="route">Купить: <b>${escapeHtml(x.buy_exchange)}</b> → продать: <b>${escapeHtml(x.sell_exchange)}</b></div><div class="metrics"><div class="metric"><span>Покупка</span><strong>${Number(x.buy_price).toPrecision(8)} USDT</strong></div><div class="metric"><span>Продажа</span><strong>${Number(x.sell_price).toPrecision(8)} USDT</strong></div><div class="metric"><span>Размер позиции</span><strong>${Number(x.estimated_size_base).toPrecision(6)} ${escapeHtml(x.symbol.split("/")[0])}</strong></div><div class="metric"><span>Оценка прибыли</span><strong>${Number(x.estimated_profit_usdt_before_transfer_costs).toFixed(2)} USDT</strong></div></div><div class="warning">До комиссий вывода/сети. Не гарантирует исполнение.</div></article>`}
$("scanBtn").addEventListener("click", async()=>{
  const assets=selectedAssets(), exchanges=selectedExchanges(), min=Number($("minSpread").value||5), dep=Number(deposit.value);
  if(assets.length===0){$("scanStatus").textContent="Выбери хотя бы один актив.";return}
  if(exchanges.length<2){$("scanStatus").textContent="Выбери минимум две биржи.";return}
  const base=(window.WHITEINCOME_CONFIG?.API_BASE_URL||"").replace(/\/$/,"");
  if(!base||base.includes("YOUR-BACKEND-HOST")){$("scanStatus").textContent="Backend ещё не подключён. Укажи URL backend в webapp/config.js.";return}
  $("scanBtn").disabled=true;$("scanBtn").textContent="Сканирую…";$("scanStatus").textContent="Запрашиваю публичные стаканы бирж…";
  try{
    const q=new URLSearchParams({deposit:String(dep),min_spread_pct:String(min),assets:["USDT",...assets].join(","),exchanges:exchanges.join(",")});
    const res=await fetch(`${base}/api/opportunities?${q.toString()}`,{cache:"no-store"});
    if(!res.ok)throw new Error(`Backend вернул HTTP ${res.status}`);
    const data=await res.json();const items=data.opportunities||[];
    $("resultCount").textContent=String(items.length);
    $("resultsList").innerHTML=items.length?items.map(card).join(""):'<div class="empty">Подходящих связок не найдено. Это не значит, что их нет: рынки могли быть недоступны или спред ниже порога.</div>';
    $("scanStatus").textContent=`Проверка завершена. Получено записей рынков: ${data.checked_markets??"—"}.`;
    if(data.warnings?.length){const note=document.createElement("div");note.className="warning";note.textContent=data.warnings.join(" ");$("resultsList").appendChild(note)}
  }catch(e){$("scanStatus").textContent=`Не удалось получить данные: ${e.message}. Проверь backend и доступность бирж.`}
  finally{$("scanBtn").disabled=false;$("scanBtn").textContent="⌕  Найти связки"}
});
