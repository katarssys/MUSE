const data=window.MUSE_DEMO;
const nav=document.getElementById("domainNav");
const intent=document.getElementById("intent");
const statusBadge=document.getElementById("statusBadge");
const pipeline=document.getElementById("pipeline");
const decisionTitle=document.getElementById("decisionTitle");
const decisionCopy=document.getElementById("decisionCopy");

function tone(text){
  const t=text.toLowerCase();
  if(t.includes("failed")||t.includes("unsafe")) return "fail";
  if(t.includes("blocked")||t.includes("insufficient")||t.includes("conflict")) return "warn";
  return "ok";
}

function render(item){
  document.querySelectorAll(".domain-button").forEach(function(b){b.classList.toggle("active",b.dataset.id===item.id);});
  intent.textContent=item.intent;
  statusBadge.textContent=item.status;
  decisionTitle.textContent=item.decision;
  decisionCopy.textContent=item.copy;
  pipeline.innerHTML="";
  item.steps.forEach(function(step,i){
    const article=document.createElement("article");
    article.className="step "+tone(step.join(" "));
    const kicker=document.createElement("div");
    kicker.className="step-kicker";
    kicker.textContent="0"+(i+1)+" · "+step[0].toUpperCase();
    const title=document.createElement("div");
    title.className="step-title";
    title.textContent=step[1];
    const items=document.createElement("div");
    items.className="step-items";
    step.slice(2).forEach(function(x){const d=document.createElement("div");d.className="step-item";d.textContent=x;items.appendChild(d);});
    article.appendChild(kicker);article.appendChild(title);article.appendChild(items);pipeline.appendChild(article);
  });
}

data.forEach(function(item){
  const b=document.createElement("button");
  b.className="domain-button";
  b.dataset.id=item.id;
  b.innerHTML='<span class="dot"></span>'+item.label;
  b.onclick=function(){render(item);};
  nav.appendChild(b);
});
render(data[0]);