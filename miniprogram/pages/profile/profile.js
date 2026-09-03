const api = require('../../services/api.js');
const profileUtils = require('../../utils/profile.js');

Page({
  data: {
    form: {},
    interestsText: '',
    goalsText: '',
    activitiesText: '',
    availabilityText: '',
    avoidancesText: '',
    naturalText: '',
    personalityText: '',
    personalityConsent: false,
    unreadNotificationCount: 0,
    loading: false,
    loadError: '',
  },

  onShow() {
    this.load();
    this.loadNotificationSummary();
  },

  goSettings() {
    wx.navigateTo({ url: '/pages/settings/settings' });
  },

  goNotifications() {
    wx.navigateTo({ url: '/pages/notifications/notifications' });
  },

  loadNotificationSummary() {
    return api.getNotifications(true).then(
      (notifications) => {
        this.setData({
          unreadNotificationCount: Array.isArray(notifications)
            ? notifications.length
            : 0,
        });
      },
      () => {
        // The entry remains available even if its badge cannot be refreshed.
        // Profile loading and editing must not fail because of this summary.
        this.setData({ unreadNotificationCount: 0 });
      }
    );
  },

  load() {
    this.setData({ loading: true, loadError: '' });
    return api.getMe().then((user) => {
      if (!user || typeof user !== 'object' || Array.isArray(user)) {
        throw new Error('用户资料加载失败，请重试');
      }
      this.setData({
        form: user,
        interestsText: (user.interests || []).join(','),
        goalsText: (user.social_goals || []).join(','),
        activitiesText: (user.activities || []).join(','),
        availabilityText: (user.availability || []).join(','),
        avoidancesText: (user.avoidances || []).join(','),
        personalityConsent: user.personality_consent || false,
        loading: false,
        loadError: '',
      });
    }).catch((err) => {
      const message = err && err.message ? err.message : '登录或用户资料加载失败';
      this.setData({
        form: {},
        loading: false,
        loadError: message,
      });
      wx.showToast({ title: message, icon: 'none' });
    });
  },

  onField(e) {
    const field = e.currentTarget.dataset.field;
    this.setData({
      [`form.${field}`]: e.detail.value,
    });
  },

  onInterests(e) {
    this.setData({ interestsText: e.detail.value });
  },

  onGoals(e) {
    this.setData({ goalsText: e.detail.value });
  },

  onAvailability(e) {
    this.setData({ availabilityText: e.detail.value });
  },

  onActivities(e) {
    this.setData({ activitiesText: e.detail.value });
  },

  onAvoidances(e) {
    this.setData({ avoidancesText: e.detail.value });
  },

  onNatural(e) {
    this.setData({ naturalText: e.detail.value });
  },

  onPersonalityText(e) {
    this.setData({ personalityText: e.detail.value });
  },

  onPersonalityConsent(e) {
    this.setData({ personalityConsent: e.detail.value });
  },

  analyzePersonality() {
    if (!this.data.personalityConsent) {
      wx.showToast({ title: '请先同意性格分析', icon: 'none' });
      return;
    }
    if ((this.data.personalityText || '').trim().length < 10) {
      wx.showToast({ title: '请多写一点社交偏好', icon: 'none' });
      return;
    }
    this.setData({ loading: true });
    api.analyzePersonality(this.data.personalityText).then(
      () => {
        this.setData({ personalityText: '', loading: false });
        wx.showToast({ title: '性格偏好已更新', icon: 'success' });
        this.load();
      },
      (err) => {
        this.setData({ loading: false });
        wx.showToast({ title: err.message, icon: 'none' });
      }
    );
  },

  clearPersonality() {
    wx.showModal({
      title: '删除性格分析',
      content: '将删除结构化性格标签和摘要，不影响其他画像。',
      success: (res) => {
        if (!res.confirm) return;
        api.clearPersonality().then(() => {
          this.setData({ personalityConsent: false });
          this.load();
        });
      },
    });
  },

  buildPayload() {
    return profileUtils.buildProfileUpdate(this.data.form, {
      interestsText: this.data.interestsText,
      goalsText: this.data.goalsText,
      activitiesText: this.data.activitiesText,
      availabilityText: this.data.availabilityText,
      avoidancesText: this.data.avoidancesText,
    });
  },

  save() {
    this.setData({ loading: true });
    api.updateMe(this.buildPayload()).then(
      () => {
        wx.showToast({ title: '保存成功', icon: 'success' });
        this.load();
        this.setData({ loading: false });
      },
      (err) => {
        wx.showToast({ title: err.message, icon: 'none' });
        this.setData({ loading: false });
      }
    );
  },

  parseNatural() {
    if (!this.data.naturalText) {
      return;
    }
    this.setData({ loading: true });
    api.parseProfile(this.data.naturalText, true).then(
      () => {
        wx.showToast({ title: '已解析并保存', icon: 'success' });
        this.setData({ naturalText: '', loading: false });
        this.load();
      },
      (err) => {
        wx.showToast({ title: err.message, icon: 'none' });
        this.setData({ loading: false });
      }
    );
  },
});
