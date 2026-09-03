const api = require('../../services/api.js');

Page({
  data: {
    me: {},
  },

  onShow() {
    api.getMe().then(
      (me) => {
        this.setData({ me });
      },
      () => {}
    );
  },

  onRecommendationToggle(e) {
    const checked = e.detail.value;
    api.updateMe({ recommendation_enabled: checked }).then(
      () => {
        this.setData({ 'me.recommendation_enabled': checked });
      },
      (err) => {
        wx.showToast({ title: err.message, icon: 'none' });
      }
    );
  },

  goNotifications() {
    wx.navigateTo({ url: '/pages/notifications/notifications' });
  },
});
