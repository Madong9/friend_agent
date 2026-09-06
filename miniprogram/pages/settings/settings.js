const api = require('../../services/api.js');

Page({
  data: {
    me: {},
    loading: false,
    loadError: '',
  },

  onShow() {
    this.setData({ loading: true, loadError: '' });
    api.getMe().then(
      (me) => {
        this.setData({ me, loading: false, loadError: '' });
      },
      (err) => {
        this.setData({ loading: false, loadError: err.message || '设置加载失败' });
      }
    );
  },

  onRecommendationToggle(e) {
    const checked = e.detail.value;
    this.setData({ loading: true });
    api.updateMe({ recommendation_enabled: checked }).then(
      () => {
        this.setData({ 'me.recommendation_enabled': checked, loading: false });
      },
      (err) => {
        this.setData({ loading: false });
        wx.showToast({ title: err.message, icon: 'none' });
      }
    );
  },

  goNotifications() {
    wx.navigateTo({ url: '/pages/notifications/notifications' });
  },
});
