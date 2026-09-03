const api = require('../../services/api.js');
const recommendations = require('../../services/recommendations.js');

Page({
  data: {
    messages: [],
    input: '',
    sessionId: null,
    constraints: [],
    quickReplies: [],
    loading: false,
    scrollTop: 0,
  },

  onLoad() {
    const saved = wx.getStorageSync('agentConversation');
    this.setData(
      saved && saved.messages
        ? {
            messages: saved.messages,
            sessionId: saved.sessionId || null,
            constraints: saved.constraints || [],
            quickReplies: saved.quickReplies || [],
          }
        : {
            messages: [
        {
          role: 'agent',
          text: '你最近想找什么样的搭子？例如：周六下午想找两个羽毛球搭子，最好在西区，休闲一点。',
        },
      ],
          }
    );
  },

  persist() {
    wx.setStorageSync('agentConversation', {
      messages: this.data.messages,
      sessionId: this.data.sessionId,
      constraints: this.data.constraints || [],
      quickReplies: this.data.quickReplies || [],
    });
  },

  buildConstraints(intent) {
    const items = [];
    if (intent && intent.activity) items.push('活动：' + intent.activity);
    if (intent && intent.availability && intent.availability.length) {
      items.push('时间：' + intent.availability.join('、'));
    }
    if (intent && intent.campus) items.push('校区：' + intent.campus);
    if (intent && intent.level) items.push('水平：' + intent.level);
    return items;
  },

  newConversation() {
    wx.removeStorageSync('agentConversation');
    this.setData({
      messages: [{ role: 'agent', text: '已开始新需求。你想找什么样的搭子？' }],
      sessionId: null,
      constraints: [],
      quickReplies: [],
    });
  },

  sendQuick(e) {
    this.setData({ input: e.currentTarget.dataset.reply || '' });
    this.send();
  },

  onInput(e) {
    this.setData({ input: e.detail.value });
  },

  send() {
    const message = (this.data.input || '').trim();
    if (!message || this.data.loading) {
      return;
    }
    this.setData({
      input: '',
      loading: true,
      quickReplies: [],
      messages: this.data.messages.concat([
        { role: 'user', text: message },
        { role: 'agent', text: '正在为你找搭子…' },
      ]),
    });

    this.requestAgent(message, false);
  },

  requestAgent(message, retriedAfterExpiry) {
    api.agentChat(message, 3, this.data.sessionId).then(
      (result) => {
        this.setData({
          sessionId: result.session_id || this.data.sessionId,
          constraints: this.buildConstraints(result.intent || {}),
          quickReplies: result.suggested_replies || [],
        });
        const items = this.data.messages.slice(0, -1);
        items.push({
          role: 'agent',
          text: result.message || '已为你找到候选人。',
          matches: result.matches || [],
          needs_clarification: result.needs_clarification || false,
        });
        if (result.response_type === 'recommendation') {
          recommendations.setLatest(result.matches || []);
        }
        this.setData({ messages: items, loading: false, scrollTop: 999999 });
        this.persist();
      },
      (err) => {
        if (
          !retriedAfterExpiry &&
          this.data.sessionId &&
          err.statusCode === 404
        ) {
          this.setData({ sessionId: null, constraints: [], quickReplies: [] });
          this.persist();
          this.requestAgent(message, true);
          return;
        }
        const items = this.data.messages.slice(0, -1);
        items.push({ role: 'agent', text: '出错了：' + err.message });
        this.setData({ messages: items, loading: false, scrollTop: 999999 });
        this.persist();
      }
    );
  },

  goDetail(e) {
    const candidateId = e.currentTarget.dataset.candidate;
    let candidate = null;
    for (let i = this.data.messages.length - 1; i >= 0; i -= 1) {
      const item = this.data.messages[i];
      if (item.matches) {
        candidate = item.matches.find((m) => m.id === candidateId) || null;
        if (candidate) {
          break;
        }
      }
    }
    if (candidate) {
      wx.setStorageSync('matchDetailCandidate', candidate);
      wx.navigateTo({ url: '/pages/match-detail/match-detail' });
    }
  },
});
