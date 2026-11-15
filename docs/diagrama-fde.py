import html,sys,re
out=sys.argv[1]
cells=[];n=[1]
def nid(): n[0]+=1; return f"c{n[0]}"
def esc(t): return html.escape(t,quote=True).replace("\n","&#xa;")
F="fontFamily=Segoe UI;"
def box(id,label,x,y,w,h,style):
    cells.append(f'<mxCell id="{id}" value="{esc(label)}" style="{style}" vertex="1" parent="1"><mxGeometry x="{x}" y="{y}" width="{w}" height="{h}" as="geometry"/></mxCell>')
def edge(a,b,label="",dash=0,ex="",color="#4a5560"):
    cells.append(f'<mxCell id="{nid()}" value="{esc(label)}" style="edgeStyle=orthogonalEdgeStyle;rounded=1;html=1;endArrow=blockThin;endFill=1;strokeColor={color};strokeWidth=2;fontSize=10;{F}labelBackgroundColor=#ffffff;dashed={dash};{ex}" edge="1" parent="1" source="{a}" target="{b}"><mxGeometry relative="1" as="geometry"/></mxCell>')
def zone(id,label,x,y,w,h,color,fill="none",dash=1,fs=12):
    box(id,label,x,y,w,h,f"rounded=1;arcSize=3;whiteSpace=wrap;html=1;{F}fontSize={fs};fontStyle=1;verticalAlign=top;align=left;spacingLeft=12;spacingTop=6;fillColor={fill};strokeColor={color};fontColor={color};dashed={dash};dashPattern=6 4;strokeWidth=2;")
K={"svc":("#ffffff","#2e8b57"),"edge":("#fff4e0","#e0a254"),"data":("#e8f1fb","#2f6fb5"),"guard":("#fff7d6","#c99a00"),"human":("#fdeee9","#c0504d"),"ext":("#fdeaea","#e5675a"),"todo":("#f4f4f4","#8a8f98")}
def node(id,label,x,y,kind="svc",w=150,h=62,shape=""):
    f,s=K[kind]; d="dashed=1;" if kind=="todo" else ""
    box(id,label,x,y,w,h,f"{shape or 'rounded=1;arcSize=14;'}whiteSpace=wrap;html=1;{F}fontSize=11;fillColor={f};strokeColor={s};strokeWidth=2;{d}")
def badge(nm,k,dx=-12,dy=-12):
    c=[c for c in cells if f'id="{nm}"' in c][0]; m=re.search(r'x="(\d+)" y="(\d+)"',c)
    box(nid(),str(k),int(m.group(1))+dx,int(m.group(2))+dy,26,26,f"ellipse;html=1;fillColor=#0b5cad;strokeColor=#ffffff;strokeWidth=2;fontColor=#ffffff;fontStyle=1;fontSize=12;{F}")
box("t","fde-demo — Build del track DataCamp “Forward Deployed Engineer” · en producción (https://fde.analizodatos.com · VPS Hetzner, Alemania)",20,10,1500,30,f"text;html=1;fontSize=18;fontStyle=1;{F}align=left;fontColor=#1b2733;")
zone("z1","Personas",20,70,190,540,"#c0504d")
zone("z2","VPS Hetzner CX33 · Nuremberg, UE — todo el razonamiento ocurre aquí",230,70,1010,540,"#2e8b57",fill="#f8fcfa")
zone("zA","🔒 Entrada · proxy TLS (Traefik) + Cloudflare DNS",245,110,185,470,"#e0a254",fill="#ffffff",fs=11)
zone("zB","App fde-demo (FastAPI · LangGraph)",445,110,780,300,"#2e8b57",fill="#ffffff",fs=11)
zone("zD","Datos",445,425,780,155,"#2f6fb5",fill="#ffffff",fs=11)
zone("z3","Servicios externos",1265,70,260,250,"#e5675a")
node("usuario","👤 Usuario\n(navegador)",40,140,"human",w=150)
node("admin","👨 Manuel\n(dueño de la demo)",40,420,"human",w=150)
node("dns","🌐 Cloudflare DNS\nA → 167.233.82.133",260,150,"edge",w=160,h=70)
node("traefik","🔒 Traefik\nTLS + Let's Encrypt\n(termina HTTPS)",260,300,"edge",w=160,h=80)
# app: fila 1
node("landing","🖥 Landing con chat\n(static/index.html)",465,150,"edge",w=140,h=70)
node("chatapi","⚙ POST /chat y\n/chat/stream (SSE)",620,150,"svc",w=140)
node("middleware","🛡 Middleware\nauth X-API-Key + log",775,150,"guard",w=140)
node("retrieve","📄 Retriever BM25\n(k=3 chunks)",935,150,"svc",w=140)
node("gate","🚧 Gate LLM\n¿el contexto alcanza?",1110,150,"guard",w=140)
# app: fila 2 (serpentín ←)
node("bump","🔁 Reformular\n(feedback loop ×1)",935,270,"svc",w=140)
node("generate","💬 Generador\ncon citas [Sección]",775,270,"svc",w=140)
node("escalate","✋ Escalado\n→ tool create_ticket",620,270,"svc",w=140,h=80)
node("stream","📡 Respuesta en vivo\nSSE token a token",465,270,"edge",w=140,h=70)
# datos
node("kb","📚 Corpus de conocimiento\ndocs/kb.md (6 secciones)",1000,465,"data",w=180,h=85,shape="shape=cylinder3;boundedLbl=1;backgroundOutline=1;size=10;")
node("tickets","🎟 tickets.jsonl\n(escalados con tool call)",800,465,"data",w=170,h=85,shape="shape=cylinder3;boundedLbl=1;backgroundOutline=1;size=10;")
node("logs","📝 logs/app.jsonl\n(requests, tickets, latencia)",600,475,"data",w=180,h=65)
node("groq","🤖 Groq · gpt-oss-120b\n(gate + generación\n+ tool calling)",1285,110,"ext",w=220,h=90)
node("lets","🔐 Let's Encrypt\n(certificado TLS)",1285,250,"ext",w=220)
node("github","💾 Repo git\n(clawd/projects/…fde-demo)",1285,470,"data",w=220,h=65)
for a,b,l,d in [("usuario","dns","HTTPS",0),("dns","traefik","",0),("traefik","landing","",0),
 ("landing","chatapi","",0),("chatapi","middleware","",0),("middleware","retrieve","",0),
 ("retrieve","gate","",0),("gate","bump","contexto insuficiente (1º)",1),("bump","retrieve","",0),
 ("gate","generate","contexto suficiente",0),("gate","escalate","2º fallo → escalar",1),
 ("generate","stream","",0),("stream","usuario","respuesta",1),
 ("retrieve","kb","BM25 k=3",0),("escalate","tickets","function calling",0),
 ("middleware","logs","eventos",1),("chatapi","groq","gate · generación · tools",0),("traefik","lets","HTTP-01",1),
 ("admin","github","commit/deploy",1),("github","z2","docker deploy",1)]:
    edge(a,b,l,d)
for k,nm in enumerate(["usuario","traefik","landing","chatapi","middleware","retrieve","gate","generate","stream","tickets","logs"],1):
    badge(nm,k,-12,-12)
leg=["1  El usuario abre https://fde.analizodatos.com: Cloudflare resuelve el dominio al VPS (A record, sin proxy de CF).",
"2  Traefik termina el TLS (cert de Let's Encrypt, renovación automática) y enruta por Host al container fde-demo de la red dokploy-network.",
"3  La landing (HTML estático) carga y corre el chat en el navegador; no guarda estado del servidor.",
"4  Cada pregunta va a POST /chat o /chat/stream: FastAPI con Pydantic de schema y respuesta SSE (token a token).",
"5  El middleware verifica la API key si FDE_API_KEY está seteada (401 si falta) y registra el evento en logs JSONL (path, status, ms).",
"6  El retriever BM25 (lexical, 2 etapas, k=3) busca sobre los 6 chunks de docs/kb.md. Decisión documentada: sin embeddings para no sumar un proveedor; el swap a un vector store es drop-in.",
"7  El gate (LLM, temperatura 0) pregunta si el contexto alcanzó para responder. Arista condicional de LangGraph: SÍ → generar; NO con 1er intento → reformular y volver a recuperar (feedback loop); NO con 2do → escalar.",
"8  El generador responde en español con citas [Sección] y el grafo queda trazado (cada nodo es un paso verificable).",
"9  La respuesta sale por SSE token a token y la landing la muestra en vivo con las fuentes usadas.",
"10 Si el gate falla dos veces, el escalado usa function calling real: el LLM decide los argumentos del tool create_ticket y el ticket queda persistido en tickets.jsonl (ESC-XXXXXXXX).",
"11 Toda operación queda en logs/app.jsonl (requests, latencias, tickets) — la capa LLMOps del curso 8/16: eval offline con eval_set.json (correctness 9/9, groundedness 6/6)."]
box("leg","<b>Qué ocurre en cada paso</b><br>"+"<br>".join(html.escape(t) for t in leg),20,630,1180,240,f"text;html=1;whiteSpace=wrap;align=left;verticalAlign=top;{F}fontSize=11;fillColor=#ffffff;strokeColor=#c3cad3;spacing=8;")
box("key","<b>Leyenda</b><br>Naranja: entrada · Verde: servicio · Amarillo: guardrail · Azul: datos · Rosa: persona · Rojo: externo. Línea discontinua: relación secundaria o flujo de retorno (feedback loop / escalado).",1215,630,310,140,f"text;html=1;whiteSpace=wrap;align=left;verticalAlign=top;{F}fontSize=11;fillColor=#ffffff;strokeColor=#c3cad3;spacing=8;")
open(out,"w").write('<mxfile host="app.diagrams.net"><diagram name="fde-demo - Componentes" id="fde-demo-v1"><mxGraphModel dx="1600" dy="900" grid="1" gridSize="10" page="1" pageScale="1" pageWidth="1600" pageHeight="900" background="#ffffff"><root><mxCell id="0"/><mxCell id="1" parent="0"/>'+"".join(cells)+'</root></mxGraphModel></diagram></mxfile>')
