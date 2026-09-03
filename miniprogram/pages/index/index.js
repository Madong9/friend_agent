Page({
  goAgent() {
    wx.switchTab({ url: '/pages/agent/agent' });
  },
  goProfile() {
    wx.switchTab({ url: '/pages/profile/profile' });
  },
  goMatches() {
    wx.switchTab({ url: '/pages/matches/matches' });
  },
});
