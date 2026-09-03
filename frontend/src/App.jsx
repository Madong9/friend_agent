import { useEffect, useRef, useState } from "react";

const API = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";
const TOKEN_KEY = "campus_social_access_token";
const featureLabels = {
  interest: "Interest",
  activity: "Activity",
  availability: "Time",
  social_goal: "Social Goal",
  location: "Location",
  feedback: "Feedback",
};

function errorMessage(detail, status) {
  if (typeof detail === "string") return detail;
  if (detail?.message) return detail.message;
  return detail ? JSON.stringify(detail) : `请求失败 ${status}`;
}

async function api(path, options = {}) {
  const token = localStorage.getItem(TOKEN_KEY);
  const { auth = true, headers: extraHeaders = {}, ...fetchOptions } = options;
  const headers = {
    "Content-Type": "application/json",
    ...(token && auth ? { Authorization: `Bearer ${token}` } : {}),
    ...extraHeaders,
  };
  const response = await fetch(`${API}${path}`, { ...fetchOptions, headers });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    if (response.status === 401 && auth) {
      localStorage.removeItem(TOKEN_KEY);
    }
    throw new Error(errorMessage(payload.detail, response.status));
  }
  return response.json();
}

function consumeAuthRedirect() {
  if (typeof window === "undefined") return null;
  const hashRaw = window.location.hash.startsWith("#") ? window.location.hash.slice(1) : "";
  const searchRaw = window.location.search.startsWith("?") ? window.location.search.slice(1) : "";
  const hashParams = new URLSearchParams(hashRaw);
  const searchParams = new URLSearchParams(searchRaw);
  const accessToken = hashParams.get("access_token");
  const authError = searchParams.get("auth_error");
  const authStage = searchParams.get("auth_stage");
  window.history.replaceState({}, document.title, window.location.pathname + window.location.search);
  if (accessToken) {
    return { accessToken, authStage: authStage || "ustc" };
  }
  if (authError) {
    return { authError, authStage: authStage || "ustc" };
  }
  return null;
}

function needsProfileBinding(profile) {
  return profile && (profile.campus === "待完善" || profile.grade === "待完善" || profile.major === "待完善");
}

function splitListInput(value) {
  return value.split(/[,，、]/).map(item => item.trim()).filter(Boolean);
}

function LoginScreen({ onLogin }) {
  const [schoolEmail, setSchoolEmail] = useState("user001@ustc.edu.cn");
  const [password, setPassword] = useState("CampusDemo123!");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function submit(event) {
    event.preventDefault();
    setLoading(true);
    setError("");
    try {
      const result = await api("/auth/login", {
        method: "POST",
        auth: false,
        body: JSON.stringify({ school_email: schoolEmail, password }),
      });
      onLogin(result);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setLoading(false);
    }
  }

  function loginWithUstc() {
    window.location.href = `${API}/auth/ustc/login?next=${encodeURIComponent("/")}`;
  }

  return (
    <main className="login-page">
      <section className="login-card">
        <div className="brand login-brand">
          <span>搭</span>
          <div><b>校园搭子</b><small>AI Agent</small></div>
        </div>
        <span className="eyebrow">CAMPUS LOGIN</span>
        <h1>登录校园搭子</h1>
        <p>使用校内邮箱登录，前台只展示匿名昵称。</p>
        {error && <div className="notice">{error}</div>}
        <form onSubmit={submit} className="login-form">
          <label>校内邮箱<input value={schoolEmail} onChange={event => setSchoolEmail(event.target.value)} /></label>
          <label>密码<input type="password" value={password} onChange={event => setPassword(event.target.value)} /></label>
          <button className="primary" disabled={loading}>{loading ? "登录中…" : "登录"}</button>
        </form>
        <button className="secondary" onClick={loginWithUstc}>使用 USTC 登录</button>
        <small className="demo-tip">默认账号：user001@ustc.edu.cn / CampusDemo123!</small>
      </section>
    </main>
  );
}

function AuthCallbackScreen({ stage, error, onRetry }) {
  if (error) {
    return (
      <main className="auth-state-page">
        <section className="auth-state-card error-state">
          <span className="eyebrow">USTC LOGIN</span>
          <h1>登录失败</h1>
          <p>{error}</p>
          <button className="primary" onClick={onRetry}>返回登录页重试</button>
        </section>
      </main>
    );
  }
  return (
    <main className="auth-state-page">
      <section className="auth-state-card">
        <span className="eyebrow">USTC LOGIN</span>
        <h1>正在验证 USTC 登录…</h1>
        <p>{stage === "ustc" ? "正在和中国科大统一身份认证建立会话并写入本地登录态。" : "正在处理登录回调。"}</p>
      </section>
    </main>
  );
}

function OnboardingWizard({ profile, onComplete, onLogout }) {
  const [formState, setFormState] = useState({
    nickname: profile.nickname || "",
    campus: profile.campus === "待完善" ? "" : profile.campus,
    grade: profile.grade === "待完善" ? "" : profile.grade,
    major: profile.major === "待完善" ? "" : profile.major,
    bio: profile.bio || "",
    interests: (profile.interests || []).join("，"),
    availability: (profile.availability || []).join("，"),
    social_goals: (profile.social_goals || []).join("，"),
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  async function submit(event) {
    event.preventDefault();
    setSaving(true);
    setError("");
    try {
      const updated = await api(`/users/${profile.id}`, {
        method: "PATCH",
        body: JSON.stringify({
          nickname: formState.nickname,
          campus: formState.campus,
          grade: formState.grade,
          major: formState.major,
          bio: formState.bio,
          interests: splitListInput(formState.interests),
          availability: splitListInput(formState.availability),
          social_goals: splitListInput(formState.social_goals),
        }),
      });
      onComplete(updated);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <main className="onboarding-page">
      <section className="onboarding-card">
        <span className="eyebrow">USTC PROFILE</span>
        <h1>先补全你的校园资料</h1>
        <p>这是首次登录后的本地绑定步骤。填完后，Agent 才能开始根据你的校区、年级、专业和公开偏好做推荐。</p>
        {error && <div className="notice">{error}</div>}
        <form className="onboarding-form" onSubmit={submit}>
          <label>昵称<input value={formState.nickname} onChange={event => setFormState(current => ({ ...current, nickname: event.target.value }))} /></label>
          <label>校区<input value={formState.campus} onChange={event => setFormState(current => ({ ...current, campus: event.target.value }))} placeholder="如：西区 / 东区 / 北区" /></label>
          <label>年级<input value={formState.grade} onChange={event => setFormState(current => ({ ...current, grade: event.target.value }))} placeholder="如：研一 / 大二" /></label>
          <label>专业<input value={formState.major} onChange={event => setFormState(current => ({ ...current, major: event.target.value }))} placeholder="如：计算机 / 数学" /></label>
          <label className="wide">个人介绍<textarea value={formState.bio} onChange={event => setFormState(current => ({ ...current, bio: event.target.value }))} placeholder="简单介绍你的校园生活和交友偏好" /></label>
          <label className="wide">兴趣（逗号分隔）<input value={formState.interests} onChange={event => setFormState(current => ({ ...current, interests: event.target.value }))} placeholder="羽毛球，摄影，阅读" /></label>
          <label className="wide">有空时间（逗号分隔）<input value={formState.availability} onChange={event => setFormState(current => ({ ...current, availability: event.target.value }))} placeholder="周六下午，工作日晚上" /></label>
          <label className="wide">社交目标（逗号分隔）<input value={formState.social_goals} onChange={event => setFormState(current => ({ ...current, social_goals: event.target.value }))} placeholder="运动搭子，学习搭子" /></label>
          <div className="onboarding-actions">
            <button className="secondary" type="button" onClick={onLogout}>退出登录</button>
            <button className="primary" disabled={saving}>{saving ? "保存中…" : "完成并进入主页"}</button>
          </div>
        </form>
      </section>
    </main>
  );
}

function ScoreBars({ features }) {
  return <div className="score-bars">{Object.entries(features || {}).map(([key, value]) => (
    <div className="score-row" key={key}>
      <span>{featureLabels[key] || key}</span>
      <div className="track"><i style={{ width: `${Math.round(value * 100)}%` }} /></div>
      <strong>{Math.round(value * 100)}%</strong>
    </div>
  ))}</div>;
}

function MatchCard({ match, onFeedback, onDetail }) {
  return <article className="match-card">
    <header><div className="avatar">{match.nickname.slice(0, 1)}</div><div>
      <h3>{match.nickname}</h3><p>{match.grade} · {match.major} · {match.campus}</p>
    </div><b className="score">{Math.round(match.total * 100)}%</b></header>
    <p>{match.bio}</p>
    <div className="tags">{(match.interests || []).map(tag => <span key={tag}>{tag}</span>)}</div>
    <ul>{match.reasons.map(reason => <li key={reason}>{reason}</li>)}</ul>
    <blockquote>{match.icebreaker}</blockquote>
    <div className="actions">
      <button className="primary" onClick={() => onFeedback(match.id, "INTERESTED")}>感兴趣</button>
      <button onClick={() => onFeedback(match.id, "PASS")}>跳过</button>
      <button onClick={() => onFeedback(match.id, "NOT_RELEVANT")}>不相关</button>
      <button onClick={() => onDetail(match)}>匹配详情</button>
    </div>
  </article>;
}

export default function App() {
  const [token, setToken] = useState(() => localStorage.getItem(TOKEN_KEY));
  const [tab, setTab] = useState("agent");
  const [profile, setProfile] = useState(null);
  const [authCallback, setAuthCallback] = useState(null);
  const [message, setMessage] = useState("帮我找几个周六下午可以一起打羽毛球的人，最好西区，水平休闲一点。");
  const [result, setResult] = useState(null);
  const [agentSessionId, setAgentSessionId] = useState(null);
  const [detail, setDetail] = useState(null);
  const [loading, setLoading] = useState(false);
  const [notice, setNotice] = useState("");
  const [conversations, setConversations] = useState([]);
  const [activeConversation, setActiveConversation] = useState(null);
  const [messages, setMessages] = useState([]);
  const [chatBody, setChatBody] = useState("");
  const recommendInFlight = useRef(false);
  const lastAgentSubmit = useRef({ message: "", at: 0 });

  function handleProfileComplete(updatedProfile) {
    setProfile(updatedProfile);
    setNotice("资料已绑定，已进入校园搭子主页。");
    setTab("agent");
  }

  useEffect(() => {
    const redirect = consumeAuthRedirect();
    if (!redirect) return;
    if (redirect.accessToken) {
      localStorage.setItem(TOKEN_KEY, redirect.accessToken);
      setToken(redirect.accessToken);
      setAuthCallback({ stage: redirect.authStage, error: null });
      return;
    }
    if (redirect.authError) {
      localStorage.removeItem(TOKEN_KEY);
      setToken(null);
      setProfile(null);
      setAuthCallback({ stage: redirect.authStage, error: redirect.authError });
    }
  }, []);

  useEffect(() => {
    if (!token) return;
    let active = true;
    api("/auth/me")
      .then(data => {
        if (!active) return;
        setProfile(data);
        setAuthCallback(null);
        if (needsProfileBinding(data)) {
          setTab("profile");
          setNotice("首次使用 USTC 登录，请先补全校区、年级和专业等本地资料。");
        }
      })
      .catch(() => {
        if (!active) return;
        if (authCallback) {
          setAuthCallback({ stage: authCallback.stage, error: "USTC 登录验证失败，请返回重试。" });
          localStorage.removeItem(TOKEN_KEY);
          setToken(null);
          setProfile(null);
          return;
        }
        logout();
      });
    return () => { active = false; };
  }, [token, authCallback]);

  useEffect(() => {
    if (token && tab === "connections") loadConversations();
  }, [token, tab]);

  function login(data) {
    localStorage.setItem(TOKEN_KEY, data.access_token);
    setToken(data.access_token);
    setProfile(data.user);
    setAuthCallback(null);
    if (needsProfileBinding(data.user)) {
      setTab("profile");
      setNotice("首次使用 USTC 登录，请先补全校区、年级和专业等本地资料。");
    }
  }

  function logout() {
    api("/auth/logout", { method: "POST" }).catch(() => {});
    localStorage.removeItem(TOKEN_KEY);
    setToken(null);
    setProfile(null);
    setResult(null);
    setAgentSessionId(null);
    setConversations([]);
    setActiveConversation(null);
  }

  async function recommend() {
    const outgoingMessage = message.trim();
    const now = Date.now();
    if (!outgoingMessage || recommendInFlight.current) return;
    if (
      lastAgentSubmit.current.message === outgoingMessage
      && now - lastAgentSubmit.current.at < 1500
    ) {
      setNotice("已忽略短时间内的重复请求。");
      return;
    }
    recommendInFlight.current = true;
    lastAgentSubmit.current = { message: outgoingMessage, at: now };
    setLoading(true);
    setNotice("");
    try {
      const data = await api("/agent/recommend", {
        method: "POST",
        body: JSON.stringify({
          message: outgoingMessage,
          limit: 3,
          ...(agentSessionId ? { session_id: agentSessionId } : {}),
        }),
      });
      setResult(data);
      setAgentSessionId(data.session_id);
      setMessage("");
      if (data.profile) setProfile(data.profile);
      if (data.response_type === "recommendation") setTab("matches");
      else setTab("agent");
    } catch (requestError) {
      setNotice(requestError.message);
    } finally {
      recommendInFlight.current = false;
      setLoading(false);
    }
  }

  async function feedback(candidate, value) {
    try {
      const data = await api("/feedback", {
        method: "POST",
        body: JSON.stringify({ candidate_id: candidate, feedback: value }),
      });
      setNotice(data.matched ? "双方都感兴趣，已建立 Match，可以进入站内聊天。" : "反馈已记录，下次推荐会有限度地参考。");
      setResult(current => ({ ...current, matches: current.matches.filter(item => item.id !== candidate) }));
    } catch (requestError) {
      setNotice(requestError.message);
    }
  }

  async function saveProfile(event) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    try {
      const updated = await api(`/users/${profile.id}`, {
        method: "PATCH",
        body: JSON.stringify({
          nickname: form.get("nickname"),
          bio: form.get("bio"),
          interests: form.get("interests").split(/[,，、]/).map(value => value.trim()).filter(Boolean),
          availability: form.get("availability").split(/[,，、]/).map(value => value.trim()).filter(Boolean),
        }),
      });
      setProfile(updated);
      setNotice("画像已保存");
    } catch (requestError) {
      setNotice(requestError.message);
    }
  }

  async function loadConversations() {
    try {
      setConversations(await api("/conversations"));
    } catch (requestError) {
      setNotice(requestError.message);
    }
  }

  async function openConversation(conversation) {
    setActiveConversation(conversation);
    try {
      const partnerId = conversation.partner.id;
      setMessages(await api(`/conversations/${partnerId}/messages`));
      await api(`/conversations/${partnerId}/read`, { method: "POST" });
      loadConversations();
    } catch (requestError) {
      setNotice(requestError.message);
    }
  }

  async function sendChat(event) {
    event.preventDefault();
    if (!chatBody.trim() || !activeConversation) return;
    try {
      const sent = await api(`/conversations/${activeConversation.partner.id}/messages`, {
        method: "POST",
        body: JSON.stringify({ body: chatBody }),
      });
      setMessages(current => [...current, sent]);
      setChatBody("");
      loadConversations();
    } catch (requestError) {
      setNotice(requestError.message);
    }
  }

  if (!token) return <LoginScreen onLogin={login} />;
  if (authCallback) return <AuthCallbackScreen stage={authCallback.stage} error={authCallback.error} onRetry={() => { setAuthCallback(null); setNotice(""); }} />;
  if (!profile) return <div className="loading-page">正在读取校园画像…</div>;
  if (needsProfileBinding(profile)) return <OnboardingWizard profile={profile} onComplete={handleProfileComplete} onLogout={logout} />;

  return <div className="shell">
    <aside><div className="brand"><span>搭</span><div><b>校园搭子</b><small>AI Agent</small></div></div>
      <nav>{[
        ["agent", "对话找搭子"],
        ["matches", "推荐结果"],
        ["connections", "我的匹配"],
        ["profile", "我的画像"],
      ].map(([id, label]) => <button className={tab === id ? "active" : ""} onClick={() => setTab(id)} key={id}>{label}</button>)}</nav>
      <div className="identity"><label>已登录</label><b>{profile.nickname}</b><small>{profile.id}</small><button onClick={logout}>退出登录</button></div>
    </aside>
    <main>
      {notice && <div className="notice" onClick={() => setNotice("")}>{notice}</div>}
      {tab === "agent" && <section className="hero"><span className="eyebrow">CAMPUS SOCIAL AGENT</span>
        <h1>你最近想找什么样的搭子？</h1><p>描述活动、时间和校区，Agent 会规划、调用工具、硬过滤并给出可解释推荐。</p>
        <div className="composer"><textarea value={message} onChange={event => setMessage(event.target.value)} /><button disabled={loading || !message.trim()} onClick={recommend}>{loading ? "Agent 运行中…" : "发送给 Agent →"}</button></div>
        {agentSessionId && <button className="secondary" onClick={() => { setAgentSessionId(null); setResult(null); setNotice("已开始新的 Agent 会话"); }}>新会话</button>}
        {result && result.response_type !== "recommendation" && <div className="agent-reply">
          <b>Agent</b><p>{result.message}</p>
          {result.activities?.length > 0 && <ul>{result.activities.map(activity => <li key={activity.id}><strong>{activity.name}</strong> · {activity.campus} · {activity.location} · {activity.time}</li>)}</ul>}
          <small>Session {result.session_id.slice(0, 8)} · 本轮 {result.plan.length} 步</small>
        </div>}
        <div className="prompts">{["周六下午羽毛球搭子", "工作日晚上自习搭子", "周末摄影 Walk 伙伴"].map(text => <button key={text} onClick={() => setMessage(`帮我找${text}，最好西区。`)}>{text}</button>)}</div>
      </section>}
      {tab === "matches" && <section><div className="section-head"><div><span className="eyebrow">TOP MATCHES</span><h2>为你找到的校园伙伴</h2></div>{result && <small>Session {result.session_id.slice(0, 8)} · {result.plan.length} 步计划</small>}</div>
        {!result ? <div className="empty">先和 Agent 说说你想找什么搭子。</div> : result.matches.length === 0 ? <div className="empty">本轮没有候选，试试放宽时间或校区偏好。</div> :
          <div className="cards">{result.matches.map(match => <MatchCard key={match.id} match={match} onFeedback={feedback} onDetail={setDetail} />)}</div>}
      </section>}
      {tab === "connections" && <section><span className="eyebrow">MUTUAL MATCH</span><h2>我的匹配与聊天</h2>
        {conversations.length === 0 ? <div className="empty">双方都点击“感兴趣”后，才会在这里开放站内聊天。</div> : <div className="chat-layout">
          <div className="conversation-list">{conversations.map(item => <button key={item.match_id} className={activeConversation?.match_id === item.match_id ? "selected" : ""} onClick={() => openConversation(item)}><span className="avatar">{item.partner.nickname.slice(0, 1)}</span><span><b>{item.partner.nickname}</b><small>{item.last_message?.body || "开始聊天"}</small></span>{item.unread_count > 0 && <i>{item.unread_count}</i>}</button>)}</div>
          <div className="chat-panel">{!activeConversation ? <div className="empty">选择一位已匹配伙伴</div> : <><header><b>{activeConversation.partner.nickname}</b><small>已通过 Mutual Match 开放聊天</small></header><div className="messages">{messages.map(item => <div className={item.sender_id === profile.id ? "message mine" : "message"} key={item.id}>{item.body}</div>)}</div><form className="chat-composer" onSubmit={sendChat}><input value={chatBody} onChange={event => setChatBody(event.target.value)} placeholder="发送安全、友善的站内消息" /><button className="primary">发送</button></form></>}</div>
        </div>}
      </section>}
      {tab === "profile" && <section><span className="eyebrow">PROFILE MEMORY</span><h2>我的公开画像</h2>
        <form key={profile.id} className="profile-form" onSubmit={saveProfile}><label>昵称<input name="nickname" defaultValue={profile.nickname} /></label>
          <label>年级 / 专业<input disabled value={`${profile.grade} / ${profile.major}`} /></label>
          <label className="wide">个人介绍<textarea name="bio" defaultValue={profile.bio} /></label>
          <label className="wide">兴趣（用逗号分隔）<input name="interests" defaultValue={profile.interests.join("，")} /></label>
          <label className="wide">有空时间<input name="availability" defaultValue={profile.availability.join("，")} /></label>
          <button className="primary">保存画像</button></form>
        <p className="privacy">只展示昵称与主动公开画像；认证状态保留在后台，不输出学号、手机、宿舍或精确位置。</p>
      </section>}
    </main>
    {detail && <div className="modal-backdrop" onClick={() => setDetail(null)}><div className="modal" onClick={event => event.stopPropagation()}><button className="close" onClick={() => setDetail(null)}>×</button><span className="eyebrow">MATCH DETAIL</span><h2>{detail.nickname} · {Math.round(detail.total * 100)}%</h2><ScoreBars features={detail.features} /></div></div>}
  </div>;
}
