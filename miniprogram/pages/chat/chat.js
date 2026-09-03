const api = require('../../services/api.js');

Page({
  data: { partner: null, meId: '', messages: [], input: '', loading: false },

  onLoad() {
    const partner = wx.getStorageSync('chatPartner');
    this.setData({ partner: partner || null });
    api.getMe().then((me) => {
      this.setData({ meId: me.id });
      this.loadMessages();
    });
  },

  onShow() {
    this.startPolling();
  },

  onHide() {
    this.stopPolling();
  },

  onUnload() {
    this.stopPolling();
  },

  startPolling() {
    this.stopPolling();
    this.pollTimer = setInterval(() => this.loadMessages(true), 4000);
  },

  stopPolling() {
    if (this.pollTimer) clearInterval(this.pollTimer);
    this.pollTimer = null;
  },

  loadMessages(silent = false) {
    if (!this.data.partner) return;
    if (!silent) this.setData({ loading: true });
    api.getMessages(this.data.partner.id).then(
      (messages) => {
        this.setData({ messages: messages || [], loading: false });
        api.markConversationRead(this.data.partner.id).catch(() => null);
      },
      (err) => {
        this.setData({ loading: false });
        if (!silent) wx.showToast({ title: err.message, icon: 'none' });
      }
    );
  },

  onInput(e) {
    this.setData({ input: e.detail.value });
  },

  send() {
    const body = (this.data.input || '').trim();
    if (!body || !this.data.partner || this.data.loading) return;
    this.setData({ input: '', loading: true });
    api.sendMessage(this.data.partner.id, body).then(
      () => this.loadMessages(),
      (err) => {
        this.setData({ loading: false });
        wx.showToast({ title: err.message, icon: 'none' });
      }
    );
  },
});
