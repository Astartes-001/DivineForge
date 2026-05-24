import { useState, useEffect, useRef, useCallback } from "react";

// ── pywebview 桥接 ──
function getApi() { return (window as any).pywebview?.api; }
function hasApi() { return !!(window as any).pywebview?.api; }

// ── 类型 ──
interface PhaseState { id: number; name: string; model: string; status: string; thinking: string; error?: string; }
interface ModelConfig { role: string; label: string; modelId: string; provider: string; apiKey: string; apiBase: string; }
type ChatMsg = { role: string; content: string };

const PHASES = [
  { id:0, name:"Phase 0 · 主题设计", model:"设计总监" },
  { id:1, name:"Phase 1 · 详细设计", model:"设计总监" },
  { id:2, name:"Phase 2 · 执行", model:"设计工程师", subAgents:[
    {id:"s0",name:"🔧 3D建模", model:"FreeCAD"},
    {id:"s1",name:"⚡ 电路设计", model:"KiCad"},
    {id:"s2",name:"💻 嵌入式编程", model:"Arduino/STM32"},
  ]},
  { id:3, name:"Phase 3 · 视觉初审", model:"视觉质检师" },
  { id:4, name:"Phase 4 · 审核决策", model:"设计总监" },
  { id:5, name:"Phase 5 · 最终交付", model:"设计总监" },
];

const FALLBACK_MODELS: ModelConfig[] = [
  { role:"manager",  label:"设计总监",   modelId:"glm-5.1",          provider:"zhipu",    apiKey:"", apiBase:"https://open.bigmodel.cn/api/paas/v4/chat/completions" },
  { role:"executor", label:"设计工程师", modelId:"deepseek-v4-flash", provider:"deepseek", apiKey:"", apiBase:"https://api.deepseek.com/v1/chat/completions" },
  { role:"reviewer", label:"视觉质检师", modelId:"glm-5v-turbo",      provider:"zhipu",    apiKey:"", apiBase:"https://open.bigmodel.cn/api/paas/v4/chat/completions" },
  { role:"coder",    label:"嵌入式工程师",modelId:"deepseek-v4-pro",  provider:"deepseek", apiKey:"", apiBase:"https://api.deepseek.com/v1/chat/completions" },
];

function tabStyle(active:boolean):any { return {flex:1,padding:"8px 0",textAlign:"center",fontSize:11,cursor:"pointer",border:"none",background:active?"#0f172a":"transparent",color:active?"#e2e8f0":"#64748b",borderBottom:active?"2px solid #3b82f6":"2px solid transparent"}; }

export default function App() {
  const [phases, setPhases] = useState<PhaseState[]>(() => PHASES.map(p=>({...p,status:"pending",thinking:""})));
  const [active, setActive] = useState(0);
  const [msgs, setMsgs] = useState<ChatMsg[]>([]);
  const [input, setInput] = useState("");
  const [running, setRunning] = useState(false);
  const [cfgOpen, setCfgOpen] = useState(false);
  const [editing, setEditing] = useState<ModelConfig[]>(() => JSON.parse(JSON.stringify(FALLBACK_MODELS)));
  const [bridge, setBridge] = useState(false);
  const [toast, setToast] = useState("");
  const [stepLogs, setStepLogs] = useState<Record<number,{type:string,text:string,ts:number,full?:string}[]>>({});
  const [rightTab, setRightTab] = useState("steps");
  const [questions, setQuestions] = useState<{question:string,options:string[],multi:boolean}[]>([]);
  const [answers, setAnswers] = useState<Record<number,string>>({});
  const [clarifySummary, setClarifySummary] = useState("");
  const [sessions, setSessions] = useState<{id:string,title:string,time:string}[]>([]);
  const [currentSid, setCurrentSid] = useState("");
  const [foldPhase2, setFoldPhase2] = useState(false);  // Phase 2 折叠
  const [activeSub, setActiveSub] = useState("");        // 当前 sub-agent
  const chatRef = useRef<HTMLDivElement>(null);
  const thinkRef = useRef<HTMLDivElement>(null);
  const pollRef = useRef<any>(null);
  const thinkText = useRef("");  // 流式思考累积器

  // 步骤日志辅助
  const addStep = (pid:number, entry:{type:string,text:string,ts:number,full?:string})=>{
    setStepLogs(p=>({...p, [pid]: [...(p[pid]||[]).filter(x=>x.type!=="think-stream"), entry]}));
  };
  const appendStream = (pid:number, text:string)=>{
    // 直接用 ref 写 DOM，React 不参与文本控制
    thinkText.current += text;
    if(thinkRef.current) thinkRef.current.textContent = thinkText.current;
    // 只更新 state（不用于渲染文本），用于会话保存
    setPhases(p=>p.map(x=>x.id===pid?{...x,thinking:x.thinking+text}:x));
  };

  const toast_ = (m:string)=>{ setToast(m); setTimeout(()=>setToast(""),2500); };

  // 加载会话列表
  const loadSessions = useCallback(async()=>{
    const a=getApi();if(!a)return;
    try{const l=JSON.parse(await a.list_sessions());setSessions(l||[]);}catch(_){}
  },[]);
  useEffect(()=>{setTimeout(loadSessions,800);},[bridge]);

  // 加载会话并还原所有状态
  const restoreSession = async(sid:string)=>{
    const a=getApi();if(!a)return;
    setCurrentSid(sid);
    const raw = await a.load_session(sid);
    try{
      const s = JSON.parse(raw);
      if(s.phases&&s.phases.length>0){
        const ps = PHASES.map(p=>{
          const found = s.phases.find((x:any)=>x.id===p.id);
          return found ? {...p, status:found.status||"done", thinking:found.thinking||""} : {...p, status:"pending", thinking:""};
        });
        setPhases(ps);
        // 重建步骤日志
        const logs: Record<number,any[]> = {};
        s.phases.forEach((p:any)=>{
          logs[p.id] = [{type:"think",text:`✅ 完成（${p.thinking?.length||0}字）`,ts:Date.now()-1000,full:p.thinking}];
        });
        setStepLogs(logs);
        // 聊天消息
        const ms:ChatMsg[] = [];
        if(s.user_idea) ms.push({role:"user",content:s.user_idea});
        if(s.msgs) s.msgs.forEach((m:any)=>ms.push(m));
        s.phases.forEach((p:any)=>{
          if(p.thinking) ms.push({role:"assistant",content:`## ${p.name}\n\n${p.thinking.slice(0,1200)}`});
        });
        setMsgs(ms);
      }
    }catch(_){}
  };

  // 自动滚底
  useEffect(()=>{ chatRef.current?.scrollTo({top:chatRef.current.scrollHeight,behavior:"smooth"}); },[msgs]);

  // 检测桥接
  useEffect(()=>{
    let n=0;
    const t=()=>{
      if(hasApi()){ setBridge(true); return; }
      if(++n<30) setTimeout(t,500);
    };
    setTimeout(t,300);
  },[]);

  // 轮询
  const startPoll = useCallback(()=>{
    if(pollRef.current) return;
    pollRef.current = setInterval(async()=>{
      const a=getApi(); if(!a) return;
      try{
        const evts=JSON.parse(await a.poll_events());
        for(const e of evts) handleEvt(e);
      }catch(_){}
    },100);  // 100ms 高频轮询 → 流式逐字显示
  },[]);

  const stopPoll = useCallback(()=>{ if(pollRef.current){ clearInterval(pollRef.current); pollRef.current=null; } },[]);

  const handleEvt = useCallback((e:any)=>{
    const t=e.type, d=e.data, pid=d.phase_id??d.id??-1;
    if(t==="phase_start"){
      setRunning(true);
      thinkText.current = "";  // 清空思考累积器
      setPhases(p=>p.map(x=>x.id===d.id?{...x,status:"running",thinking:""}:x));
      setActive(d.id);
      addStep(d.id,{type:"phase",text:`▶ ${d.name}`,ts:Date.now()});
      setQuestions([]); setAnswers({});
    }else if(t==="thinking_stream"){
      setPhases(p=>p.map(x=>x.id===pid?{...x,thinking:x.thinking+d.text}:x));
      appendStream(pid, d.text);
    }else if(t==="thinking"){
      setPhases(p=>p.map(x=>x.id===pid?{...x,thinking:d.text,model:d.model||x.model}:x));
      addStep(pid,{type:"think",text:`✅ ${d.model||"AI"} 完成（${d.text.length}字）`,ts:Date.now(),full:d.text});
      // 聊天区也显示
      const phase = PHASES[pid];
      const label = phase ? phase.name : `Phase ${pid}`;
      setMsgs(p=>[...p,{role:"assistant",content:`## ${label} — ${d.model||"AI"}\n\n${d.text.slice(0,1200)}${d.text.length>1200?"\n\n...[截断]":""}`}]);
    }else if(t==="phase_end"){
      setPhases(p=>p.map(x=>x.id===d.id?{...x,status:d.status||"done",error:d.error}:x));
      addStep(d.id,{type:"done",text:`✅ ${d.name||"Phase"} 完成`,ts:Date.now()});
    }else if(t==="error"){
      setMsgs(p=>[...p,{role:"system",content:"⚠ "+d}]);
      addStep(d.phase_id??active,{type:"error",text:`❌ ${d}`,ts:Date.now()});
    }else if(t==="pipeline_done"){
      setRunning(false); stopPoll();
      setMsgs(p=>[...p,{role:"assistant",content:d.message}]);
      addStep(99,{type:"done",text:"🎉 全部完成",ts:Date.now()});
    }else if(t==="pipeline_stopped"){
      setRunning(false); stopPoll();
      setPhases(p=>p.map(x=>x.status==="running"?{...x,status:"pending",thinking:""}:x));
      setMsgs(p=>[...p,{role:"system",content:"⏹ 已停止"}]);
      addStep(active,{type:"stop",text:"⏹ 用户停止",ts:Date.now()});
      setQuestions([]); setAnswers({});
    }else if(t==="judging"){
      addStep(-1,{type:"phase",text:"🔍 "+d.text,ts:Date.now()});
    }else if(t==="chat_response"){
      setMsgs(p=>[...p,{role:"assistant",content:d.text}]);
      addStep(-1,{type:"think",text:"💬 聊天回复",ts:Date.now()});
      // 如果是澄清后的回复（含"开始工业设计"），不设 running=false
      if(!d.text.includes("Pipeline")){ setRunning(false); stopPoll(); }
    }else if(t==="clarify_questions"){
      setQuestions(d.questions||[]); setAnswers({}); setClarifySummary(d.summary||"");
      setMsgs(p=>[...p,{role:"system",content:"🤔 需要你确认几个问题，请在下方选择..."}]);
      addStep(-1,{type:"think",text:"❓ 生成澄清问题",ts:Date.now()});
    }else if(t==="session_created"){
      setCurrentSid(d.id); loadSessions();
    }
  },[]);

  const stop = ()=>{
    const a=getApi();
    if(a) a.stop_pipeline();
    setRunning(false); stopPoll();
    setPhases(p=>p.map(x=>x.status==="running"?{...x,status:"pending",thinking:""}:x));
    setQuestions([]); setAnswers({});
  };

  const answerQuestion = ()=>{
    if(Object.keys(answers).length===0) return;
    setQuestions([]); setAnswers({});
    setRunning(true); startPoll();  // 设为运行态，开轮询
    const lines:string[] = [];
    questions.forEach((q,i)=>{
      const a = answers[i];
      if(a) lines.push(`Q: ${q.question}\nA: ${a}`);
    });
    const a=getApi();
    if(a){ a.answer_question(lines.join("\n\n")); }
  };

  const submit = ()=>{
    const idea=input.trim(); if(!idea||running) return;
    setInput(""); setMsgs([{role:"user",content:idea},{role:"system",content:"\uD83D\uDE80 Pipeline \u542F\u52A8..."}]);
    setRunning(true); setPhases(PHASES.map(p=>({...p,status:"pending",thinking:""}))); setActive(0);
    setStepLogs({}); startPoll();
    const a=getApi();
    if(a){ a.start_pipeline(idea); }
    else{ setMsgs(p=>[...p,{role:"system",content:"\u26A0 \u6865\u63A5\u672A\u5C31\u7EEA"}]);
      setRunning(false); stopPoll(); }
  };

  const saveCfg = async ()=>{
    const a=getApi(); if(!a){ toast_("\u6865\u63A5\u65AD\u8FDE"); return; }
    await a.save_models(JSON.stringify(editing));
    setCfgOpen(false); toast_("\u5DF2\u4FDD\u5B58");
  };

  const testModel = async (role:string)=>{
    const a=getApi(); if(!a){ toast_("\u6865\u63A5\u65AD\u8FDE"); return; }
    toast_("\u6B63\u5728\u6D4B\u8BD5...");
    const r=JSON.parse(await a.test_model(role));
    toast_(r.ok?`\u2705 ${r.response}`:`\u274C ${r.error}`);
  };

  const inpS:any = { width:"100%",height:34,padding:"0 10px",marginBottom:5,borderRadius:4,
    border:"1px solid #475569",background:"#020617",color:"#e2e8f0",fontSize:12,outline:"none" };

  const pd = phases[active];

  return (
    <div style={{height:"100%",display:"flex",flexDirection:"column",background:"#020617",color:"#e2e8f0",fontFamily:"sans-serif"}}>
      {/* 顶部栏 */}
      <div style={{height:42,background:"#0f172a",borderBottom:"1px solid #1e293b",display:"flex",alignItems:"center",padding:"0 14px",gap:10,flexShrink:0}}>
        <span style={{fontWeight:600,fontSize:13}}>⚙ Pipeline Desk</span>
        <span style={{fontSize:11,color:"#64748b"}}>工业设计 AI 工作台</span>
        <div style={{marginLeft:"auto"}}>
          <button onClick={()=>setCfgOpen(true)} style={{padding:"4px 12px",fontSize:11,borderRadius:4,border:"1px solid #334155",background:"transparent",color:"#94a3b8",cursor:"pointer"}}>⚙ 模型配置</button>
        </div>
      </div>

      {/* 主布局 */}
      <div style={{flex:1,display:"flex",overflow:"hidden"}}>
        {/* 左侧栏 */}
        <div style={{width:200,minWidth:200,background:"#020617",borderRight:"1px solid #1e293b",overflowY:"auto",padding:10}}>
          <div style={{fontSize:10,color:"#64748b",textTransform:"uppercase",marginBottom:8}}>Pipeline 阶段</div>
          {phases.map(p=>{
            const dotC = p.status==="done"?"#22c55e":p.status==="running"?"#3b82f6":p.status==="failed"?"#ef4444":"#475569";
            const isActive = active===p.id;
            const hasSub = !!(p as any).subAgents;
            return <div key={p.id}>
              <div onClick={()=>{
                setActive(p.id); setActiveSub("");
                thinkText.current = p.thinking||"";
                if(thinkRef.current) thinkRef.current.textContent = thinkText.current||"\u200B";
                if(p.id===2) setFoldPhase2(true);
              }} style={{display:"flex",alignItems:"center",gap:5,padding:"7px 10px",borderRadius:5,marginBottom:2,cursor:"pointer",background:isActive?"#1e3a5f":"transparent",border:isActive?"1px solid #3b82f6":"1px solid transparent"}}>
                {hasSub && <span onClick={(e)=>{e.stopPropagation();setFoldPhase2(!foldPhase2)}} style={{fontSize:8,width:10,transform:foldPhase2?"rotate(90deg)":"",transition:"transform .15s",color:"#64748b"}}>▶</span>}
                <div style={{width:8,height:8,borderRadius:"50%",background:dotC,animation:p.status==="running"?"pulse 1.5s infinite":undefined,flexShrink:0}} />
                <div style={{flex:1,overflow:"hidden"}}>
                  <div style={{fontWeight:500,fontSize:12,whiteSpace:"nowrap",textOverflow:"ellipsis",overflow:"hidden"}}>{p.name}</div>
                  <div style={{fontSize:10,color:p.status==="running"?"#3b82f6":"#64748b"}}>{p.status==="running"?"⚡ 运行中":p.status==="done"?"✅ 完成":p.status==="failed"?"❌ 失败":"等待中"}</div>
                </div>
              </div>
              {hasSub && foldPhase2 && (p as any).subAgents.map((s:any)=>(
                <div key={s.id} onClick={()=>{setActiveSub(s.id);setActive(2)}} style={{marginLeft:20,marginBottom:2,padding:"5px 8px",borderRadius:4,cursor:"pointer",background:activeSub===s.id?"#1e3a5f":"transparent",border:activeSub===s.id?"1px solid #334155":"1px solid transparent",fontSize:11,color:"#94a3b8"}}>
                  <div>{s.name}</div><div style={{fontSize:9,color:"#475569"}}>{s.model}</div>
                </div>
              ))}
            </div>;
          })}
          <div style={{marginTop:"auto",padding:"12px 0",borderTop:"1px solid #1e293b",fontSize:10,color:"#475569"}}>{running?"⚡ 运行中":"就绪"}</div>
          {/* 会话列表 */}
          <div style={{marginTop:6}}>
            <div style={{fontSize:9,color:"#475569",textTransform:"uppercase",marginBottom:4,padding:"0 2px"}}>📁 会话记录</div>
            <div style={{maxHeight:180,overflowY:"auto"}}>
              {sessions.slice(0,20).map((s:any)=>(
                <div key={s.id} onClick={()=>restoreSession(s.id)} style={{
                  padding:"5px 8px",marginBottom:2,borderRadius:4,cursor:"pointer",
                  background:currentSid===s.id?"#1e3a5f":"transparent",
                  color:"#94a3b8",fontSize:10
                }}>
                  <div style={{fontWeight:500,overflow:"hidden",textOverflow:"ellipsis",whiteSpace:"nowrap"}}>{s.title||s.id}</div>
                  <div style={{fontSize:8,color:"#475569"}}>{s.time}</div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* 中间 */}
        <div style={{flex:1,display:"flex",flexDirection:"column",background:"#0a0f1e",overflow:"hidden"}}>
          <div ref={chatRef} style={{flex:1,overflowY:"auto",padding:"16px 20px"}}>
            {msgs.length===0&&!running&&<div style={{textAlign:"center",padding:60,color:"#64748b"}}>
              <div style={{fontSize:40,marginBottom:10}}>💡</div>
              <div style={{fontSize:15,marginBottom:4}}>输入你的产品想法</div>
              <div style={{fontSize:11}}>例如："设计一台桌面级激光雕刻机，工作面积 300×200mm"</div>
            </div>}
            {msgs.map((m,i)=>(
              <div key={i} style={{marginBottom:12,maxWidth:"85%",marginLeft:m.role==="user"?"auto":0}}>
                <div style={{fontSize:10,color:"#64748b",marginBottom:2}}>{m.role==="user"?"🧑 你":m.role==="system"?"⚙":"🤖 AI"}</div>
                <div style={{padding:"8px 12px",borderRadius:6,fontSize:13,lineHeight:1.6,whiteSpace:"pre-wrap",wordBreak:"break-word",
                  background:m.role==="user"?"#1e3a5f":m.role==="system"?"transparent":"#1a2332",color:m.role==="system"?"#64748b":"#cbd5e1"}}>{m.content}</div>
              </div>
            ))}
            {pd?.status==="running"&&pd.thinking&&<div style={{marginBottom:12,maxWidth:"85%"}}>
              <div style={{fontSize:10,color:"#64748b",marginBottom:2}}>🤖 {pd.model}</div>
              <div style={{padding:"8px 12px",borderRadius:6,fontSize:13,lineHeight:1.6,whiteSpace:"pre-wrap",background:"#1a2332",color:"#cbd5e1",borderLeft:"2px solid #3b82f6"}}>{pd.thinking}</div>
            </div>}
          </div>

          {/* 选择题卡片 (WorkBuddy 风格) */}
          {questions.length>0 && <div style={{maxHeight:200,overflowY:"auto",padding:"0 16px 8px",flexShrink:0}}>
            {clarifySummary&&<div style={{fontSize:12,color:"#94a3b8",marginBottom:8,padding:"6px 10px",background:"#0f172a",borderRadius:4}}>📋 {clarifySummary}</div>}
            {questions.map((q,i)=>(
              <div key={i} style={{marginBottom:8,background:"#1e293b",borderRadius:6,padding:8,fontSize:11}}>
                <div style={{color:"#e2e8f0",marginBottom:6,fontWeight:500}}>{i+1}. {q.question}</div>
                <div style={{display:"flex",flexWrap:"wrap",gap:4}}>
                  {q.options.map((opt,j)=>(
                    <button key={j} onClick={()=>{setAnswers(p=>({...p,[i]:opt}));}}
                      style={{
                        padding:"4px 10px",borderRadius:4,fontSize:10,cursor:"pointer",
                        background:answers[i]===opt?"#3b82f6":"#0f172a",
                        color:answers[i]===opt?"#fff":"#94a3b8",
                        border:answers[i]===opt?"1px solid #3b82f6":"1px solid #334155",
                      }}>{opt}</button>
                  ))}
                </div>
                {q.multi&&<div style={{fontSize:9,color:"#64748b",marginTop:4}}>可多选</div>}
              </div>
            ))}
            <button onClick={answerQuestion}
              style={{width:"100%",padding:"8px",borderRadius:6,background:"#3b82f6",color:"#fff",border:"none",fontSize:12,cursor:"pointer",marginTop:4,opacity:Object.keys(answers).length>0?1:0.4}}>
              📤 提交选择 ({Object.keys(answers).length}/{questions.length})
            </button>
          </div>}

          {/* 输入栏 */}
          <div style={{height:52,display:"flex",alignItems:"center",gap:8,padding:"0 16px",background:"#0f172a",borderTop:"1px solid #1e293b",flexShrink:0}}>
            <input value={input} onChange={e=>setInput(e.target.value)} onKeyDown={e=>e.key==="Enter"&&submit()}
              disabled={running} autoFocus placeholder={running?"Pipeline 运行中..." :"输入你的产品想法，回车发送..."}
              style={{flex:1,height:36,padding:"0 12px",borderRadius:6,border:"1px solid #334155",background:"#020617",color:"#e2e8f0",fontSize:13,outline:"none"}} />
            {running ? (
              <button onClick={stop}
                style={{padding:"6px 16px",borderRadius:6,background:"#dc2626",color:"#fff",border:"none",fontSize:13,cursor:"pointer"}}>
                ⏹ 停止</button>
            ) : (
              <button onClick={submit} disabled={!input.trim()}
                style={{padding:"6px 16px",borderRadius:6,background:"#3b82f6",color:"#fff",border:"none",fontSize:13,cursor:input.trim()?"pointer":"not-allowed",opacity:input.trim()?1:0.4}}>
                发送</button>
            )}
          </div>
        </div>

        {/* 右侧栏 — 步骤面板 (Hermes 风格) */}
        <div style={{width:280,minWidth:280,background:"#020617",borderLeft:"1px solid #1e293b",display:"flex",flexDirection:"column",overflow:"hidden"}}>
          {/* 标签栏 */}
          <div style={{display:"flex",borderBottom:"1px solid #1e293b",flexShrink:0}}>
            <button onClick={()=>setRightTab("steps")} style={tabStyle(rightTab==="steps")}>📋 步骤</button>
            <button onClick={()=>setRightTab("detail")} style={tabStyle(rightTab==="detail")}>📊 详情</button>
          </div>

          {rightTab==="steps" ? (
            <div style={{flex:1,overflowY:"auto",padding:8}}>
              {/* 实时思考：ref 直接操作 DOM，逐字显示 */}
              <div ref={thinkRef} style={{
                padding:"6px 8px",marginBottom:4,borderRadius:4,background:"#0a1628",
                fontSize:11,lineHeight:1.5,borderLeft:"2px solid #3b82f6",
                color:"#e2e8f0",maxHeight:350,overflowY:"auto",whiteSpace:"pre-wrap",
                display:pd?.status==="running"?"block":"none"
              }}>&#8203;</div>
              {/* 历史步骤 */}
              {(stepLogs[active]||[]).slice().reverse().map((s:any,i:number)=>{
                const isStream=s.type==="think-stream";
                return <div key={i} style={{
                  padding:"6px 8px",marginBottom:3,borderRadius:4,
                  fontSize:11,lineHeight:1.5,wordBreak:"break-word",
                  background:s.type==="think"||isStream?"#0f172a":s.type==="error"?"#450a0a":s.type==="stop"?"#1a1a1a":"transparent",
                  color:s.type==="error"?"#fca5a5":s.type==="think"||isStream?"#94a3b8":"#64748b",
                  borderLeft:s.type==="phase"?"2px solid #3b82f6":s.type==="done"?"2px solid #22c55e":"2px solid transparent",
                }}>
                  <div style={{fontSize:9,color:"#475569",marginBottom:1}}>{new Date(s.ts).toLocaleTimeString()}</div>
                  {s.full&&<details style={{marginBottom:2}}><summary style={{fontSize:10,color:"#3b82f6",cursor:"pointer"}}>展开全文</summary><div style={{whiteSpace:"pre-wrap",fontSize:10,maxHeight:200,overflowY:"auto",padding:4}}>{s.full}</div></details>}
                </div>;
              })}
              {!pd?.thinking && (stepLogs[active]||[]).length===0 && (
                <div style={{padding:20,textAlign:"center",fontSize:11,color:"#475569"}}>
                  {pd?.status==="running" ? "等待 AI 响应..." : pd?.status==="done" ? "✅ 已完成" : "等待中"}
                  {activeSub&&<div style={{marginTop:4,fontSize:10,color:"#3b82f6"}}>◈ {PHASES[2].subAgents?.find((s:any)=>s.id===activeSub)?.name||activeSub}</div>}
                </div>
              )}
            </div>
          ) : (
            /* 详情面板 */
            <div style={{flex:1,overflowY:"auto",padding:10}}>
              {pd ? <div>
                <div style={{fontSize:12,fontWeight:500,marginBottom:8,color:"#e2e8f0"}}>{pd.name}</div>
                <div style={{fontSize:11,color:"#64748b",marginBottom:3}}>负责人: {pd.model}</div>
                <div style={{fontSize:11,color:"#64748b",marginBottom:3}}>状态: {
                  pd.status==="running"?"⚡ 执行中":pd.status==="done"?"✅ 完成":pd.status==="failed"?"❌ 失败":"等待中"}</div>
                {pd.error&&<div style={{marginTop:6,padding:6,background:"#450a0a",borderRadius:4,fontSize:10}}>❌ {pd.error}</div>}
                {pd.thinking&&<div style={{marginTop:8}}>
                  <div style={{fontSize:10,color:"#64748b",marginBottom:4,textTransform:"uppercase"}}>💭 思考过程</div>
                  <div style={{fontSize:11,lineHeight:1.6,color:"#94a3b8",whiteSpace:"pre-wrap",maxHeight:300,overflowY:"auto",background:"#0f172a",padding:8,borderRadius:4}}>{pd.thinking}</div>
                </div>}
              </div>:<div style={{fontSize:11,color:"#475569",padding:20,textAlign:"center"}}>选择一个 Phase</div>}
            </div>
          )}

          {/* 底部状态 */}
          <div style={{padding:"8px 10px",borderTop:"1px solid #1e293b",fontSize:10,color:running?"#3b82f6":"#475569",flexShrink:0}}>
            {running ? `⚡ ${phases[active]?.name||"运行中"}` : "⏸ 就绪"}
          </div>
        </div>
      </div>

      {/* 状态栏 */}
      <div style={{height:26,background:"#020617",borderTop:"1px solid #1e293b",display:"flex",alignItems:"center",padding:"0 12px",fontSize:10,gap:10,flexShrink:0,color:"#64748b"}}>
        <span>{running?"⚡ Running":"⏸ 就绪"}</span>
        <span style={{color:bridge?"#22c55e":"#ef4444"}}>{bridge?"🔗 已连接":"⚠ 桥接断连"}</span>
        <span style={{marginLeft:"auto"}}>{running?`Phase ${active}/6`:"输入想法开始"}</span>
      </div>

      {/* Toast */}
      {toast&&<div style={{position:"fixed",bottom:36,left:"50%",transform:"translateX(-50%)",background:"#1e293b",color:"#e2e8f0",padding:"8px 20px",borderRadius:6,fontSize:12,border:"1px solid #475569",zIndex:9999}}>{toast}</div>}

      {/* 配置面板 */}
      {cfgOpen&&<div onClick={()=>setCfgOpen(false)} style={{position:"fixed",inset:0,background:"rgba(0,0,0,0.65)",zIndex:999,display:"flex",alignItems:"center",justifyContent:"center"}}>
        <div onClick={e=>e.stopPropagation()} style={{width:500,maxHeight:"85vh",overflowY:"auto",background:"#1e293b",border:"1px solid #475569",borderRadius:12}}>
          <div style={{display:"flex",justifyContent:"space-between",padding:"12px 16px",background:"#0f172a",borderBottom:"1px solid #334155",borderRadius:"12px 12px 0 0",fontSize:13,fontWeight:600,color:"#94a3b8"}}>
            <span>⚙ 模型配置</span>
            <span onClick={()=>setCfgOpen(false)} style={{cursor:"pointer",fontSize:16}}>✕</span>
          </div>
          <div style={{padding:10}}>
            {editing.map((m,i)=><div key={m.role} style={{marginBottom:8,padding:10,background:"#0f172a",borderRadius:6,border:"1px solid #334155"}}>
              <div style={{display:"flex",justifyContent:"space-between",alignItems:"center",marginBottom:6,fontSize:13,fontWeight:500}}>
                <span>{m.role==="manager"?"👑":m.role==="executor"?"🔧":m.role==="reviewer"?"👁️":"💻"} {m.label}</span>
                <button onClick={()=>testModel(m.role)} style={{padding:"3px 10px",fontSize:11,borderRadius:4,border:"1px solid #475569",background:"transparent",color:"#94a3b8",cursor:"pointer"}}>测试</button>
              </div>
              <input placeholder="Model ID" value={m.modelId} onChange={e=>{const n=[...editing];n[i]={...n[i],modelId:e.target.value};setEditing(n);}} style={inpS} />
              <input placeholder="API Key" type="password" value={m.apiKey} onChange={e=>{const n=[...editing];n[i]={...n[i],apiKey:e.target.value};setEditing(n);}} style={inpS} />
              <input placeholder="API Base URL" value={m.apiBase} onChange={e=>{const n=[...editing];n[i]={...n[i],apiBase:e.target.value};setEditing(n);}} style={inpS} />
            </div>)}
          </div>
          <div style={{padding:"10px 16px",borderTop:"1px solid #334155"}}>
            <button onClick={saveCfg} style={{width:"100%",padding:"10px",borderRadius:6,background:"#3b82f6",color:"#fff",border:"none",fontSize:14,fontWeight:500,cursor:"pointer"}}>💾 保存配置</button>
          </div>
        </div>
      </div>}
    </div>
  );
}
